"""PV2-0A — truthful LLM-call meter + turn-decision signals (log-only)."""

from __future__ import annotations

import types
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.test import override_settings

from ai.tests.pv21_stub import answer_decision
from ai.engine.core.config import get_settings
from ai.engine.cognition.plan.loop import ReActLoop
from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.turn.witnesses import RetrievalResult
from ai.engine.llm.call_meter import (
    current_meter,
    meter_scope,
    record_call,
    stage,
)
from ai.store import reset_store


def _fake_completion(*args, **kwargs) -> types.SimpleNamespace:
    async def _create(**kw):
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content="This is a stubbed chat reply.",
                        tool_calls=answer_decision(kw),
                    ),
                    finish_reason="stop",
                )
            ],
            usage=types.SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=4,
                total_tokens=14,
            ),
        )

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=_create)
        )
    )


@pytest.fixture
def django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def single_pass(monkeypatch):
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "false")
    monkeypatch.setenv("KG_MULTI_STEP_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub_llm():
    with patch("ai.engine.llm.provider.get_llm_client") as mock:
        mock.return_value = _fake_completion()
        yield mock


@pytest.fixture
def no_nav_fast_path(monkeypatch):
    """Force single-pass spine — nav resolver matches too many dev briefs."""
    patched = get_settings().model_copy(
        update={"NAVIGATION_RESOLVER_ENABLED": False},
    )
    monkeypatch.setattr(
        "ai.engine.cognition.turn.runner.get_settings",
        lambda: patched,
    )


def test_call_meter_counts_per_stage():
    with meter_scope() as meter:
        with stage("draft"):
            record_call(12.0, 10, 4, "test-model")
            record_call(8.0, 5, 2, "test-model")
        with stage("critic"):
            record_call(6.0, 3, 1, "test-model")

    assert meter.by_stage() == {"draft": 2, "critic": 1}
    assert meter.total == 3

    # No active meter → no-op.
    assert current_meter() is None
    record_call(1.0, 1, 1, "x")
    assert meter.total == 3


def test_meter_scope_nesting_rolls_up_and_restores_outer():
    with meter_scope() as outer:
        with stage("pulse_loop"):
            with meter_scope() as inner:
                assert current_meter() is inner
                assert inner.parent is outer
                with stage("draft"):
                    record_call(2.0, 1, 1, "m")
            assert current_meter() is outer
        with stage("intent"):
            record_call(4.0, 1, 1, "m")

    assert inner.by_stage() == {"draft": 1}
    assert outer.by_stage() == {"pulse_loop": 1, "intent": 1}
    assert outer.total_ms() == 6.0
    assert outer.parent is None
    assert current_meter() is None


def test_meter_scope_grandchild_records_once_per_level():
    with meter_scope() as turn:
        with stage("pulse_loop"):
            with meter_scope() as run:
                with stage("plan_synthesis"):
                    with meter_scope() as step:
                        with stage("critic"):
                            record_call(1.0, 1, 1, "m")

    assert step.by_stage() == {"critic": 1}
    assert run.by_stage() == {"plan_synthesis": 1}
    assert turn.by_stage() == {"pulse_loop": 1}
    assert (step.total, run.total, turn.total) == (1, 1, 1)


@pytest.mark.django_db(transaction=True)
def test_chat_turn_reports_decision_and_meter(
    django_store, single_pass, stub_llm, cfg, no_nav_fast_path,
):
    from ai.engine_runtime import dispatch_task

    payload = {
        "message": "What is our carbon footprint this quarter?",
        "conversation_history": {
            "conversation_id": "conv-pv2-001",
            "messages": [{"role": "user", "content": "hello"}],
        },
    }
    data = dispatch_task("chat", payload, instance_id="carbon")
    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("content") == "This is a stubbed chat reply."
    assert result.get("turn_decision") in {
        "memory_confirm", "navigate", "process_brief", "clarify", "refuse",
        "answer", "handoff_agent", "tool_answer",
    }
    assert int(result.get("llm_calls") or 0) >= 1
    assert "answer" in (result.get("llm_calls_by_stage") or {})
    assert "unattributed" not in result["llm_calls_by_stage"], result["llm_calls_by_stage"]


@pytest.mark.django_db(transaction=True)
def test_nav_fast_path_records_zero_llm_and_navigate_decision(
    django_store, single_pass, cfg, monkeypatch,
):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    from ai.engine_runtime import dispatch_task

    payload = {
        "message": "payroll",
        "conversation_history": {
            "conversation_id": "conv-pv2-nav",
            "messages": [],
        },
    }
    data = dispatch_task("chat", payload, instance_id="nibras")
    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    assert result.get("turn_decision") == "navigate"
    assert int(result.get("llm_calls") or 0) == 0
    assert result.get("llm_calls_by_stage") == {}


@pytest.mark.django_db(transaction=True)
def test_plan_step_journal_carries_llm_calls(django_store, cfg):
    from ai.engine.cognition.turn.critic import CriticWitness
    from ai.engine.cognition.turn.draft import DraftWitness
    from ai.models.core import Run, RunStep
    from ai.store import get_store

    async def _go():
        async with get_store().get_session_factory()() as db:
            loop = ReActLoop(
                draft_witness=DraftWitness(),
                critic_witness=CriticWitness(),
                executor=None,
            )
            plan = Plan(
                pattern="custom",
                steps=[
                    PlanStep(step_id=0, intent="Summarize emissions", depends_on=[]),
                ],
                synthesis_instruction="Summarize.",
                source="test",
            )
            return await loop.run(
                plan=plan,
                instance_id="carbon",
                conversation_id="conv-plan-pv2",
                user_message="Summarize emissions",
                system_prompt="You are Carbon.",
                retrieval=RetrievalResult(),
                db=db,
            )

    with patch("ai.engine.llm.provider.get_llm_client") as mock_llm:
        mock_llm.return_value = _fake_completion()
        result = async_to_sync(_go)()

    assert result.step_results
    run = Run.objects.get(conversation_id="conv-plan-pv2")
    row = RunStep.objects.get(run_id=run.id, step_index=0)
    llm_meter = row.critic_flags_json["llm_meter"]
    assert isinstance(llm_meter["llm_calls"], int)
    assert llm_meter["llm_calls"] >= 1
    assert "draft" in llm_meter["llm_by_stage"]
    assert float(llm_meter["llm_ms"]) >= 0.0


@pytest.mark.django_db
def test_advance_step_journal_payload_carries_llm_meter():
    from ai import run_machine
    from ai.models.core import Run, RunStep
    from ai.models.step_journal import EVENT_STEP_COMPLETED, EVENT_STEP_STARTED
    from ai.plans_service import PlansService, _step_llm_meter
    from ai.step_journal import StepJournal, canonical_step_id

    run = Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id="conv-pv2-advance",
        host_user_id="1",
        user_message="brief",
        status="running",
        plan_json={"pattern": "custom", "steps": []},
    )
    meter = {"llm_calls": 2, "llm_ms": 12.5, "llm_by_stage": {"draft": 1, "critic": 1}}
    step = RunStep.objects.create(
        run_id=run.id,
        step_id="step-0",
        step_index=0,
        intent="Step 0",
        status="pending",
        step_state=run_machine.RUN_PLANNED,
        critic_flags_json={"consent_granted": True, "llm_meter": meter},
    )

    PlansService.advance_step(step, run_machine.RUN_READY)
    PlansService.advance_step(step, run_machine.RUN_EXECUTING)
    PlansService.advance_step(step, run_machine.RUN_SUCCEEDED, outcome="succeeded")

    entries = {
        e.event_type: e.payload
        for e in StepJournal.for_step(run.id, canonical_step_id(step))
    }
    assert entries[EVENT_STEP_STARTED] == {"llm_meter": meter}
    assert entries[EVENT_STEP_COMPLETED] == {"outcome": "succeeded", "llm_meter": meter}

    # Defensive reads: JSON string, missing key, garbage.
    import json
    assert _step_llm_meter(types.SimpleNamespace(
        critic_flags_json=json.dumps({"llm_meter": meter}),
    )) == meter
    assert _step_llm_meter(types.SimpleNamespace(critic_flags_json={"critic_flags": []})) is None
    assert _step_llm_meter(types.SimpleNamespace(critic_flags_json="not json")) is None
    assert _step_llm_meter(types.SimpleNamespace(critic_flags_json=None)) is None


@pytest.mark.django_db(transaction=True)
def test_meter_is_truthful_where_hand_count_drifts(
    django_store, single_pass, stub_llm, cfg, no_nav_fast_path, monkeypatch,
):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    from ai.engine_runtime import dispatch_task
    from ai.models.core import TurnLedgerRow

    payload = {
        "message": "What is our carbon footprint this quarter?",
        "conversation_history": {
            "conversation_id": "conv-pv2-meter",
            "messages": [],
        },
    }
    data = dispatch_task("chat", payload, instance_id="carbon")
    assert data.get("status") == "completed", data
    result = data.get("result") or {}
    by_stage = result.get("llm_calls_by_stage") or {}
    # auto_memory is fire-and-forget: present only if it lands before finalize.
    measured_excl = sum(v for k, v in by_stage.items() if k != "auto_memory")

    final_row = (
        TurnLedgerRow.objects.filter(
            conversation_id="conv-pv2-meter", stage="final",
        )
        .order_by("-created_at")
        .first()
    )
    hand = 0
    final_payload = final_row.payload_json if final_row else None
    if isinstance(final_payload, str):
        import json
        final_payload = json.loads(final_payload)
    if isinstance(final_payload, dict):
        hand = int(final_payload.get("total_llm_calls") or 0)

    assert "unattributed" not in by_stage, by_stage
    assert by_stage.get("intent") == 1, by_stage
    assert by_stage.get("draft") == 1, by_stage
    assert measured_excl == 2, by_stage
    # Hand counting skips the intent call; the meter does not.
    assert measured_excl - hand == 1, (hand, by_stage)
