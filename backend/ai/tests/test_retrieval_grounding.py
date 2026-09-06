"""Regression tests for the S4 critic's citation-grounding check.

Locks in the fix for a live-E2E failure: an empty retrieval result was being
surfaced as a *non-empty* ``knowledge_chunks`` (via the "No knowledge loaded
yet." placeholder), so the critic's ``has_retrieval_results`` check always
returned True and false-flagged ``ungrounded_claim`` on perfectly valid
general-knowledge answers. The live LLM critic then vetoed the answer and the
turn surfaced "uncertain" instead of confident.

Contract under test:
  * RetrievalWitness.retrieve emits an EMPTY ``knowledge_chunks`` list when
    nothing is found (the placeholder is prompt-fodder for the draft, not a
    grounded chunk).
  * The critic flags ``ungrounded_claim`` ONLY when there is real retrieval
    evidence the draft failed to cite — never when retrieval found nothing.
"""

from __future__ import annotations

import asyncio

from ai.engine.cognition.turn.critic import CriticWitness
from ai.engine.cognition.turn.retrieve import RetrievalWitness
from ai.engine.cognition.turn.witnesses import DraftResult, RetrievalResult


# ── 1. RetrievalWitness emits empty chunks on empty retrieval ─────────────


class _EmptyStore:
    """Knowledge store that finds nothing (lexical/vector both empty)."""

    async def search(self, instance_id, query, top_k=10):
        return []


class _PopulatedStore:
    """Knowledge store that finds a couple of entities."""

    async def search(self, instance_id, query, top_k=10):
        return [
            {"name": "Scope 1 Emissions", "semantic_description": "Direct GHG emissions from owned sources."},
            {"name": "Scope 2 Emissions", "semantic_description": "Indirect emissions from purchased electricity."},
        ]


def test_retrieve_empty_knowledge_emits_empty_chunks():
    witness = RetrievalWitness(knowledge_store=_EmptyStore())
    result = asyncio.run(
        witness.retrieve("carbon", "conv-1", "What is Scope 1 versus Scope 2?")
    )
    # The placeholder must NOT leak into knowledge_chunks — empty retrieval
    # means empty chunks, so the critic sees "no evidence" rather than a
    # pseudo-chunk to ground against.
    assert result.knowledge_chunks == []


def test_retrieve_populated_knowledge_emits_chunks():
    witness = RetrievalWitness(knowledge_store=_PopulatedStore())
    result = asyncio.run(
        witness.retrieve("carbon", "conv-1", "What is Scope 1 versus Scope 2?")
    )
    assert result.knowledge_chunks
    assert any("Scope 1" in c["content"] for c in result.knowledge_chunks)


# ── 2. Critic flags ungrounded_claim ONLY when evidence exists ─────────────


def _review(draft_text, knowledge_chunks):
    critic = CriticWitness()
    draft = DraftResult(text=draft_text, claimed_citations=[])
    retrieval = RetrievalResult(
        knowledge_chunks=knowledge_chunks,
        memory_chunks=[],
    )
    return asyncio.run(
        critic.review(draft, retrieval, enable_llm_critic=False)
    )


def test_critic_no_flag_when_retrieval_empty():
    """Empty retrieval → no grounding flag, clean pass (general knowledge)."""
    verdict = _review(
        "Scope 1 covers direct emissions; Scope 2 covers purchased energy.",
        knowledge_chunks=[],
    )
    assert verdict.verdict == "pass"
    assert "ungrounded_claim" not in verdict.flags


def test_critic_flags_when_evidence_uncited():
    """Real retrieval evidence + no citations → advisory ungrounded_claim flag."""
    verdict = _review(
        "Scope 1 covers direct emissions.",
        knowledge_chunks=[{"type": "text", "content": "Scope 1 Emissions: direct GHG emissions."}],
    )
    assert "ungrounded_claim" in verdict.flags
    # Advisory only: rules-only path returns pass_with_flag, never a veto.
    assert verdict.verdict == "pass_with_flag"
