"""
Iterative prompt optimizer — critique → rewrite loop.

Uses LLM to analyze eval failures and rewrite system prompts
so they score higher on the evaluation harness.
"""
import hashlib
import json
import logging
from typing import Optional
from uuid import uuid4

from ai.engine.core.config import get_settings
from ai.engine.core.models import PromptEval, PromptVersion, generate_uuid
from ai.engine.core.query import first
from ai.engine.llm.prompt_eval import compute_prompt_score, evaluate_prompt, get_eval_queries
from ai.engine.ports.store import Session

logger = logging.getLogger("pulse.llm.prompt_optimizer")


def _score_key(value):
    """Sort key for prompt scores (None-safe, None sorts last)."""
    if value is None:
        return -1.0
    return value

# ── Meta-prompts ──────────────────────────────────────────────────────────

CRITIQUE_META_PROMPT = """You are an expert prompt engineer conducting a quality review. Analyze the evaluation results below and write a detailed critique of the system prompt.

## Current Prompt
{prompt_text}

## Evaluation Results
{eval_summary}

## Instructions
1. Identify specific weaknesses in the prompt based on the eval failures.
2. Note any missing context, unclear instructions, or structural issues.
3. Point out which sections need improvement and why.
4. Be specific and actionable — cite examples from the failed queries.

Return a focused critique (under 500 words). Do NOT rewrite the prompt — only critique it."""


REWRITE_META_PROMPT = """You are an expert prompt engineer. Rewrite the system prompt to address the critique below.

## Current Prompt
{prompt_text}

## Critique
{critique}

## Platform Context
{instance_context}

## Instructions
1. Address every issue raised in the critique.
2. Maintain the original prompt's structure and domain language.
3. Improve clarity, specificity, and completeness.
4. Do not add new sections unless they address a specific critique point.
5. Keep the same overall length.

Return ONLY the rewritten system prompt text, no preamble, no markdown fences."""


# ── Public API ────────────────────────────────────────────────────────────

async def optimize_prompt(
    db: Session,
    instance_name: str,
    instance_id: str,
    max_rounds: int = 3,
    min_score: float = 0.65,
) -> str:
    """Full critique→rewrite loop. Saves PromptVersion rows. Returns best prompt text.

    Algorithm:
    1. Load the current active prompt (round 0).
    2. Evaluate it against sampled queries.
    3. If score >= min_score, return immediately.
    4. Critique → rewrite → evaluate → repeat up to max_rounds.
    5. Save each version with improvement_round and parent_version_id chain.
    6. Return the highest-scoring prompt.
    """
    # 1. Find the current active prompt version
    active = await db.select(
        PromptVersion,
        ("instance_id", instance_id),
        ("is_active", True),
    )
    active.sort(key=lambda v: v.improvement_round or 0, reverse=True)
    current_version = active[0] if active else None

    if current_version is None:
        logger.warning(f"No active prompt version for {instance_name} — cannot optimize")
        return ""

    prompt_text = current_version.prompt_text
    parent_id = current_version.id
    best_prompt = prompt_text
    best_score = current_version.score or 0.0

    queries = await get_eval_queries(db, instance_id, count=5)

    for round_num in range(1, max_rounds + 1):
        # Evaluate current prompt
        evals = await evaluate_prompt(db, prompt_text, instance_id, queries)

        # Save version first so evals can reference it
        version = PromptVersion(
            id=generate_uuid(),
            instance_id=instance_id,
            prompt_text=prompt_text,
            content_hash=hashlib.sha256(prompt_text.encode()).hexdigest()[:16],
            is_active=False,  # only activate winner at end
            improvement_round=round_num,
            parent_version_id=parent_id,
        )
        db.add(version)
        await db.flush()  # get the ID assigned without committing

        # Link evals to this version
        for pe in evals:
            pe.prompt_version_id = version.id
            db.add(pe)
        await db.flush()

        # Compute score
        score = await compute_prompt_score(db, version.id)
        version.score = score
        await db.flush()

        logger.info(
            f"Prompt round {round_num} for {instance_name}: "
            f"score={score:.4f} (best={best_score:.4f})"
        )

        if score >= best_score:
            best_score = score
            best_prompt = prompt_text

        if score >= min_score:
            logger.info(
                f"Prompt for {instance_name} reached threshold {min_score} "
                f"at round {round_num} (score={score:.4f})"
            )
            break

        if round_num >= max_rounds:
            break

        # Critique → rewrite
        critique = await _critique_prompt(prompt_text, evals, instance_id)
        prompt_text = await _rewrite_prompt(prompt_text, critique, {"name": instance_name}, instance_id)
        parent_id = version.id

    # Activate the winner
    await _activate_best(db, instance_id, best_score)
    await db.commit()

    logger.info(
        f"Prompt optimization complete for {instance_name}: "
        f"final_score={best_score:.4f}, rounds={round_num}"
    )
    return best_prompt


async def _critique_prompt(prompt_text: str, eval_results: list[PromptEval], instance_id: str) -> str:
    """LLM analyzes failures, returns natural-language critique."""
    if not eval_results:
        return "No evaluation data available — cannot critique."

    # Build eval summary
    lines = []
    for i, pe in enumerate(eval_results):
        status = "✓" if pe.task_completion else "✗"
        rel = f"relevance={pe.relevance_score:.2f}" if pe.relevance_score is not None else "relevance=N/A"
        lines.append(
            f"{i + 1}. [{status}] Query: {pe.query_text[:80]}... — {rel}"
        )
    eval_summary = "\n".join(lines)

    messages = [
        {"role": "system", "content": "You are an expert prompt engineer."},
        {"role": "user", "content": CRITIQUE_META_PROMPT.format(
            prompt_text=prompt_text[:6000],  # truncate for safety
            eval_summary=eval_summary,
        )},
    ]

    from ai.engine.llm.router import route_chat

    result = await route_chat(
        task="introspect",
        instance_id=instance_id,
        conversation_id=f"prompt-opt-{uuid4().hex[:8]}",
        messages=messages,
        temperature=0.4,
    )
    critique = result["content"] or ""
    return critique.strip()


async def _rewrite_prompt(
    current_prompt: str,
    critique: str,
    instance_context: dict,
    instance_id: str,
) -> str:
    """LLM rewrites prompt incorporating critique."""
    messages = [
        {"role": "system", "content": "You are an expert prompt engineer. Return ONLY the rewritten prompt, no preamble."},
        {"role": "user", "content": REWRITE_META_PROMPT.format(
            prompt_text=current_prompt[:6000],
            critique=critique[:2000],
            instance_context=json.dumps(instance_context, indent=2),
        )},
    ]

    from ai.engine.llm.router import route_chat

    result = await route_chat(
        task="introspect",
        instance_id=instance_id,
        conversation_id=f"prompt-opt-{uuid4().hex[:8]}",
        messages=messages,
        temperature=0.4,
    )
    rewritten = result["content"] or ""

    # Strip markdown fences if LLM adds them
    rewritten = rewritten.strip()
    if rewritten.startswith("```"):
        rewritten = rewritten.split("\n", 1)[-1] if "\n" in rewritten else rewritten[3:]
    if rewritten.endswith("```"):
        rewritten = rewritten.rsplit("\n", 1)[0] if "\n" in rewritten else rewritten[:-3]

    return rewritten.strip()


async def _activate_best(db: Session, instance_id: str, best_score: float) -> None:
    """Deactivate all prompts for this instance, then activate the highest-scoring one."""
    # Deactivate all
    all_versions = await db.select(
        PromptVersion, ("instance_id", instance_id)
    )
    for v in all_versions:
        v.is_active = False

    # Find the best-scoring version (None score sorts last)
    all_versions.sort(key=lambda v: _score_key(v.score), reverse=True)
    best = all_versions[0] if all_versions else None
    if best:
        best.is_active = True
