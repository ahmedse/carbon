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


async def test_verification_fails_closed_on_llm_failure():
    """VerificationWitness must fail closed — passed=False with an error — when
    the verification LLM call fails, so the ledger shows it was not verified."""
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

    assert result.passed is False
    assert result.error


async def test_verification_fails_closed_on_unparseable_json():
    """VerificationWitness must fail closed — passed=False with an 'unparseable'
    error — when the verification LLM returns non-JSON content."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value={
            "content": "not json",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "test",
        }),
    ):
        result = await vw.verify(
            answer="Some answer",
            tool_results=[{"tool_name": "get_entity_details", "result": {}}],
            user_message="test",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is False
    assert "unparseable" in result.error


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


# ── Deterministic no-data contradiction guard ────────────────────────────────

def test_detect_no_data_contradiction_fires_on_summary():
    """Answer claims 'no data' while the summary returned calculations → caught."""
    from ai.engine.cognition.turn.verify import detect_no_data_contradiction

    summary = {"status_code": 200, "data": {
        "total_calculations": 115,
        "by_scope": [{"scope": 1, "count": 39}, {"scope": 2, "count": 58}],
    }}
    reason = detect_no_data_contradiction(
        "No carbon emissions data is available for AASTMT in 2026.",
        [{"tool_name": "call_host_api", "result": summary}],
    )
    assert reason is not None
    assert "call_host_api" in reason


def test_detect_no_data_contradiction_silent_when_data_reported():
    """A real data answer must NOT trip the guard."""
    from ai.engine.cognition.turn.verify import detect_no_data_contradiction

    summary = {"status_code": 200, "data": {"total_calculations": 115}}
    reason = detect_no_data_contradiction(
        "Total emissions across all scopes: 10.3 million kg CO2e from 115 calculations.",
        [{"tool_name": "call_host_api", "result": summary}],
    )
    assert reason is None


def test_detect_no_data_contradiction_silent_when_truly_empty():
    """A 'no data' answer over an empty result is correct — no contradiction."""
    from ai.engine.cognition.turn.verify import detect_no_data_contradiction

    empty = {"status_code": 200, "data": {"total_calculations": 0, "by_scope": []}}
    reason = detect_no_data_contradiction(
        "There are no records for this period.",
        [{"tool_name": "call_host_api", "result": empty}],
    )
    assert reason is None


async def test_verify_fails_closed_on_deterministic_contradiction_without_llm():
    """The deterministic guard fires BEFORE the normal fact-check LLM call,
    and also calls the correction LLM (not the verify LLM) to get a fix."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    summary = {"status_code": 200, "data": {"total_calculations": 18, "by_module": [{"m": 1}]}}
    # route_chat is called ONCE (for correction), not the original verify call.
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value={"content": "AASTMT had 18 calculations.", "model": "test"}),
    ) as mock_route:
        result = await vw.verify(
            answer="No emissions data is available for 2026.",
            tool_results=[{"tool_name": "call_host_api", "result": summary}],
            user_message="emissions in 2026",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is False
    assert "call_host_api" in result.error
    # correction LLM was called once (for the re-synthesis)
    mock_route.assert_awaited_once()
    assert result.corrected_text == "AASTMT had 18 calculations."


async def test_correct_no_data_falls_back_when_llm_returns_empty():
    """When the correction LLM returns empty content, the deterministic
    fallback renders the real tool data instead of leaving 'no data'."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    summary = {"status_code": 200, "data": {
        "total_calculations": 115,
        "by_scope": {"1": {"count": 39, "total_co2e_kg": 1000.0}},
        "by_module": [{"module_name": "Stationary", "count": 76, "total_co2e_kg": 900.0}],
    }}
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value={"content": "", "model": "test"}),
    ):
        result = await vw.verify(
            answer="No emissions data is available for 2026.",
            tool_results=[{"tool_name": "call_host_api", "result": summary}],
            user_message="emissions in 2026",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is False
    assert result.corrected_text is not None
    assert "115" in result.corrected_text
    assert "Stationary" in result.corrected_text


async def test_correct_no_data_falls_back_when_llm_reasserts_no_data():
    """When the correction LLM hallucinates 'no data' again, the deterministic
    fallback replaces it with real numbers."""
    from ai.engine.cognition.turn.verify import VerificationWitness

    vw = VerificationWitness()
    summary = {"status_code": 200, "data": {"total_calculations": 42}}
    with patch(
        "ai.engine.cognition.turn.verify.route_chat",
        AsyncMock(return_value={"content": "There are no records available.", "model": "test"}),
    ):
        result = await vw.verify(
            answer="No emissions data is available for 2026.",
            tool_results=[{"tool_name": "call_host_api", "result": summary}],
            user_message="emissions in 2026",
            instance_id="i1",
            conversation_id="c1",
        )

    assert result.passed is False
    assert result.corrected_text is not None
    assert "42" in result.corrected_text
    assert "no data" not in result.corrected_text.lower()
    assert "no records" not in result.corrected_text.lower()


def test_result_has_data_parses_json_string():
    """The real pipeline serializes results to JSON strings; the guard must
    parse them so a non-empty count is recognised and an empty one is not."""
    from ai.engine.cognition.turn.verify import _result_has_data

    assert _result_has_data('{"status_code": 200, "data": {"total_calculations": 115}}') is True
    assert _result_has_data('{"status_code": 200, "data": {"total_calculations": 0, "by_scope": {}, "by_module": []}}') is False


def test_deterministic_correction_renders_json_string_result():
    """The deterministic fallback must render real numbers from a JSON-string
    tool result (the shape the pipeline actually produces)."""
    from ai.engine.cognition.turn.verify import _deterministic_correction

    summary = '{"status_code": 200, "data": {"total_calculations": 115, ' \
        '"by_scope": {"1": {"count": 39, "total_co2e_kg": 1000.0}}, ' \
        '"by_module": [{"module_name": "Stationary", "count": 76, "total_co2e_kg": 900.0}]}}'
    out = _deterministic_correction([{"tool_name": "call_host_api", "result": summary}])
    assert out is not None
    assert "115" in out
    assert "Stationary" in out
    assert "1,000.00" in out
