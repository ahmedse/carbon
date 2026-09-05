"""Phase 1 — Pulse v2 adaptive ReAct loop.

Unit tests for ``ReActLoop._observe`` (the observation stage that synthesizes a
grounded answer from a successfully executed tool result) and for the
``PULSE_LOOP_*`` settings defaults. Pure functions + a fake draft witness — no
DB, no network, no LLM.
"""
from __future__ import annotations

import json

import pytest

from ai.engine.cognition.plan.loop import ReActLoop
from ai.engine.cognition.plan.planner import PlanStep
from ai.engine.cognition.turn.witnesses import DraftResult

pytestmark = pytest.mark.asyncio


class _FakeDraftWitness:
    """Records draft() kwargs and returns a canned DraftResult."""

    def __init__(self, text: str = ""):
        self._text = text
        self.call_kwargs: dict | None = None

    async def draft(self, **kwargs) -> DraftResult:
        self.call_kwargs = kwargs
        return DraftResult(text=self._text)


def _step() -> PlanStep:
    return PlanStep(step_id=0, intent="test")


async def test_observe_returns_none_for_confirmation_response():
    """A confirmation proposal is owned by the consent gate — never synthesized."""
    loop = ReActLoop()
    dw = _FakeDraftWitness("should not be used")
    tool_output = {
        "tool_name": "learn_fact",
        "result": json.dumps({"requires_confirmation": True}),
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="remember my preference",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=dw,
    )
    assert out is None
    assert dw.call_kwargs is None  # draft never called


async def test_observe_calls_draft_with_tool_result_prompt():
    """A resolved tool result is synthesized into a grounded answer via draft."""
    loop = ReActLoop()
    dw = _FakeDraftWitness("Cairo is the capital of Egypt.")
    tool_output = {
        "tool_name": "search_knowledge",
        "result": json.dumps({"status": "resolved", "data": {"city": "Cairo"}}),
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="what is the capital of Egypt?",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=dw,
    )
    assert out.answer == "Cairo is the capital of Egypt."
    assert out.needs_followup is False
    assert dw.call_kwargs is not None
    assert dw.call_kwargs["tools"] is None
    assert "TOOL RESULT" in dw.call_kwargs["user_message"]
    assert "search_knowledge" in dw.call_kwargs["user_message"]
    assert "capital of Egypt" in dw.call_kwargs["user_message"]
    assert dw.call_kwargs["instance_id"] == ""
    assert dw.call_kwargs["conversation_id"] == ""


async def test_observe_returns_none_for_no_match():
    """A no_match payload is owned by escalation/clarification — never synthesized."""
    loop = ReActLoop()
    dw = _FakeDraftWitness("should not be used")
    tool_output = {
        "tool_name": "get_entity_details",
        "result": {"status": "no_match"},
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="show me entity X",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=dw,
    )
    assert out is None
    assert dw.call_kwargs is None


async def test_pulse_loop_settings_exist():
    """PULSE_LOOP_* settings expose the Phase 1 defaults."""
    from ai.engine.core.config import Settings

    settings = Settings()
    assert settings.PULSE_LOOP_ENABLED is True
    assert settings.PULSE_LOOP_MAX_STEPS == 6
    assert settings.PULSE_LOOP_MAX_TOKENS == 8000
