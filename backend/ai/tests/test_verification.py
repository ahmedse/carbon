"""Pulse v2 Phase 7 — Post-result verification."""
import json

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def test_verification_passes_correct_claim():
    """VerificationWitness must return passed=True when the answer's numbers
    match the tool results."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    fake_response = {
        "content": json.dumps({
            "passed": True,
            "unsupported_claims": [],
            "verified_claims": ["2.5 kg CO2e/kWh"],
            "corrected_text": None,
        }),
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "test",
    }
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value=fake_response),
    ):
        result = await vw.verify(
            answer="The electricity factor is 2.5 kg CO2e/kWh.",
            tool_results=[{"tool_name": "get_entity_details", "result": {"factor": 2.5}}],
            user_message="What is the electricity factor?",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is True
    assert "2.5 kg CO2e/kWh" in result.verified_claims


async def test_verification_corrects_wrong_number():
    """VerificationWitness must return passed=False and corrected_text when the
    answer contains a number that contradicts the tool result."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    fake_response = {
        "content": json.dumps({
            "passed": False,
            "unsupported_claims": ["2.3 kg CO2e/kWh"],
            "verified_claims": [],
            "corrected_text": "The electricity factor is 2.5 kg CO2e/kWh, as configured.",
        }),
        "input_tokens": 100,
        "output_tokens": 80,
        "model": "test",
    }
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value=fake_response),
    ):
        result = await vw.verify(
            answer="The electricity factor is 2.3 kg CO2e/kWh.",  # wrong number
            tool_results=[{"tool_name": "get_entity_details", "result": {"factor": 2.5}}],
            user_message="What is the electricity factor?",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is False
    assert "2.3 kg CO2e/kWh" in result.unsupported_claims
    assert result.corrected_text is not None
    assert "2.5" in result.corrected_text


async def test_verification_returns_passed_on_llm_failure():
    """VerificationWitness must return passed=True (fail-open) when the
    verification LLM call fails — never block the response."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(side_effect=RuntimeError("LLM unavailable")),
    ):
        result = await vw.verify(
            answer="Some answer",
            tool_results=[{"tool_name": "get_entity_details", "result": {}}],
            user_message="test",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is True


async def test_verification_returns_passed_when_no_answer_or_results():
    """No answer or no tool results → passed=True with zero LLM calls."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value={"content": "{}", "model": "test"}),
    ) as mock_route:
        result = await vw.verify(
            answer="",
            tool_results=[],
            user_message="test",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is True
    mock_route.assert_not_awaited()
