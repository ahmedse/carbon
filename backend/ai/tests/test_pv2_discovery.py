"""PV2-3C — discovery: 0 LLM on process-dial short-circuit; never re-ask known slots."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from accounts.models import User
from ai.engine.cognition.state_store import ConversationState
from ai.models.core import ConversationContextRecord
from ai.plans_service import PlansService

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(username="pv2-3c-disc", password="secret123")


def _seed_state(conversation_id: str, **slots):
    state = ConversationState()
    state.slots = dict(slots)
    ConversationContextRecord.objects.update_or_create(
        conversation_id=conversation_id,
        defaults={"instance_id": "nibras", "session_json": state.to_dict()},
    )


def test_process_dial_short_circuit_zero_llm(user, monkeypatch):
    called = {"n": 0}

    async def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("discovery LLM must not run on process dial")

    monkeypatch.setattr("ai.engine.llm.router.route_chat", _boom)
    monkeypatch.setattr(
        PlansService,
        "create_plan",
        lambda self, *a, **k: {"id": "plan-3c", "status": "pending_approval"},
    )
    result = PlansService().start_discovery(
        user, brief="I want an emergency loan of 3000 SAR",
    )
    assert called["n"] == 0
    assert result.get("llm_calls", 0) == 0
    assert result["status"] == "plan_ready"
    assert result.get("question") in (None, "")


def test_scope_route_leave_gate_zero_llm(user, monkeypatch):
    called = {"n": 0}

    async def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("gated leave must not call discovery LLM")

    monkeypatch.setattr("ai.engine.llm.router.route_chat", _boom)
    result = PlansService().start_discovery(user, brief="أريد عمل اجازه")
    assert called["n"] == 0
    assert result.get("id") is None
    assert result.get("plannable") is False


@pytest.mark.parametrize("language,forbidden", [
    ("en", ("how much", "amount", "principal")),
    ("ar", ("المبلغ", "كم")),
])
def test_state_amount_never_reasked(user, monkeypatch, language, forbidden):
    conv = f"conv-3c-amt-{language}"
    _seed_state(conv, amount=5000, principal=5000)

    monkeypatch.setattr(
        "ai.engine.llm.router.route_chat",
        AsyncMock(
            return_value={
                "content": (
                    '{"action":"ask","question":"How much is the amount / كم المبلغ؟"}'
                    if language == "en"
                    else '{"action":"ask","question":"كم المبلغ المطلوب؟"}'
                ),
                "tool_calls": None,
                "finish_reason": "stop",
                "model": "test",
            }
        ),
    )
    # Force language so sanitize picks AR residual wording.
    monkeypatch.setattr(
        "ai.engine_runtime._build_chat_user_info",
        lambda *_a, **_k: {"language": language, "audience": ["ess"]},
    )
    result = PlansService().start_discovery(
        user,
        brief="Summarize our carbon footprint",
        conversation_id=conv,
    )
    question = (result.get("question") or "").lower()
    assert result["status"] == "needs_input"
    for token in forbidden:
        assert token not in question, (token, result.get("question"))
    assert "how much" not in question
    assert "كم المبلغ" not in (result.get("question") or "")


def test_chat_slots_appear_in_agent_discovery_brief(user, monkeypatch):
    conv = "conv-5a-inherit"
    _seed_state(conv, loan_type="emergency", amount=3000, principal=3000)
    seen = {"brief": ""}

    def _capture(self, user, brief="", conversation_id=""):
        seen["brief"] = brief
        return {"id": "plan-5a", "status": "pending_approval"}

    monkeypatch.setattr(PlansService, "create_plan", _capture)
    PlansService().start_discovery(
        user,
        brief="I want to apply for a loan",
        conversation_id=conv,
    )
    assert "emergency" in seen["brief"]
    assert "3000" in seen["brief"]
    assert "Inherited from Chat" in seen["brief"]


def test_public_inherited_context_is_outcome_only(user):
    conv = "conv-5c-inherit"
    _seed_state(conv, loan_type="emergency", amount=3000, principal=3000, api="submit_my_loan")
    items = PlansService()._public_inherited_context(conv)
    keys = {i["key"] for i in items}
    assert keys == {"amount", "loan_type"}
    values = {i["key"]: i["value"] for i in items}
    assert values["amount"] == "3000"
    assert values["loan_type"] == "emergency"
    assert "api" not in keys


def test_serialize_run_includes_inherited_context(user):
    from ai.models.core import Run, generate_uuid
    from ai.plans_service import PLAN_INSTANCE_ID, STATUS_PENDING_APPROVAL

    conv = "conv-5c-ser"
    _seed_state(conv, leave_type="sick", start_date="2026-09-24")
    run = Run.objects.create(
        id=generate_uuid(),
        instance_id=PLAN_INSTANCE_ID,
        conversation_id=conv,
        host_user_id=str(user.pk),
        user_message="sick leave tomorrow",
        status=STATUS_PENDING_APPROVAL,
        plan_json={"pattern": "custom", "steps": []},
    )
    dto = PlansService._serialize_run(run)
    keys = {i["key"] for i in dto.get("inherited_context") or []}
    assert "leave_type" in keys
    assert "start_date" in keys


def test_discovery_prompt_includes_stateblock(user):
    conv = "conv-3c-pack"
    _seed_state(conv, amount=5000, loan_type="emergency")
    svc = PlansService()
    state = svc._load_conversation_state(conv)  # noqa: SLF001
    messages = svc._discovery_prompt(  # noqa: SLF001
        "Summarize our carbon footprint",
        [],
        state=state,
        known_slots={"amount": 5000, "loan_type": "emergency"},
        language="en",
    )
    system = messages[0]["content"]
    assert "CONVERSATION STATE" in system or "amount=5000" in system
    last = messages[-1]["content"]
    assert "amount=5000" in last
    assert "do NOT ask" in last or "Never re-ask" in last
