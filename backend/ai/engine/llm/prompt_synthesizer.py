"""
Prompt Synthesizer — LLM-powered prompt generation, not template rendering.

Instead of hardcoding a SYSTEM_PROMPT_CHAT template, Pulse asks the LLM to write
the optimal system prompt for each instance. The prompt evolves as the knowledge
graph grows, memories accumulate, and the instance config is refined.

Design:
  - Synthesize on first use (or cache miss)
  - Cache in memory with content-hash invalidation
  - Re-synthesize when the knowledge graph is reloaded or a memory is added
  - Each instance gets a completely different prompt tailored to its domain

This means the system gets better day over day — prompt quality improves as
context deepens, without any human-written template changes.
"""
import hashlib
import json
import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.models import PromptVersion, generate_uuid
from ai.engine.llm.provider import chat_completion

logger = logging.getLogger("pulse.llm.prompt_synthesizer")

# ── Per-instance in-memory cache ──────────────────────────────────────────
# instance_id → {"prompt": str, "hash": str, "synthesized_at": float}
_prompt_cache: dict[str, dict] = {}

# ── Meta-prompt — the prompt that generates prompts ───────────────────────
# This is the ONLY hardcoded prompt in the system, and it's intentionally
# generic: it teaches the LLM how to write system prompts for any platform.

META_PROMPT = """You are an expert prompt engineer. Write a system prompt for Pulse, an AI operations copilot embedded in a software platform.

## Platform Context

- **Instance Name**: {display_name} ({name})
- **Description**: {description}
- **Domain**: {domain}
- **Audience**: {audience}
- **Domain Noun** (how to refer to the domain): {domain_noun}
- **Tagline**: {tagline}

## Available Host API Endpoints

The copilot can call these live API endpoints via `call_host_api(endpoint_name, params)`:

{api_catalog_text}

## Frontend Navigation Routes

The copilot can navigate the user to these pages via `open_entity` or `navigate_to`:

{navigation_routes_text}

## Domain Topics

The copilot ONLY discusses these topics -- everything else is off-topic:

{domain_topics_text}

## Learned Rules & Memories

These are facts, preferences, and business rules learned from past conversations:

{memories_text}

## Knowledge Graph Summary

The copilot has a knowledge graph with {kg_node_count} entities and {kg_edge_count} relationships connecting them.

{kg_summary_text}

---

Write a concise but comprehensive system prompt (under 1500 words). Structure it with these sections:

1. **Identity & Role** -- Who Pulse is in the context of this platform. How it adapts its role based on question type (analyst, advisor, expert, guide).

2. **Communication Rules** -- Emphasize brevity, audience-awareness, domain language, formatting. Use the platform's actual domain language -- never generic AI chatbot phrasing. Lead with the answer, no preamble.

3. **Domain Scope** -- What topics are in-scope, what's off-topic, the off-topic redirect message.

4. **Available Tools** -- When to use `call_host_api` (for live operational data) vs `search_knowledge` (for understanding concepts). Include entity-specific guidance (e.g., "to get the latest forecast, always call get_latest_predictions"). Reference specific API endpoint names from the catalog above.

5. **Investigation Protocol** -- How to follow chains of related entities. When the copilot finds an entity, what related things should it check? Build natural chains based on the entity types available in the API catalog.

6. **Operational Rules** -- Time-awareness, data grounding (never fabricate numbers), AI/ML confidentiality (never explain model internals or algorithms), consent before mutations, tool retry behavior, latest-available fallback.

7. **Memory & Learning** -- How the copilot learns from corrections (learn_fact tool), proposes memories, and builds expertise over time.

Critical guidelines:
- Reference the ACTUAL API endpoint names from the catalog -- be specific about which endpoints to call for which questions
- NEVER mention table names, SQL, column names, database schemas, or any software internals
- NEVER explain AI/ML internals -- say "AI forecasting engine" not "ensemble model" or "LightGBM"
- Use the platform's domain vocabulary throughout (not generic terms)
- The prompt must feel like it was written by someone who deeply knows THIS specific platform
- Keep it under 1500 words -- be concise but complete

Return ONLY the system prompt text, no preamble, no "Here is the system prompt:", no markdown fences."""


def _hash_config(
    instance_name: str,
    config: dict,
    kg_node_count: int,
    kg_edge_count: int,
    memory_count: int,
) -> str:
    """Compute a content hash for cache invalidation."""
    payload = {
        "name": instance_name,
        "config": config,
        "kg_nodes": kg_node_count,
        "kg_edges": kg_edge_count,
        "memories": memory_count,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


async def synthesize_system_prompt(
    instance_name: str,
    display_name: str,
    description: str,
    domain: str,
    persona: dict | None = None,
    api_catalog: list[dict] | None = None,
    navigation_routes: list[dict] | None = None,
    domain_topics: list[str] | None = None,
    memories_text: str = "",
    kg_node_count: int = 0,
    kg_edge_count: int = 0,
    kg_summary_text: str = "",
    optimize: bool = False,
    db: AsyncSession | None = None,
    instance_id: str = "",
) -> str:
    """Generate an optimal system prompt for a specific instance.

    Uses the LLM to write the prompt — no template rendering. The result
    is cached in memory until the inputs change.

    When optimize=True, routes through optimize_and_cache() which runs the
    critique→rewrite loop to improve prompt quality iteratively.
    """
    if optimize:
        if db is None:
            logger.warning("optimize=True but no db session provided — falling back to direct synthesis")
        else:
            return await optimize_and_cache(
                db=db,
                instance_name=instance_name,
                instance_id=instance_id,
                display_name=display_name,
                description=description,
                domain=domain,
                persona=persona,
                api_catalog=api_catalog,
                navigation_routes=navigation_routes,
                domain_topics=domain_topics,
                memories_text=memories_text,
                kg_node_count=kg_node_count,
                kg_edge_count=kg_edge_count,
                kg_summary_text=kg_summary_text,
            )
    persona = persona or {}
    api_catalog = api_catalog or []
    navigation_routes = navigation_routes or []
    domain_topics = domain_topics or []

    # ── Compute cache key ────────────────────────────────────────────────
    config_for_hash = {
        "display_name": display_name,
        "description": description,
        "domain": domain,
        "persona": persona,
        "api_names": sorted(ep.get("name", "") for ep in api_catalog),
        "routes": sorted(r.get("path", "") for r in navigation_routes),
        "topics": sorted(domain_topics),
    }
    content_hash = _hash_config(
        instance_name, config_for_hash,
        kg_node_count, kg_edge_count,
        len(memories_text),
    )

    # ── Cache hit? ───────────────────────────────────────────────────────
    cached = _prompt_cache.get(instance_name)
    if cached and cached.get("hash") == content_hash:
        age = time.time() - cached.get("synthesized_at", 0)
        logger.debug(
            f"Prompt cache HIT for {instance_name} "
            f"(age={age:.0f}s, hash={content_hash})"
        )
        return cached["prompt"]

    logger.info(
        f"Prompt cache MISS for {instance_name} — synthesizing new prompt "
        f"(hash={content_hash}, kg_nodes={kg_node_count}, kg_edges={kg_edge_count})"
    )

    # ── Format inputs for the meta-prompt ────────────────────────────────
    audience = persona.get("audience", "platform users")
    domain_noun = persona.get("domain_noun", "the connected host system")
    tagline = persona.get("domain_tagline", "an AI operations platform")

    # API catalog as readable text
    if api_catalog:
        api_lines = []
        for ep in api_catalog:
            name = ep.get("name", "unknown")
            method = ep.get("method", "GET")
            desc = (ep.get("description", "") or "").replace("\n", " ").strip()
            confirm = " [requires user confirmation]" if ep.get("requires_confirmation") else ""
            api_lines.append(f"- `{name}` ({method}): {desc}{confirm}")
        api_catalog_text = "\n".join(api_lines)
    else:
        api_catalog_text = "_No API endpoints configured._"

    # Navigation routes as readable text
    if navigation_routes:
        nav_lines = []
        for r in navigation_routes:
            path = r.get("path", "")
            desc = r.get("description", "")
            nav_lines.append(f"- {desc}: `{path}`")
        navigation_routes_text = "\n".join(nav_lines)
    else:
        navigation_routes_text = "_No frontend routes configured._"

    # Domain topics
    domain_topics_text = "\n".join(f"- {t}" for t in domain_topics) if domain_topics else "_No domain topics defined._"

    # Memories
    memories_display = memories_text if memories_text.strip() else "_No learned rules or memories yet._"

    # KG summary
    kg_display = kg_summary_text if kg_summary_text.strip() else "_No knowledge graph summary available._"

    # ── Build meta-prompt ────────────────────────────────────────────────
    meta_prompt = META_PROMPT.format(
        name=instance_name,
        display_name=display_name,
        description=description,
        domain=domain,
        audience=audience,
        domain_noun=domain_noun,
        tagline=tagline,
        api_catalog_text=api_catalog_text,
        navigation_routes_text=navigation_routes_text,
        domain_topics_text=domain_topics_text,
        memories_text=memories_display,
        kg_node_count=kg_node_count,
        kg_edge_count=kg_edge_count,
        kg_summary_text=kg_display,
    )

    # ── Synthesize via LLM ───────────────────────────────────────────────
    messages = [
        {"role": "system", "content": "You are an expert prompt engineer. You write precise, effective system prompts for AI copilots. Return ONLY the prompt text, no preamble, no markdown fences."},
        {"role": "user", "content": meta_prompt},
    ]

    try:
        synthesized = await chat_completion(messages, temperature=0.4)
    except Exception as exc:
        logger.error(f"Prompt synthesis failed for {instance_name}: {exc}")
        # Fall back to a minimal prompt
        synthesized = _minimal_fallback_prompt(
            display_name=display_name,
            description=description,
            domain_noun=domain_noun,
            audience=audience,
            domain_topics=domain_topics,
        )

    # Strip any markdown fences that the LLM might add
    synthesized = synthesized.strip()
    if synthesized.startswith("```"):
        synthesized = synthesized.split("\n", 1)[-1] if "\n" in synthesized else synthesized[3:]
    if synthesized.endswith("```"):
        synthesized = synthesized.rsplit("\n", 1)[0] if "\n" in synthesized else synthesized[:-3]
    synthesized = synthesized.strip()

    # ── Cache and return ─────────────────────────────────────────────────
    _prompt_cache[instance_name] = {
        "prompt": synthesized,
        "hash": content_hash,
        "synthesized_at": time.time(),
    }

    logger.info(
        f"Prompt synthesized for {instance_name}: "
        f"{len(synthesized)} chars, {synthesized.count(chr(10)) + 1} lines"
    )
    return synthesized


def invalidate_prompt_cache(instance_name: str) -> None:
    """Force re-synthesis on next call. Call this when the knowledge graph
    is reloaded, the instance config changes, or new memories are added.
    """
    if instance_name in _prompt_cache:
        del _prompt_cache[instance_name]
        logger.info(f"Prompt cache invalidated for {instance_name}")


def get_cached_prompt(instance_name: str) -> str | None:
    """Return the cached prompt if available, without re-synthesizing."""
    cached = _prompt_cache.get(instance_name)
    return cached["prompt"] if cached else None


def _minimal_fallback_prompt(
    display_name: str,
    description: str,
    domain_noun: str,
    audience: str,
    domain_topics: list[str],
) -> str:
    """Absolute minimal prompt used when LLM synthesis fails."""
    topics = "\n".join(f"- {t}" for t in domain_topics) if domain_topics else "- Platform operations"
    return f"""You are Pulse, the AI operations copilot for {display_name}.
{description}

Your audience is {audience}. You are a professional operations copilot — not a generic chatbot.

## Domain Scope
You ONLY discuss topics related to {domain_noun}:
{topics}

## Communication Rules
- Lead with the answer — no preamble or throat-clearing
- Use the platform's domain language
- Never mention table names, SQL, API paths, or software internals
- Never fabricate data — if a tool returns nothing, say so

## Tools
- Use `call_host_api` for operational data
- Use `search_knowledge` to understand concepts

## Operational Rules
- Always be time-aware — flag stale data
- Never explain AI/ML internals
- Ask for confirmation before mutations
- Learn from corrections using `learn_fact`"""


# ── Optimize-and-cache entry point ────────────────────────────────────────

async def optimize_and_cache(
    db: AsyncSession,
    instance_name: str,
    instance_id: str,
    display_name: str = "",
    description: str = "",
    domain: str = "",
    persona: dict | None = None,
    api_catalog: list[dict] | None = None,
    navigation_routes: list[dict] | None = None,
    domain_topics: list[str] | None = None,
    memories_text: str = "",
    kg_node_count: int = 0,
    kg_edge_count: int = 0,
    kg_summary_text: str = "",
) -> str:
    """Synthesize a seed prompt, save it as PromptVersion round 0,
    then run the optimizer to improve it through critique→rewrite.

    Returns the best prompt text.
    """
    from ai.engine.llm.prompt_optimizer import optimize_prompt

    # 1. Synthesize the seed prompt (same as normal path)
    seed_prompt = await synthesize_system_prompt(
        instance_name=instance_name,
        display_name=display_name,
        description=description,
        domain=domain,
        persona=persona,
        api_catalog=api_catalog,
        navigation_routes=navigation_routes,
        domain_topics=domain_topics,
        memories_text=memories_text,
        kg_node_count=kg_node_count,
        kg_edge_count=kg_edge_count,
        kg_summary_text=kg_summary_text,
        optimize=False,  # prevent recursion
    )

    if not seed_prompt:
        logger.error(f"Seed prompt synthesis failed for {instance_name}")
        return ""

    # 2. Save as PromptVersion round 0
    content_hash = hashlib.sha256(seed_prompt.encode()).hexdigest()[:16]
    version = PromptVersion(
        id=generate_uuid(),
        instance_id=instance_id,
        prompt_text=seed_prompt,
        content_hash=content_hash,
        improvement_round=0,
        is_active=True,
        parent_version_id=None,
    )
    db.add(version)
    await db.commit()

    logger.info(
        f"Saved seed PromptVersion round=0 for {instance_name} "
        f"(hash={content_hash}, {len(seed_prompt)} chars)"
    )

    # 3. Run the optimizer
    try:
        best_prompt = await optimize_prompt(
            db=db,
            instance_name=instance_name,
            instance_id=instance_id,
            max_rounds=3,
            min_score=0.65,
        )
    except Exception as exc:
        logger.error(
            f"Prompt optimization failed for {instance_name}: {exc}",
            exc_info=True,
        )
        best_prompt = seed_prompt

    # 4. Cache the winner in memory
    _prompt_cache[instance_name] = {
        "prompt": best_prompt,
        "hash": content_hash,
        "synthesized_at": time.time(),
    }

    logger.info(
        f"Prompt optimize-and-cache complete for {instance_name}: "
        f"{len(best_prompt)} chars"
    )
    return best_prompt
