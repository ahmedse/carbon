"""Phase 2 — Evidence-need detection, no zone vetoes."""
import pathlib

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio


async def test_intent_resolver_sets_needs_live_evidence_for_weather():
    """IntentResolver must set needs_live_evidence=True for current weather
    queries even when the zone is mislabelled."""
    from ai.engine.cognition.turn.intent import IntentResolver

    resolver = IntentResolver()
    fake_llm_response = {
        "content": '{"action":"answer","zone":"concept","intent":"current weather",'
                   '"needs_live_evidence":true,"delivery":"explain",'
                   '"candidates":[],"confidence":0.9}',
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "test",
    }
    with patch("ai.engine.llm.router.route_chat", AsyncMock(return_value=fake_llm_response)):
        result = await resolver.resolve(
            user_message="what is the weather in cairo today",
            api_catalog=[{"name": "list_emission_factors", "method": "GET",
                          "description": "List emission factors"}],
            conversation_history=None,
            instance_id="i1",
            conversation_id="c1",
            db=None,
        )

    assert result is not None
    assert result.needs_live_evidence is True


async def test_weather_tool_description_mentions_weather():
    """web_research description must mention 'weather' so the LLM selects it
    for weather queries without a zone veto."""
    from ai.engine.agent.tools import get_tool_definitions
    defs = get_tool_definitions()
    wr = next((d for d in defs if d.get("function", {}).get("name") == "web_research"), None)
    assert wr is not None, "web_research tool not found in definitions"
    desc = wr["function"]["description"]
    assert "weather" in desc.lower(), f"'weather' not in web_research description: {desc}"


def test_zone_concept_does_not_block_tool_call():
    """The single-pass path must no longer inject a 'no platform tool needed'
    veto for concept/general zones. We assert the veto string is gone from the
    runner source, which is the literal Phase-2 acceptance requirement."""
    runner_path = pathlib.Path(__file__).resolve().parent.parent / "engine" / "cognition" / "turn" / "runner.py"
    source = runner_path.read_text()
    assert "No platform tool call is needed" not in source
    assert "Answer this question from your knowledge" not in source
