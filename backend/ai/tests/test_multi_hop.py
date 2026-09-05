"""Pulse v2 Phase 5 — multi-hop reasoning.

Covers the observation decision (follow-up vs. final answer), the read-only
allow-list that blocks mutation tools from auto-chaining, and the max-steps
budget that bounds the number of injected follow-up steps.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai.engine.cognition.plan.loop import (
    ObservationResult,
    ReActLoop,
    StepResult,
    _ALLOWED_FOLLOWUP_TOOLS,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_observe_returns_followup_when_data_insufficient():
    """_observe must detect a partial result and request a read-only follow-up."""
    loop = ReActLoop()

    fake_llm_response = json.dumps({
        "answer": "The platform factor is 2.5 kg CO2e/kWh.",
        "needs_followup": True,
        "followup_tool": "web_research",
        "followup_args": {"query": "latest IPCC grid electricity emission factor"},
    })
    mock_dw = AsyncMock()
    mock_dw.draft.return_value = MagicMock(text=fake_llm_response, tool_calls=[])

    result = await loop._observe(
        step=MagicMock(step_id=0),
        tool_output={
            "tool_name": "get_entity_details",
            "result": {"name": "Electricity", "factor": 2.5},
        },
        user_message="Compare our factor with the latest IPCC value",
        system_prompt="",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=mock_dw,
    )

    assert isinstance(result, ObservationResult)
    assert result.needs_followup is True
    assert result.followup_tool == "web_research"
    assert result.answer == "The platform factor is 2.5 kg CO2e/kWh."


def test_followup_mutation_tool_is_blocked():
    """Mutation tools must NEVER appear in the read-only follow-up allow-list."""
    assert "create_dq_rule" not in _ALLOWED_FOLLOWUP_TOOLS
    assert "plan_task" not in _ALLOWED_FOLLOWUP_TOOLS
    assert "learn_fact" not in _ALLOWED_FOLLOWUP_TOOLS
    assert "export_document" not in _ALLOWED_FOLLOWUP_TOOLS
    # Read-only candidates ARE allowed.
    assert "web_research" in _ALLOWED_FOLLOWUP_TOOLS


def test_multihop_stops_at_max_steps():
    """The follow-up budget is bounded — used == max rejects, below allows."""
    loop = ReActLoop()
    step_result = StepResult(
        step_id=0,
        intent="compare factor",
        followup=ObservationResult(
            needs_followup=True,
            followup_tool="web_research",
            followup_args={"query": "latest IPCC factor"},
        ),
    )

    # Below the budget → allowed.
    assert loop._should_inject_followup(step_result, 1, 2) is True
    # At the budget (used == max) → rejected.
    assert loop._should_inject_followup(step_result, 2, 2) is False
    # Over the budget → rejected.
    assert loop._should_inject_followup(step_result, 3, 2) is False


def test_multihop_rejects_mutation_tool_regardless_of_budget():
    """A follow-up naming a mutation tool is rejected even with budget left."""
    loop = ReActLoop()
    bad = StepResult(
        step_id=0,
        intent="write rule",
        followup=ObservationResult(
            needs_followup=True,
            followup_tool="create_dq_rule",
            followup_args={"rule": "x"},
        ),
    )
    assert loop._should_inject_followup(bad, 0, 10) is False
