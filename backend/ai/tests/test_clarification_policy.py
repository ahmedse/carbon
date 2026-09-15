"""Pure tests for the clarification policy (Pulse Phase 4 — P4-06).

The clarification policy is a deterministic, LLM-free gate. These tests
exercise the pure decision function directly and verify that
``DraftWitness.draft`` short-circuits (never invoking the LLM) when the
policy says to ask, while still proceeding normally when the case is clear.
"""
import asyncio

import pytest

from ai.engine.cognition.turn.clarify import (
    CLARIFICATION_REASONS,
    ClarificationDecision,
    evaluate_clarification,
)
from ai.engine.cognition.turn.draft import DraftWitness


def test_clarification_reasons_constant():
    assert CLARIFICATION_REASONS == (
        "ambiguous_identity",
        "missing_evidence",
        "unclear_authority",
    )


def test_ambiguous_identity_zero_candidates():
    decision = evaluate_clarification(
        object_candidates=0,
        evidence_available=True,
        evidence_required=False,
        authority_granted=frozenset({"*"}),
        authority_required=None,
    )
    assert decision.needs_clarification is True
    assert decision.reason == "ambiguous_identity"
    assert decision.question


def test_ambiguous_identity_multiple_candidates():
    decision = evaluate_clarification(
        object_candidates=2,
        evidence_available=True,
        evidence_required=False,
        authority_granted=frozenset({"*"}),
        authority_required=None,
    )
    assert decision.needs_clarification is True
    assert decision.reason == "ambiguous_identity"
    assert decision.question


def test_missing_evidence():
    decision = evaluate_clarification(
        object_candidates=1,
        evidence_available=False,
        evidence_required=True,
        authority_granted=frozenset({"*"}),
        authority_required=None,
    )
    assert decision.needs_clarification is True
    assert decision.reason == "missing_evidence"


def test_missing_evidence_not_required_does_not_clarify():
    decision = evaluate_clarification(
        object_candidates=1,
        evidence_available=False,
        evidence_required=False,
        authority_granted=frozenset({"*"}),
        authority_required=None,
    )
    assert decision.needs_clarification is False
    assert decision.reason is None


def test_unclear_authority():
    decision = evaluate_clarification(
        object_candidates=1,
        evidence_available=True,
        evidence_required=False,
        authority_granted=frozenset({"read_data"}),
        authority_required="approve_plan",
    )
    assert decision.needs_clarification is True
    assert decision.reason == "unclear_authority"
    # "never guess authority" contract: must NOT have returned a clear decision.
    assert decision.reason != "clear"
    assert decision.needs_clarification is not False


def test_clear_case_no_clarification():
    decision = evaluate_clarification(
        object_candidates=1,
        evidence_available=True,
        evidence_required=False,
        authority_granted=frozenset({"*"}),
        authority_required=None,
    )
    assert decision.needs_clarification is False
    assert decision.reason is None
    assert decision.question == ""


def test_superuser_wildcard_authority_is_clear():
    decision = evaluate_clarification(
        object_candidates=1,
        evidence_available=True,
        evidence_required=False,
        authority_granted=frozenset({"*"}),
        authority_required="anything",
    )
    assert decision.needs_clarification is False
    assert decision.reason is None


def test_draft_short_circuits_without_llm_call(monkeypatch):
    def _boom(**kwargs):
        raise AssertionError("route_chat must not be called")

    monkeypatch.setattr("ai.engine.cognition.turn.draft.route_chat", _boom)

    witness = DraftWitness()

    async def _run():
        return await witness.draft(
            instance_id="i",
            conversation_id="c",
            user_message="x",
            system_prompt="sys",
            clarify_inputs={"object_candidates": 2},
        )

    result = asyncio.run(_run())
    assert result.model_used == "clarification_policy"
    assert result.tool_calls == []
    assert result.tokens_used == 0
    assert result.text


def test_draft_proceeds_when_clear(monkeypatch):
    calls = []

    async def _fake_route_chat(**kwargs):
        calls.append(kwargs)
        return {
            "content": "ok",
            "tool_calls": [],
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "fake",
        }

    monkeypatch.setattr(
        "ai.engine.cognition.turn.draft.route_chat", _fake_route_chat
    )

    witness = DraftWitness()

    async def _run():
        return await witness.draft(
            instance_id="i",
            conversation_id="c",
            user_message="x",
            system_prompt="sys",
            clarify_inputs={"object_candidates": 1},
        )

    result = asyncio.run(_run())
    assert result.model_used == "fake"
    assert result.text == "ok"
    assert len(calls) == 1
