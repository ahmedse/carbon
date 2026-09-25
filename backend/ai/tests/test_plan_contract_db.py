"""ADR-0052 on persisted plans: resume, Approve, guard picks, and the final gate."""
from __future__ import annotations

import uuid

import pytest

from ai.models.core import Run, RunStep
from ai.plans_service import (
    PLAN_INSTANCE_ID,
    PlanStepError,
    PlansService,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_GAPS,
    _hold_for_missed_acceptance,
    _reconcile_run_status_from_steps,
)


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username=f"contract-{uuid.uuid4().hex[:6]}", password="x")


def _run(user, steps, status="paused", brief="Escalate the variance."):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id=PLAN_INSTANCE_ID,
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message=brief,
        status=status,
        plan_json={"pattern": "custom", "source": "llm_decompose", "steps": steps},
    )


def _row(run, index, status, **kw):
    return RunStep.objects.create(
        run_id=run.id, step_index=index, intent=kw.pop("intent", f"Step {index}"),
        tool_name=kw.pop("tool_name", None), tool_args_json=kw.pop("tool_args", {}),
        depends_on_json=kw.pop("depends_on", []), status=status, **kw,
    )


_INVENTED = [{
    "step_id": 0,
    "intent": "Escalate to the team",
    "tool_name": "call_host_api",
    "tool_args": {"api_name": "escalate_to_finance"},
    "depends_on": [],
    "is_mutation": True,
}]


@pytest.mark.django_db
def test_old_paused_plan_with_invented_api_is_refused_at_approve(user):
    run = _run(user, _INVENTED)
    _row(run, 0, "awaiting_approval", tool_name="call_host_api",
         tool_args={"api_name": "escalate_to_finance"}, confirmation_token="t")
    with pytest.raises(PlanStepError) as err:
        PlansService().confirm_step(user, run.id, 0)
    assert str(err.value).startswith("gap:")
    assert "not a host API" not in str(err.value)


@pytest.mark.django_db(transaction=True)
def test_old_paused_plan_with_invented_api_is_refused_at_resume(user):
    run = _run(user, _INVENTED)
    _row(run, 0, "awaiting_approval", tool_name="call_host_api",
         tool_args={"api_name": "escalate_to_finance"})
    frames = list(PlansService()._run_plan_frames_sync(user, run.id))
    assert frames and frames[0]["type"] == "error"
    assert frames[0]["code"] == "plan_contract"
    assert frames[0]["error"].startswith("gap:")
    assert Run.objects.get(pk=run.id).status == "paused"


@pytest.mark.django_db
def test_guard_pick_is_written_to_the_source_step(user):
    steps = [
        {"step_id": 1, "intent": "band", "tool_name": None, "tool_args": {}, "depends_on": []},
        {"step_id": 6, "intent": "board pack", "tool_name": "export_document",
         "tool_args": {"title": "Board"}, "depends_on": [1],
         "guard": {"step": 1, "field": "within_band", "value": True}},
    ]
    run = _run(user, steps)
    source = _row(run, 1, "completed")
    _row(run, 6, "awaiting_approval", tool_name="export_document",
         tool_args={"title": "Board"}, depends_on=[1],
         critic_flags_json={
             "failure_class": "missing_binding",
             "choice": {"kind": "guard", "key": "within_band", "step": 1,
                        "options": [{"value": True}, {"value": False}]},
         })
    with pytest.raises(PlanStepError):
        PlansService().confirm_step(user, run.id, 6, body_override={"within_band": "maybe"})
    out = PlansService().confirm_step(user, run.id, 6, body_override={"within_band": False})
    assert out["choice"] == {"within_band": False}
    source.refresh_from_db()
    assert source.critic_flags_json["guard_values"] == {"within_band": False}


@pytest.mark.django_db
def test_missed_acceptance_holds_the_run_and_leads_the_summary(user):
    run = _run(user, [], status=STATUS_COMPLETED)
    run.final_response = "Board pack exported."
    run.save()
    step = _row(run, 0, "completed", intent="Board pack")
    report = {"status": "missed", "requirements": [
        {"step_id": 0, "intent": "Board pack", "verdict": "missed"},
    ]}
    assert _hold_for_missed_acceptance(run, report) is True
    run.refresh_from_db()
    assert run.status == STATUS_COMPLETED_WITH_GAPS
    assert run.final_response.startswith("Not complete")
    assert "Board pack exported." in run.final_response

    run.working_notes = {"flight": {"acceptance": {"status": "missed"}}}
    run.status = STATUS_COMPLETED
    run.save()
    _reconcile_run_status_from_steps(run, [step])
    assert Run.objects.get(pk=run.id).status == STATUS_COMPLETED_WITH_GAPS


@pytest.mark.django_db
def test_met_acceptance_leaves_a_completed_run(user):
    run = _run(user, [], status=STATUS_COMPLETED)
    assert _hold_for_missed_acceptance(run, {"status": "met", "requirements": []}) is False
    assert Run.objects.get(pk=run.id).status == STATUS_COMPLETED
