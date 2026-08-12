"""
System prompts and templates for Pulse LLM interactions.
All prompts use placeholder injection — never hardcode instance-specific content.

Prompts are now synthesized at runtime by llm.prompt_synthesizer — no
hardcoded per-instance template. The SYSTEM_PROMPT_INTROSPECT templates
below are the only remaining static prompts (schema analysis, not chat).
"""

# ── Note: SYSTEM_PROMPT_CHAT removed 2026-08-09 ──
# build_chat_prompt() now calls llm.prompt_synthesizer.synthesize_system_prompt()
# which uses LLM-powered prompt generation tailored to each instance.

import logging

logger = logging.getLogger("pulse.llm.prompts")

SYSTEM_PROMPT_INTROSPECT_SYSTEM = """You are a database schema analyst for a {domain} platform called {instance_name}.
{instance_description}
You respond ONLY with valid JSON — no markdown, no explanation, no code fences.
Output format: {{"table_name": "2-3 sentence business description", ...}}
For each description explain: (1) what the entity represents in the business domain, (2) what data it holds, (3) how it connects to the system's purpose."""

SYSTEM_PROMPT_INTROSPECT_USER = """Describe each of the following database tables as a business analyst would.

{tables_block}

Return a JSON object mapping each table name to its description."""


async def build_chat_prompt(
    instance_name: str,
    system_description: str,
    relevant_knowledge: str = "No knowledge loaded yet.",
    relevant_memories: str = "No memories available.",
    page_context: str = "unknown",
    current_datetime: str = "",
    user_info: dict | None = None,
    persona: dict | None = None,
    api_catalog: list[dict] | None = None,
    navigation_routes: list[dict] | None = None,
    domain_topics: list[str] | None = None,
    instance_config: dict | None = None,
    conversation_id: str = "",
    instance_id: str = "",
) -> str:
    """Build the system prompt for chat interactions.

    Uses the PlaybookAssembler to build the instance-specific prompt from
    versioned PlaybookBlocks (persona, domain rules, tool heuristics, lessons).
    Prepends a runtime header with per-conversation context (datetime, user,
    page, knowledge, memories) so that every request carries current state.

    When conversation_id + instance_id are provided, checks for an A/B
    candidate prompt (improvement_round=0, is_active=False).  20% of
    conversations are routed to the candidate for real-world testing.
    """
    from datetime import datetime, timezone
    from ai.engine.core.database import get_session_factory
    from ai.engine.llm.playbook import playbook_assembler

    config = instance_config or {}
    persona = persona or {}

    # ── Runtime header (per-conversation context) ──────────────────────────
    if not current_datetime:
        now_utc = datetime.now(timezone.utc)
        current_datetime = now_utc.strftime('%A, %B %d, %Y %H:%M UTC')

    if user_info:
        username = user_info.get("username", "Unknown")
        display_name = user_info.get("display_name") or username
        email = user_info.get("email") or ""
        roles = user_info.get("roles") or []
        email_part = f" <{email}>" if email else ""
        roles_part = f" — Roles: {', '.join(roles)}" if roles else ""
        user_context = f"**{display_name}**{email_part}{roles_part}"
    else:
        user_context = (
            "Anonymous (no Pulse API key configured — user identity unknown; "
            "answers must not expose data beyond what a public user could see)"
        )

    header = (
        f"# Pulse AI Copilot — {instance_name}\n\n"
        f"**Current time**: {current_datetime}\n"
        f"**Current user**: {user_context}\n"
        f"**Current page**: {page_context}\n"
    )

    # ── Assemble instance-specific prompt from PlaybookBlocks ──────────────
    runtime_ctx = {
        "instance_name": instance_name,
        "current_datetime": current_datetime,
        "user_context": user_context,
        "page_context": page_context,
        "relevant_knowledge": relevant_knowledge,
        "relevant_memories": relevant_memories,
    }

    if instance_id:
        factory = get_session_factory()
        async with factory() as _db:
            result = await playbook_assembler.assemble(
                db=_db,
                instance_id=instance_id,
                runtime_context=runtime_ctx,
            )
    else:
        # No instance_id — use fallback (test/standalone path)
        from ai.engine.llm.playbook import _fallback_prompt
        result = _fallback_prompt(runtime_ctx)

    # ── A/B candidate routing (20% traffic split) ─────────────────────────
    if conversation_id and instance_id:
        try:
            from ai.engine.core.models import PromptVersion
            from sqlalchemy import select

            factory2 = get_session_factory()
            async with factory2() as _ab_db:
                cand_result = await _ab_db.execute(
                    select(PromptVersion)
                    .where(
                        PromptVersion.instance_id == instance_id,
                        PromptVersion.is_active == False,  # noqa: E712
                        PromptVersion.improvement_round == 0,
                    )
                    .order_by(PromptVersion.synthesized_at.desc())
                    .limit(1)
                )
                candidate = cand_result.scalar_one_or_none()

            if candidate is not None:
                import hashlib
                h = int(hashlib.md5(conversation_id.encode()).hexdigest()[:8], 16)
                if h % 100 < 20:  # 20% traffic to candidate
                    logger.info(
                        f"A/B split: routing conv={conversation_id[:8]} to "
                        f"candidate prompt v{candidate.id[:8]} "
                        f"(score={candidate.score})"
                    )
                    # Rebuild with candidate replacing the assembled blocks
                    context_section = (
                        f"\n\n## Current Context\n\n"
                        f"**Relevant knowledge from the knowledge graph:**\n{relevant_knowledge}\n\n"
                        f"**Relevant memories:**\n{relevant_memories}"
                    )
                    result = header + "\n" + candidate.prompt_text + context_section
                else:
                    logger.debug(
                        f"A/B split: conv={conversation_id[:8]} stays on active prompt"
                    )
        except Exception as _ab_exc:
            # Never break chat for A/B bookkeeping
            logger.debug(f"A/B candidate check skipped: {_ab_exc}")

    return result


def build_introspect_messages(
    domain: str,
    instance_name: str,
    instance_description: str,
    tables_block: str,
) -> list[dict]:
    """Build system+user messages for schema introspection."""
    system = SYSTEM_PROMPT_INTROSPECT_SYSTEM.format(
        domain=domain,
        instance_name=instance_name,
        instance_description=instance_description.strip() or f"A {domain} platform.",
    )
    user = SYSTEM_PROMPT_INTROSPECT_USER.format(tables_block=tables_block)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Prompt builder functions (formerly knowledge_graph/prompt_builder.py)
# ══════════════════════════════════════════════════════════════════════════════

import json as _json_import
from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    from ai.engine.knowledge_graph.synthesis import QueryPlan, ResolvedColumn, SuggestedFilter

_PLAN_PREAMBLE = (
    "A query plan has been pre-computed from the database schema graph. "
    "Use it as your primary guide for table selection, joins, and aggregations. "
    "You may adjust column selections or add WHERE clauses based on the user's specific "
    "phrasing, but do not deviate from the join paths unless you have strong reason to. "
    "For inferred (LEFT JOIN) relationships, validate the join makes sense in context."
)


def build_sql_prompt(
    plan,
    question: str,
    dialect: str = "sqlite",
    entity_importances: dict[str, float] | None = None,
    entity_profiles: dict[str, dict] | None = None,
    golden_pairs: list[dict] | None = None,
) -> str:
    """Convert a QueryPlan into a structured prompt block for the LLM."""
    lines: list[str] = []
    lines.append(_PLAN_PREAMBLE)
    lines.append("")
    lines.append("=== QUERY PLAN ===")
    lines.append("")
    lines.append(f'Intent: {plan.intent}')
    lines.append(f'Question: "{question}"')
    lines.append("")

    # ── Target tables ─────────────────────────────────────────────────────────
    if plan.target_entities:
        lines.append("TARGET TABLES:")
        for entity in plan.target_entities:
            imp = (entity_importances or {}).get(entity)
            imp_str = f" (importance: {imp:.2f})" if imp is not None else ""
            lines.append(f"- {entity}{imp_str}")
        lines.append("")
    else:
        lines.append("TARGET TABLES: (none resolved)")
        lines.append("")

    if entity_profiles:
        count_lines = [
            f"- {entity}: {prof.get('row_count_actual', '?'):,} rows"
            for entity, prof in entity_profiles.items()
            if entity in plan.target_entities and prof
        ]
        if count_lines:
            lines.append("ROW COUNTS:")
            lines.extend(count_lines)
            lines.append("")

    if plan.join_paths:
        lines.append("JOIN PATH:")
        for path in plan.join_paths:
            for step in path.steps:
                conf_str = f"confidence: {step.confidence:.1f}"
                rel_str = "FK" if step.join_type == "fk" else "inferred"
                lines.append(
                    f"  {step.from_entity}.{step.from_column} → "
                    f"{step.to_entity}.{step.to_column} "
                    f"({rel_str}, {conf_str})"
                )
        lines.append("")

    if plan.select_columns:
        lines.append("TARGET COLUMNS:")
        for col in plan.select_columns:
            role_str = f" ({col.role})" if col.role else ""
            lines.append(f"- {col.entity}.{col.column} ({col.data_type}){role_str}")
        lines.append("")

    if plan.group_by_columns:
        lines.append("GROUP BY:")
        for col in plan.group_by_columns:
            lines.append(f"- {col.entity}.{col.column}")
        lines.append("")

    if plan.suggested_filters:
        lines.append("SUGGESTED FILTERS:")
        for f in plan.suggested_filters:
            hint = f" (hint: {f.value_hint})" if f.value_hint else ""
            lines.append(f"- {f.entity}.{f.column} {f.operator} ?{hint}")
        lines.append("")

    if plan.order_by_hint:
        lines.append(f"ORDER BY: {plan.order_by_hint}")
        lines.append("")

    lines.append(f"SQL DIALECT: {dialect}")
    lines.append("")

    if golden_pairs:
        lines.append("FEW-SHOT EXAMPLES (verified correct):")
        for gp in golden_pairs[:5]:
            lines.append(f"  Q: {gp.get('natural_language', '')}")
            lines.append(f"  SQL: {gp.get('corrected_sql', '')}")
            lines.append("")

    lines.append("=== END QUERY PLAN ===")
    return "\n".join(lines)


def build_retry_prompt(
    sql: str,
    error_message: str,
    error_hint: str,
    attempt: int = 0,
) -> str:
    """Build the repair request sent to the LLM when SQL execution fails."""
    header = f"SQL correction needed (attempt {attempt + 1}):\n" if attempt > 0 else "SQL correction needed:\n"
    return (
        f"{header}"
        f"The following SQL query failed with a database error:\n"
        f"\n```sql\n{sql}\n```\n\n"
        f"Error: {error_message}\n\n"
        f"Hint: {error_hint}\n\n"
        "Please rewrite the SQL to fix this error. "
        "Keep the original query intent unchanged — only fix what is broken. "
        "Return ONLY the corrected SQL inside a ```sql ... ``` block, nothing else."
    )


def build_fallback_prompt(context_prose: str, question: str) -> str:
    """Fallback prompt when the planner cannot produce a confident plan."""
    return (
        "The following is the relevant schema context for the database. "
        "Use it to identify the correct tables, columns, and relationships "
        "needed to answer the user's question. Infer join conditions from "
        "the relationships described.\n\n"
        f"{context_prose}"
    )
