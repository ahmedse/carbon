"""Tiered, budgeted context assembly for AI conversations.

Sprint 15 — replaces the prior "send ALL history every turn" behaviour with a
tiered assembler that caps verbatim history and reserves budget for the engine's
knowledge-graph (T3) and long-term memory (T4) retrieval seams.

Token estimates are approximate: ``len(text) // 4`` (~4 chars/token).
"""

from __future__ import annotations

from typing import Any


def _estimate_tokens(text: str) -> int:
    """Approximate token count at ~4 characters per token."""
    return max(0, len(text or "") // 4)


def assemble_context(
    conversation,
    messages,
    scope,
    *,
    recent_turns: int = 8,
    summary_budget: int = 1500,
    retrieval_budget: int = 2000,
    memory_budget: int = 1000,
) -> dict[str, Any]:
    """Assemble tiered, budgeted context for a conversation turn.

    Tier rules:
      * T2 history  — the most recent ``recent_turns`` messages verbatim;
                      anything older is NOT sent.
      * T2b summary — prepend ``conversation.summary`` (as a system note) when
                      non-empty.
      * T3 retrieval — engine knowledge-graph retrieval (stubbed this sprint).
      * T4 memory    — engine long-term memory retrieval (stubbed this sprint).

    ``scope`` and ``summary_budget`` are accepted for the (future) T3/T4
    retrieval + summary compaction seams but are unused this sprint — no
    cross-conversation or cross-app reads ever happen here.

    Returns ``{"messages": [...], "budget": {tier: token_estimate}}``.  The
    ``messages`` list is the verbatim history actually sent to the provider; the
    ``budget`` dict records token telemetry for every tier (T3/T4 reserve their
    configured budgets even though no engine call is made yet).
    """
    tiered: list[dict[str, Any]] = []

    # T2b — rolling compaction summary as the leading system note.
    summary = getattr(conversation, "summary", "") or ""
    if summary:
        tiered.append(
            {
                "role": "system",
                "content": f"[Summary]\n{summary}",
                "timestamp": None,
            }
        )

    # T2 — most recent turns verbatim; anything older is NOT sent.
    recent = list(messages[-recent_turns:])
    for message in recent:
        created_at = message.get("created_at")
        tiered.append(
            {
                "role": message.get("role"),
                "content": message.get("content"),
                "timestamp": (
                    created_at.isoformat() if created_at is not None else None
                ),
            }
        )

    # T3 + T4 — engine retrieval seams (stubbed this sprint).
    # TODO(Sprint 16+): wire KnowledgeGraphStore (engine/knowledge_graph/store.py)
    # and LongTermMemory.get_relevant_facts (engine/memory/long_term.py), scoped to
    # this conversation's own instance/app_identifier, into the outgoing context.
    # No engine calls are fabricated here — both tiers return empty lists but
    # still reserve their configured token budgets below.

    budget = {
        "T2_history": sum(_estimate_tokens(m["content"]) for m in recent),
        "T2b_summary": _estimate_tokens(summary),
        "T3_retrieval": retrieval_budget,
        "T4_memory": memory_budget,
    }

    return {
        "messages": tiered,
        "budget": budget,
    }
