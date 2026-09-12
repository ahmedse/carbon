"""Regression (P1-02) — the S4 critic must HARD-veto an unconfirmed mutation.

Locks in the fail-closed contract: a draft that carries a non-GET tool call
with ``confirmed`` falsy is a hard ``veto`` (rules tier), never an advisory
flag. A confirmed mutation must pass, and a ``dry_run`` preview must never
hard-block (previews are informational). The rules-only fallback used when the
LLM critic is disabled or errors must also veto.

See ``test_retrieval_grounding.py`` for the DraftResult/RetrievalResult
construction pattern.
"""

from __future__ import annotations

import asyncio

from ai.engine.cognition.turn.critic import CriticWitness, _rules_only_verdict
from ai.engine.cognition.turn.witnesses import DraftResult, RetrievalResult


def _draft(confirmed: bool) -> DraftResult:
    """A draft proposing a state-changing (non-GET) tool call."""
    return DraftResult(
        text="Creating the new table now.",
        tool_calls=[
            {
                "id": "call_1",
                "method": "POST",
                "confirmed": confirmed,
                "function": {"name": "create_table", "arguments": "{}"},
            }
        ],
        claimed_citations=[],
    )


def _review(draft: DraftResult, *, dry_run: bool = False):
    critic = CriticWitness()
    retrieval = RetrievalResult(knowledge_chunks=[], memory_chunks=[])
    return asyncio.run(
        critic.review(
            draft,
            retrieval,
            dry_run=dry_run,
            enable_llm_critic=False,
        )
    )


# ── Rules-tier hard veto ────────────────────────────────────────────────────


def test_unconfirmed_mutation_is_hard_veto():
    """non-GET + confirmed falsy → hard veto, never advisory."""
    verdict = _review(_draft(confirmed=False))
    assert verdict.verdict == "veto"
    assert "unconfirmed_mutation" in verdict.flags
    assert verdict.veto_reason


def test_confirmed_mutation_is_not_vetoed():
    """non-GET + confirmed=True → the mutation is allowed through."""
    verdict = _review(_draft(confirmed=True))
    assert verdict.verdict != "veto"
    assert "unconfirmed_mutation" not in verdict.flags


def test_dry_run_preview_unconfirmed_mutation_is_not_vetoed():
    """dry_run=True → a preview must not hard-block."""
    verdict = _review(_draft(confirmed=False), dry_run=True)
    assert verdict.verdict != "veto"
    assert "unconfirmed_mutation" not in verdict.flags


# ── Defense-in-depth: rules-only fallback ───────────────────────────────────


def test_rules_only_verdict_vetoes_unconfirmed_mutation():
    """The LLM-critic fallback must also fail closed."""
    verdict = _rules_only_verdict(["unconfirmed_mutation"])
    assert verdict.verdict == "veto"
    assert "unconfirmed_mutation" in verdict.flags
