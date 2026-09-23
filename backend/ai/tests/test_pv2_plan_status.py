"""PV2-5B — active_plans write-back + Chat plan_status (0 LLM)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from accounts.models import User
from ai.engine.cognition.state_store import (
    ConversationState,
    upsert_active_plan,
)
from ai.engine.cognition.turn.plan_status import (
    can_answer_plan_status,
    is_plan_status_utterance,
    render_plan_status,
)
from ai.models.core import ConversationContextRecord, Run
from ai.plans_service import (
    PLAN_INSTANCE_ID,
    STATUS_PENDING_APPROVAL,
    PlansService,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(username="pv2-5b", password="secret123")


def test_status_utterance_not_new_write():
    assert is_plan_status_utterance("What is the status of my request?")
    assert is_plan_status_utterance("what happened to my loan request?")
    assert is_plan_status_utterance("ما حالة الطلب؟")
    assert not is_plan_status_utterance("I want to request a loan")
    assert not is_plan_status_utterance("أريد قرض طارئ")


def test_render_from_handoff_slots_mentions_review_honestly():
    state = ConversationState()
    upsert_active_plan(
        state,
        status="handoff_ready",
        title="emergency loan",
        slots={"loan_type": "emergency", "amount": 5000, "principal": 5000},
    )
    text = render_plan_status(state, "What is the status of my request?")
    assert "emergency" in text.lower()
    assert "5000" in text
    assert "review" in text.lower()
    assert can_answer_plan_status(state)


def test_render_pending_approval_is_review():
    state = ConversationState()
    upsert_active_plan(
        state,
        plan_id="p1",
        status="pending_approval",
        title="emergency loan",
        slots={"loan_type": "emergency", "amount": 5000},
        step_summary="0/2 steps done",
    )
    text = render_plan_status(state, "status of my request")
    assert "review" in text.lower()
    assert "5000" in text


def test_upsert_replaces_same_plan_id():
    state = ConversationState()
    upsert_active_plan(state, plan_id="p1", status="pending_approval", title="loan")
    upsert_active_plan(state, plan_id="p1", status="paused", title="loan")
    assert len(state.active_plans) == 1
    assert state.active_plans[0]["status"] == "paused"


@pytest.mark.asyncio
async def test_runner_plan_status_zero_llm():
    from ai.engine.cognition.turn.runner import TurnPipelineRunner
    from ai.engine.cognition.turn.witnesses import TurnLedger

    runner = TurnPipelineRunner.__new__(TurnPipelineRunner)
    state = ConversationState()
    upsert_active_plan(
        state,
        status="handoff_ready",
        title="emergency loan",
        slots={"loan_type": "emergency", "amount": 5000},
    )
    ctx = SimpleNamespace(state=state)
    ledger = TurnLedger()
    with patch(
        "ai.engine.cognition.notifier.broadcast_run_event",
        new_callable=AsyncMock,
    ):
        pair = await runner._try_plan_status_answer(  # noqa: SLF001
            user_message="What is the status of my request?",
            state_ctx=ctx,
            ledger=ledger,
            meter=SimpleNamespace(),
            turn_id="t1",
            instance_id="nibras",
            conversation_id="c1",
            host_user_id="u1",
            t0=0.0,
        )
    assert pair is not None
    response, out = pair
    assert out.turn_decision == "answer"
    assert out.total_llm_calls == 0
    assert "5000" in (response.text or "")
    assert "emergency" in (response.text or "").lower()


def test_create_plan_writes_active_plans(user, monkeypatch):
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    def _fake_decompose(self, user, brief):
        return Plan(
            pattern="custom",
            steps=[
                PlanStep(step_id=1, intent="Submit", tool_name="call_host_api"),
            ],
            synthesis_instruction="",
            source="llm_decompose",
        )

    monkeypatch.setattr(PlansService, "_decompose", _fake_decompose)
    conv = "conv-5b-plan"
    svc = PlansService()
    dto = svc.create_plan(user, brief="Emergency loan 5000", conversation_id=conv)
    row = ConversationContextRecord.objects.get(conversation_id=conv)
    state = ConversationState.from_dict(row.session_json)
    assert state.active_plans
    assert state.active_plans[0]["plan_id"] == dto["id"]
    assert state.active_plans[0]["status"] == STATUS_PENDING_APPROVAL
    run = Run.objects.get(id=dto["id"])
    assert run.instance_id == PLAN_INSTANCE_ID
    svc.approve_plan(user, dto["id"])
    state = ConversationState.from_dict(
        ConversationContextRecord.objects.get(conversation_id=conv).session_json
    )
    assert state.active_plans[0]["status"] == "approved"
