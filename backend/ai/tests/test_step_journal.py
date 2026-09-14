"""P3-07b — Workflow/activity split + deterministic step journal replay.

Acceptance: restart mid-run → resumes from journal (completed activities are
NOT re-executed; interrupted activities resume to their reconstructed state;
the fold is deterministic).  Plus append-only monotonic sequencing, closed
event vocabulary, workflow-vs-activity classification, bounded retry-count
journaling, and the consent gate (never auto-confirmed).

Host-side only — no engine imports (RULE_20 / ADR-0007).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from django.utils import timezone

from accounts.models import User
from ai import run_machine
from ai.models.core import Run, RunStep
from ai.models.step_journal import (
    EVENT_OUTCOME_UNKNOWN,
    EVENT_STEP_COMPLETED,
    EVENT_STEP_CONSENT_DECLINED,
    EVENT_STEP_CONSENT_GRANTED,
    EVENT_STEP_CONSENT_REQUESTED,
    EVENT_STEP_FAILED,
    EVENT_STEP_QUEUED,
    EVENT_STEP_RETRIED,
    EVENT_STEP_STARTED,
    STEP_KIND_ACTIVITY,
    STEP_KIND_WORKFLOW,
    StepJournalEntry,
)
from ai.plans_service import (
    RETRY_MAX_ATTEMPTS,
    STEP_AWAITING_APPROVAL,
    PlansService,
)
from ai.step_journal import StepJournal, canonical_step_id


@pytest.fixture
def user(db):
    return User.objects.create_user(username="journal-worker", password="secret123")


def _make_run(user, status="running"):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="test brief",
        status=status,
        plan_json={"pattern": "custom", "steps": []},
    )


def _make_jstep(run, step_id="step-0", step_index=0, step_kind=STEP_KIND_ACTIVITY):
    return RunStep.objects.create(
        run_id=run.id,
        step_id=step_id,
        step_index=step_index,
        intent=f"Step {step_index}",
        tool_name="host:emissions.summarize" if step_kind == STEP_KIND_ACTIVITY else None,
        tool_args_json={},
        depends_on_json=[],
        step_kind=step_kind,
        status="pending",
        step_state=run_machine.RUN_PLANNED,
    )


def _fold(*event_types):
    """Pure fold over event names (no DB) — for determinism assertions."""
    return StepJournal.reconstruct(
        [SimpleNamespace(event_type=e) for e in event_types]
    )


# ── Fold determinism (the single source of truth) ─────────────────────────


def test_fold_is_deterministic():
    events = (EVENT_STEP_QUEUED, EVENT_STEP_STARTED, EVENT_STEP_COMPLETED)
    first = _fold(*events)
    second = _fold(*events)
    assert first == second
    assert first["committed"] is True
    assert first["step_state"] == run_machine.RUN_SUCCEEDED
    assert first["status"] == "completed"


def test_fold_failed_is_not_committed():
    recon = _fold(EVENT_STEP_QUEUED, EVENT_STEP_STARTED, EVENT_STEP_FAILED)
    assert recon["committed"] is False
    assert recon["step_state"] == run_machine.RUN_FAILED
    assert recon["status"] == "failed"
    assert recon["outcome"] == "failed"


def test_fold_consent_declined_is_terminal_committed():
    recon = _fold(
        EVENT_STEP_QUEUED, EVENT_STEP_STARTED, EVENT_STEP_CONSENT_DECLINED
    )
    assert recon["committed"] is True
    assert recon["consent"] == "declined"
    assert recon["step_state"] == run_machine.RUN_CANCELLED
    assert recon["status"] == "skipped"


def test_fold_consent_granted_never_auto_confirmed():
    recon = _fold(
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_CONSENT_REQUESTED,
        EVENT_STEP_CONSENT_GRANTED,
    )
    # Consent granted but NOT terminal — the step still awaits its staged
    # execution (RULE_21: consent is never auto-confirmed into an effect).
    assert recon["committed"] is False
    assert recon["consent"] == "granted"
    assert recon["step_state"] == run_machine.RUN_AWAITING_APPROVAL


def test_fold_retry_increments_exactly_once_per_retried_event():
    recon = _fold(
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_FAILED,
        EVENT_STEP_RETRIED,
        EVENT_STEP_STARTED,
        EVENT_STEP_COMPLETED,
    )
    assert recon["retry_count"] == 1
    assert recon["committed"] is True


def test_fold_outcome_unknown_lands_on_running():
    recon = _fold(EVENT_STEP_QUEUED, EVENT_STEP_STARTED, EVENT_OUTCOME_UNKNOWN)
    assert recon["committed"] is False
    assert recon["step_state"] == run_machine.RUN_OUTCOME_UNKNOWN
    assert recon["status"] == "running"


# ── Append-only journal ───────────────────────────────────────────────────


def test_append_monotonic_sequence_and_ordering(db, user):
    run = _make_run(user)
    step = _make_jstep(run)
    sid = canonical_step_id(step)

    StepJournal.append(run.id, sid, EVENT_STEP_QUEUED)
    StepJournal.append(run.id, sid, EVENT_STEP_STARTED)
    StepJournal.append(run.id, sid, EVENT_STEP_COMPLETED)

    entries = StepJournal.for_step(run.id, sid)
    assert [e.sequence for e in entries] == [1, 2, 3]
    assert [e.event_type for e in entries] == [
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_COMPLETED,
    ]
    # The default ordering already returns ascending sequence.
    assert list(StepJournalEntry.objects.filter(run_id=run.id)) == entries


def test_append_rejects_unknown_event(db, user):
    run = _make_run(user)
    step = _make_jstep(run)
    with pytest.raises(ValueError):
        StepJournal.append(run.id, canonical_step_id(step), "engine_thingy")


# ── Workflow / activity split ─────────────────────────────────────────────


def test_is_activity_classifies_workflow_vs_activity(db, user):
    run = _make_run(user)
    workflow = _make_jstep(run, step_id="wf", step_kind=STEP_KIND_WORKFLOW)
    activity = _make_jstep(run, step_id="act", step_kind=STEP_KIND_ACTIVITY)

    assert PlansService.is_activity(workflow) is False
    assert PlansService.is_activity(activity) is True


def test_default_step_kind_is_activity(db, user):
    run = _make_run(user)
    # Omit step_kind → model default is "activity" (retry, don't skip).
    step = RunStep.objects.create(
        run_id=run.id,
        step_index=0,
        intent="default kind",
        status="pending",
        step_state=run_machine.RUN_PLANNED,
    )
    assert step.step_kind == STEP_KIND_ACTIVITY
    assert PlansService.is_activity(step) is True


# ── Replay decisions (exactly-one-effect) ─────────────────────────────────


def test_replay_completed_step_is_noop_not_reexecuted(db, user):
    run = _make_run(user)
    step = _make_jstep(run, step_id="step-0", step_kind=STEP_KIND_ACTIVITY)
    sid = canonical_step_id(step)
    StepJournal.append(run.id, sid, EVENT_STEP_QUEUED)
    StepJournal.append(run.id, sid, EVENT_STEP_STARTED)
    StepJournal.append(run.id, sid, EVENT_STEP_COMPLETED)

    result = PlansService.replay_step(run, step)

    assert result["action"] == "noop"
    assert result["committed"] is True
    assert result["step_state"] == run_machine.RUN_SUCCEEDED
    assert result["status"] == "completed"
    # Row restored to the journal fold, and NO new events appended → the
    # completed activity was not re-executed.
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_SUCCEEDED
    assert step.status == "completed"
    assert len(StepJournal.for_step(run.id, sid)) == 3


def test_replay_interrupted_activity_resumes_from_journal(db, user):
    run = _make_run(user)
    step = _make_jstep(run, step_id="step-1", step_kind=STEP_KIND_ACTIVITY)
    sid = canonical_step_id(step)
    StepJournal.append(run.id, sid, EVENT_STEP_QUEUED)
    StepJournal.append(run.id, sid, EVENT_STEP_STARTED)
    # Interrupted mid-activity: started but never completed (e.g. crash).

    result = PlansService.replay_step(run, step)

    assert result["action"] == "resume"
    assert result["committed"] is False
    assert result["step_state"] == run_machine.RUN_EXECUTING
    assert result["status"] == "running"
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_EXECUTING


def test_replay_workflow_step_requeues(db, user):
    run = _make_run(user)
    step = _make_jstep(run, step_id="wf-0", step_kind=STEP_KIND_WORKFLOW)
    sid = canonical_step_id(step)
    StepJournal.append(run.id, sid, EVENT_STEP_QUEUED)

    result = PlansService.replay_step(run, step)

    assert result["action"] == "requeue"
    assert result["committed"] is False
    assert result["step_state"] == run_machine.RUN_PLANNED


def test_replay_is_idempotent(db, user):
    run = _make_run(user)
    step = _make_jstep(run, step_id="step-2", step_kind=STEP_KIND_ACTIVITY)
    sid = canonical_step_id(step)
    StepJournal.append(run.id, sid, EVENT_STEP_QUEUED)
    StepJournal.append(run.id, sid, EVENT_STEP_STARTED)

    first = PlansService.replay_step(run, step)
    second = PlansService.replay_step(run, step)
    assert first == second


# ── Acceptance: restart mid-run → resumes from journal ────────────────────


def test_restart_mid_run_resumes_from_journal(db, user):
    """A mid-run restart replays each step from the journal: committed
    activities are skipped (exactly-one-effect), the interrupted activity
    resumes, and the workflow step re-queues — all deterministically."""
    run = _make_run(user)

    done = _make_jstep(run, step_id="done", step_index=0)
    interrupted = _make_jstep(run, step_id="mid", step_index=1)
    workflow = _make_jstep(run, step_id="wf", step_index=2, step_kind=STEP_KIND_WORKFLOW)

    # "done" committed before the crash.
    for evt in (EVENT_STEP_QUEUED, EVENT_STEP_STARTED, EVENT_STEP_COMPLETED):
        StepJournal.append(run.id, "done", evt)
    # "mid" was executing when the process died.
    for evt in (EVENT_STEP_QUEUED, EVENT_STEP_STARTED):
        StepJournal.append(run.id, "mid", evt)
    # "wf" was queued but never started.
    StepJournal.append(run.id, "wf", EVENT_STEP_QUEUED)

    decisions = {
        s.step_id: PlansService.replay_step(run, s)
        for s in (done, interrupted, workflow)
    }

    assert decisions["done"]["action"] == "noop"
    assert decisions["mid"]["action"] == "resume"
    assert decisions["wf"]["action"] == "requeue"

    # Exactly-one-effect: the committed activity has NO re-execution events.
    assert len(StepJournal.for_step(run.id, "done")) == 3

    # Replay is deterministic across a second restart.
    again = {
        s.step_id: PlansService.replay_step(run, s)
        for s in (done, interrupted, workflow)
    }
    assert again == decisions


def test_consent_never_auto_confirmed_on_replay(db, user):
    """Replaying a consent-gated activity resumes it WITHOUT granting consent
    (RULE_21)."""
    run = _make_run(user)
    step = _make_jstep(run, step_id="gate", step_kind=STEP_KIND_ACTIVITY)
    sid = canonical_step_id(step)
    for evt in (
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_CONSENT_REQUESTED,
    ):
        StepJournal.append(run.id, sid, evt)

    result = PlansService.replay_step(run, step)

    assert result["consent"] is None
    assert result["action"] == "resume"
    assert result["step_state"] == run_machine.RUN_AWAITING_APPROVAL
    # No consent event was appended by replay.
    assert [e.event_type for e in StepJournal.for_step(run.id, sid)] == [
        EVENT_STEP_QUEUED,
        EVENT_STEP_STARTED,
        EVENT_STEP_CONSENT_REQUESTED,
    ]


# ── Acceptance: deterministic activity dispatch (retry / reconciliation) ──


def test_activity_retry_policy_capped(db, user):
    """A transiently failing activity is re-dispatched exactly
    ``RETRY_MAX_ATTEMPTS`` times — never unbounded (bounded retry policy)."""
    run = _make_run(user)
    step = _make_jstep(run, step_id="step-0", step_kind=STEP_KIND_ACTIVITY)
    attempts: list[int] = []

    def flaky_effect(*, operation_id, attempt):
        attempts.append(attempt)
        return {"status": "failed", "error": "transient"}

    final = PlansService().dispatch_activity(
        run, step, flaky_effect, sleep=lambda _s: None
    )

    assert final == "failed"
    assert len(attempts) == RETRY_MAX_ATTEMPTS
    step.refresh_from_db()
    assert step.retry_count == RETRY_MAX_ATTEMPTS - 1
    assert step.step_state == run_machine.RUN_FAILED
    assert step.status == "failed"


def test_dispatch_outcome_unknown_never_blind_retries(db, user):
    """An ``outcome_unknown`` effect is NEVER blind-retried: it is routed to
    reconciliation (P3-08) with its operation id persisted for read-back."""
    run = _make_run(user)
    step = _make_jstep(run, step_id="step-0", step_kind=STEP_KIND_ACTIVITY)
    attempts: list[int] = []

    def flaky_effect(*, operation_id, attempt):
        attempts.append(attempt)
        return {"status": "outcome_unknown", "error": "readback timed out"}

    final = PlansService().dispatch_activity(
        run, step, flaky_effect, sleep=lambda _s: None
    )

    assert final == "outcome_unknown"
    assert len(attempts) == 1  # exactly one dispatch — no blind retry
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION
    assert step.operation_id == f"op-{run.id}-{canonical_step_id(step)}"


def test_operation_id_persisted_on_successful_dispatch(db, user):
    """The activity's operation id is persisted at dispatch time and survives
    a successful effect (the stable read-back key for reconciliation)."""
    run = _make_run(user)
    step = _make_jstep(run, step_id="step-0", step_kind=STEP_KIND_ACTIVITY)

    def ok_effect(*, operation_id, attempt):
        return {"status": "succeeded", "result": {"ok": True}}

    final = PlansService().dispatch_activity(
        run, step, ok_effect, sleep=lambda _s: None
    )

    assert final == "succeeded"
    step.refresh_from_db()
    assert step.operation_id == f"op-{run.id}-{canonical_step_id(step)}"
    assert step.step_state == run_machine.RUN_SUCCEEDED
    assert step.status == "completed"


# ── Acceptance: consent gate survives a multi-day restart ─────────────────


def test_three_day_approval_survives_restart(db, user):
    """A consent-gated activity stays gated after a 3-day restart — the
    ``now`` clock is recorded for provenance but NEVER auto-expires consent
    (RULE_21)."""
    run = _make_run(user, status="approved")
    step = _make_jstep(run, step_id="gate", step_kind=STEP_KIND_ACTIVITY)
    step.step_state = run_machine.RUN_AWAITING_APPROVAL
    step.status = STEP_AWAITING_APPROVAL
    step.save(update_fields=["step_state", "status", "updated_at"])

    result = PlansService().resume_workflow(
        user,
        run.id,
        now=timezone.now() + timedelta(days=3),
    )

    assert result["status"] == "resumed"
    assert result["next_activity"] is None  # still consent-gated
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_AWAITING_APPROVAL
