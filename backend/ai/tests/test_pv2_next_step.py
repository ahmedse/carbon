"""L4 — next ESS step from ConversationState (0 LLM)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ai.engine.cognition.state_store import ConversationState, upsert_active_plan
from ai.engine.cognition.turn.next_step import (
    is_next_step_utterance,
    next_step_action,
    render_next_step_offer,
    should_offer_next_step,
)
from ai.engine.cognition.turn.plan_status import render_plan_status


def test_next_verb_by_plan_status():
    state = ConversationState()
    upsert_active_plan(state, plan_id="p1", status="handoff_ready", title="annual leave",
                       slots={"leave_type": "annual"})
    assert next_step_action(state) == "submit_in_agent"
    text = render_next_step_offer(state, "what next")
    assert text and "Agent" in text and "submit" in text.lower()
    assert "Chat will not send" in text

    upsert_active_plan(state, plan_id="p1", status="pending_approval", title="annual leave")
    assert next_step_action(state) == "approve_in_agent"
    assert "Approve" in (render_next_step_offer(state, "ok") or "")

    upsert_active_plan(state, plan_id="p1", status="paused", title="annual leave")
    assert next_step_action(state) == "confirm_in_agent"

    upsert_active_plan(state, plan_id="p1", status="approved", title="annual leave")
    assert next_step_action(state) == "run_in_agent"

    upsert_active_plan(state, plan_id="p1", status="completed", title="annual leave")
    assert next_step_action(state) is None
    assert render_next_step_offer(state, "what next") is None

    slots_only = ConversationState()
    slots_only.slots = {"leave_type": "annual", "start_date": "2027-08-31"}
    assert next_step_action(slots_only) == "submit_in_agent"


def test_utterance_gate_skips_new_write_and_payroll():
    state = ConversationState()
    upsert_active_plan(
        state, status="pending_approval", title="personal loan",
        slots={"loan_type": "personal", "principal": 551},
    )
    assert is_next_step_utterance("what next")
    assert is_next_step_utterance("ok")
    assert is_next_step_utterance("ماذا بعد؟")
    assert not is_next_step_utterance("what was my net pay")
    assert should_offer_next_step("what next", state)
    assert not should_offer_next_step("I want to request a loan", state)
    assert not should_offer_next_step("what next", ConversationState())


def test_plan_status_appends_next_verb():
    state = ConversationState()
    upsert_active_plan(
        state,
        plan_id="p1",
        status="pending_approval",
        title="emergency loan",
        slots={"loan_type": "emergency", "amount": 5000},
    )
    text = render_plan_status(state, "What is the status of my request?")
    assert "5000" in text
    assert "Next: open Agent and Approve" in text


@pytest.mark.asyncio
async def test_runner_next_step_zero_llm():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    from ai.engine.cognition.turn.witnesses import TurnLedger

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    state = ConversationState()
    upsert_active_plan(
        state,
        plan_id="p1",
        status="paused",
        title="annual leave",
        slots={"leave_type": "annual"},
    )
    ctx = SimpleNamespace(state=state)
    ledger = TurnLedger()
    with patch(
        "ai.engine.cognition.notifier.broadcast_run_event",
        new_callable=AsyncMock,
    ):
        pair = await runner._try_next_step_offer(  # noqa: SLF001
            user_message="what next",
            state_ctx=ctx,
            ledger=ledger,
            meter=SimpleNamespace(),
            turn_id="t1",
            instance_id="nibras",
            t0=0.0,
        )
    assert pair is not None
    response, out = pair
    assert out.total_llm_calls == 0
    assert "confirm" in (response.text or "").lower()
    assert "Agent" in (response.text or "")
