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


async def test_observe_skips_llm_for_empty_payslips():
    """Empty ESS payslips are stated in copy — observe must not spend a draft."""
    loop = ReActLoop()
    dw = _FakeDraftWitness("should not invent 4500")
    tool_output = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_payslips"},
        "result": json.dumps({"status_code": 200, "data": {"count": 0, "results": []}}),
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="What was my net pay last month?",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=dw,
    )
    assert out is not None
    assert out.needs_followup is False
    assert dw.call_kwargs is None
    assert "4500" not in (out.answer or "") and "4,500" not in (out.answer or "")
    assert "payslip" in (out.answer or "").lower()


async def test_observe_empty_leave_history_not_zero_balance():
    """Empty list_my_leave must not invent remaining=0 for a balance ask."""
    loop = ReActLoop()
    dw = _FakeDraftWitness("remaining 0 / used 0 / pending 0")
    tool_output = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_leave"},
        "result": json.dumps({"status_code": 200, "data": {"count": 0, "results": []}}),
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="عن الإجازات",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info={"language": "ar"},
        dw=dw,
    )
    assert out is not None
    assert dw.call_kwargs is None
    text = out.answer or ""
    assert "المتبقي 0" not in text
    assert "remaining 0" not in text.lower()
    assert "رصيد" in text or "طلبات" in text


async def test_observe_skips_llm_for_committed_payslips():
    """Committed identity is restated from the tool — observe must not draft."""
    loop = ReActLoop()
    dw = _FakeDraftWitness("should not invent 3700")
    tool_output = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "list_my_payslips"},
        "result": json.dumps({
            "status_code": 200,
            "data": {
                "count": 4,
                "results": [
                    {"line_type": {"code": "gross"}, "amount": "6500.000"},
                    {"line_type": {"code": "gosi"}, "amount": "1200.000"},
                    {"line_type": {"code": "loan_installment"}, "amount": "800.000"},
                    {"line_type": {"code": "net"}, "amount": "4500.000"},
                ],
            },
        }),
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="What was my net pay last month?",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=dw,
    )
    assert out is not None
    assert dw.call_kwargs is None
    assert "4500" in (out.answer or "")
    assert "3700" not in (out.answer or "")


async def test_observe_skips_llm_for_profile():
    loop = ReActLoop()
    dw = _FakeDraftWitness("should not invent Engineering")
    tool_output = {
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "get_my_profile"},
        "result": json.dumps({
            "status_code": 200,
            "data": {
                "employee_no": "1067",
                "org_unit": {"id": 6, "name": "Coiled Tubing"},
                "manager": {"id": 3, "name": "Mohammad Bolto Ali"},
            },
        }),
    }
    out = await loop._observe(
        step=_step(),
        tool_output=tool_output,
        user_message="What department am I in?",
        system_prompt="sys",
        conversation_history=None,
        instance_config=None,
        user_info=None,
        dw=dw,
    )
    assert out is not None
    assert dw.call_kwargs is None
    assert "Coiled Tubing" in (out.answer or "")
    assert "Engineering" not in (out.answer or "")


async def test_pulse_loop_settings_exist():
    """PULSE_LOOP_* settings expose the Phase 1 defaults."""
    from ai.engine.core.config import Settings

    settings = Settings()
    assert settings.PULSE_LOOP_ENABLED is True
    assert settings.PULSE_LOOP_MAX_STEPS == 6
    assert settings.PULSE_LOOP_MAX_TOKENS == 8000
