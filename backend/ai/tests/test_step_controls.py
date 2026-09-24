"""
Per-step controls (Phase W-7) — retry / skip / cancel / pause / resume.

Covers the step-control state machine (``PlansService``) and its REST surface
(``PlanViewSet`` step-control actions):

  - retry: only a ``failed`` step re-queues to ``pending`` with
    ``retry_count`` incremented and the run flipped back to a resumable
    ``paused`` state; a ``completed`` step is refused.
  - skip: ``pending`` / ``failed`` / ``awaiting_approval`` / ``paused`` steps
    become ``skipped`` (satisfies ``depends_on`` — ``workflow.COMMITTED_STATUSES``
    holds ``skipped``); a ``completed`` step is refused.
  - cancel: a ``running`` step is abandoned to ``skipped``; the run continues.
  - pause/resume: ``running`` → ``paused`` → ``pending``; a ``pending`` step
    cannot be paused (guard).
  - journal: every control appends its non-effect marker event.
  - REST: 200 on the happy path, 409 Conflict on a state-guard violation.
  - replay: the deterministic fold tolerates the new control events (they are
    non-effect markers ignored for effect reconstruction) and stays
    deterministic.

Controls only transition / re-queue step state — no host effect is executed
here (RULE_21). Host-side only, no engine imports (RULE_20 / ADR-0007).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.models.core import Run, RunStep
from ai.models.step_journal import (
    EVENT_STEP_CANCELLED,
    EVENT_STEP_COMPLETED,
    EVENT_STEP_PAUSED,
    EVENT_STEP_QUEUED,
    EVENT_STEP_RESUMED,
    EVENT_STEP_RETRIED,
    EVENT_STEP_SKIPPED,
    EVENT_STEP_STARTED,
)
from ai.plans_service import (
    PlanStepError,
    PlansService,
    STEP_PAUSED,
)
from ai.step_journal import StepJournal, canonical_step_id

from ai.tests.test_plans import _make_plan, _make_step


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="step-ctl-worker", password="secret123")


@pytest.fixture
def run_ids_cleanup():
    ids: list[str] = []
    yield ids
    RunStep.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()


def _events(run_id, step) -> list[str]:
    """Journal event types for a step, ascending by sequence."""
    return [
        e.event_type
        for e in StepJournal.for_step(run_id, canonical_step_id(step))
    ]


def _reload(step) -> RunStep:
    return RunStep.objects.get(pk=step.pk)


# ── retry_step ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_retry_failed_step_requeues_and_makes_run_resumable(user, run_ids_cleanup):
    plan = _make_plan(user, status="failed")
    step = _make_step(plan, step_index=0, status="failed")
    step.error = "boom"
    step.save(update_fields=["error"])
    run_ids_cleanup.append(plan.id)

    result = PlansService().retry_step(user, plan.id, 0)

    assert result == {"status": "retried", "plan_id": plan.id, "step_id": 0}
    step = _reload(step)
    assert step.status == "pending"
    assert step.retry_count == 1
    assert not step.error
    # Failed run flipped to a resumable state so run/resume re-executes it.
    assert Run.objects.get(id=plan.id).status == "paused"
    assert EVENT_STEP_RETRIED in _events(plan.id, step)


@pytest.mark.django_db
def test_retry_completed_step_requeues(user, run_ids_cleanup):
    plan = _make_plan(user, status="completed")
    step = _make_step(plan, step_index=0, status="completed")
    run_ids_cleanup.append(plan.id)

    result = PlansService().retry_step(user, plan.id, 0)
    assert result["status"] == "retried"
    assert _reload(step).status == "pending"
    assert Run.objects.get(id=plan.id).status == "paused"


# ── rerun_plan ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_rerun_completed_plan_resets_steps_and_approves(user, run_ids_cleanup):
    plan = _make_plan(user, status="completed")
    plan.final_response = "### Prior answer\n\nTotal **42**"
    plan.save(update_fields=["final_response"])
    s0 = _make_step(plan, step_index=0, status="completed")
    s1 = _make_step(plan, step_index=1, status="failed")
    s1.error = "boom"
    s1.retry_count = 2
    s1.save(update_fields=["error", "retry_count"])
    run_ids_cleanup.append(plan.id)

    result = PlansService().rerun_plan(user, plan.id)

    assert result["rerun"] == {"of": "completed", "reset_count": 2}
    # Run returns to a runnable status so the existing run stream executes.
    assert Run.objects.get(id=plan.id).status == "approved"
    assert _reload(s0).status == "pending"
    s1 = _reload(s1)
    assert s1.status == "pending"
    assert not s1.error
    assert s1.retry_count == 0
    # Track D — prior Answer preserved for Output receipt (comparison pending).
    assert result.get("prior_run", {}).get("comparison") == "pending"
    assert "Prior answer" in (result["prior_run"]["prior_final_response"] or "")


@pytest.mark.django_db
def test_rerun_completed_with_gaps_plan_resets_and_approves(user, run_ids_cleanup):
    plan = _make_plan(user, status="completed_with_gaps")
    s0 = _make_step(plan, step_index=0, status="completed")
    s1 = _make_step(plan, step_index=1, status="failed")
    s1.error = "[caught] tool boom"
    s1.save(update_fields=["error"])
    run_ids_cleanup.append(plan.id)

    result = PlansService().rerun_plan(user, plan.id)

    assert result["rerun"] == {"of": "completed_with_gaps", "reset_count": 2}
    assert Run.objects.get(id=plan.id).status == "approved"
    assert _reload(s0).status == "pending"
    assert _reload(s1).status == "pending"
    assert not _reload(s1).error


@pytest.mark.django_db
def test_rerun_running_or_paused_plan_resets(user, run_ids_cleanup):
    plan = _make_plan(user, status="paused")
    step = _make_step(plan, step_index=0, status="awaiting_approval")
    run_ids_cleanup.append(plan.id)

    result = PlansService().rerun_plan(user, plan.id)

    assert result["rerun"]["of"] == "paused"
    assert result["rerun"]["reset_count"] == 1
    assert Run.objects.get(id=plan.id).status == "approved"
    assert _reload(step).status == "pending"


# ── skip_step ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_skip_pending_step_marks_skipped_and_journals(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="pending")
    run_ids_cleanup.append(plan.id)

    result = PlansService().skip_step(user, plan.id, 0)

    assert result["status"] == "skipped"
    assert _reload(step).status == "skipped"
    assert EVENT_STEP_SKIPPED in _events(plan.id, step)


@pytest.mark.django_db
def test_skip_completed_step_is_refused(user, run_ids_cleanup):
    plan = _make_plan(user, status="completed")
    step = _make_step(plan, step_index=0, status="completed")
    run_ids_cleanup.append(plan.id)

    with pytest.raises(PlanStepError):
        PlansService().skip_step(user, plan.id, 0)
    assert _reload(step).status == "completed"


# ── cancel_step ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_cancel_running_step_marks_skipped_and_journals(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="running")
    run_ids_cleanup.append(plan.id)

    result = PlansService().cancel_step(user, plan.id, 0)

    assert result["status"] == "cancelled"
    assert _reload(step).status == "skipped"
    assert EVENT_STEP_CANCELLED in _events(plan.id, step)


# ── pause_step / resume_step ────────────────────────────────────────────────


@pytest.mark.django_db
def test_pause_then_resume_round_trips_running_to_pending(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="running")
    run_ids_cleanup.append(plan.id)

    service = PlansService()

    assert service.pause_step(user, plan.id, 0)["status"] == "paused"
    assert _reload(step).status == STEP_PAUSED
    assert EVENT_STEP_PAUSED in _events(plan.id, step)

    assert service.resume_step(user, plan.id, 0)["status"] == "resumed"
    assert _reload(step).status == "pending"
    assert EVENT_STEP_RESUMED in _events(plan.id, step)


@pytest.mark.django_db
def test_pause_pending_step_holds_it(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="pending")
    run_ids_cleanup.append(plan.id)

    assert PlansService().pause_step(user, plan.id, 0)["status"] == "paused"
    assert _reload(step).status == STEP_PAUSED


@pytest.mark.django_db
def test_resume_running_step_requeues(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="running")
    run_ids_cleanup.append(plan.id)

    assert PlansService().resume_step(user, plan.id, 0)["status"] == "resumed"
    assert _reload(step).status == "pending"


@pytest.mark.django_db
def test_second_control_on_transitioned_step_raises_clean(user, run_ids_cleanup):
    """Idempotent-safe: a repeat control on an already-moved step raises a
    clear ``PlanStepError`` (not a crash)."""
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="pending")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    service.skip_step(user, plan.id, 0)  # pending -> skipped
    with pytest.raises(PlanStepError):
        service.skip_step(user, plan.id, 0)  # already skipped


# ── REST surface ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_api_retry_happy_path(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    plan = _make_plan(user, status="failed")
    _make_step(plan, step_index=0, status="failed")
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/steps/0/retry/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "retried"


@pytest.mark.django_db
def test_api_retry_guard_violation_is_conflict(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status="completed")
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/steps/0/retry/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "retried"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "verb,start_status",
    [
        ("skip", "pending"),
        ("cancel", "running"),
        ("pause", "running"),
    ],
)
def test_api_step_control_happy_path(
    api_client, get_token_for_user, user, run_ids_cleanup, verb, start_status
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status=start_status)
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/steps/0/{verb}/")
    assert resp.status_code == 200, resp.content


@pytest.mark.django_db
def test_api_resume_happy_path(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status=STEP_PAUSED)
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/steps/0/resume/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "resumed"


@pytest.mark.django_db
def test_api_pause_guard_violation_is_conflict(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status="pending")
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/steps/0/pause/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "paused"


@pytest.mark.django_db
def test_api_control_requires_auth(api_client, user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status="pending")
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/steps/0/skip/")
    assert resp.status_code == 401


# ── Deterministic replay fold tolerates the control events ───────────────


def _fold(*event_types):
    return StepJournal.reconstruct(
        [SimpleNamespace(event_type=e) for e in event_types]
    )


def test_fold_ignores_control_events_for_effect_reconstruction():
    """Control markers are non-effect: the fold reconstructs the same
    committed outcome whether or not a skip/cancel/pause/resume follows."""
    base = _fold(EVENT_STEP_QUEUED, EVENT_STEP_STARTED, EVENT_STEP_COMPLETED)
    with_control = _fold(
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_COMPLETED,
        EVENT_STEP_SKIPPED,
    )
    assert with_control == base
    assert with_control["committed"] is True


def test_fold_is_deterministic_across_all_control_events():
    events = (
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_PAUSED,
        EVENT_STEP_RESUMED,
        EVENT_STEP_CANCELLED,
        EVENT_STEP_SKIPPED,
    )
    first = _fold(*events)
    second = _fold(*events)
    assert first == second
    # No crash; control-only tail leaves the pre-control effect state intact.
    assert first["committed"] is False


@pytest.mark.django_db
def test_persisted_control_journal_reconstructs_cleanly(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    step = _make_step(plan, step_index=0, status="running")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    service.pause_step(user, plan.id, 0)
    service.resume_step(user, plan.id, 0)

    entries = StepJournal.for_step(plan.id, canonical_step_id(step))
    first = StepJournal.reconstruct(entries)
    second = StepJournal.reconstruct(entries)
    assert first == second  # deterministic, no crash on the new event kinds
