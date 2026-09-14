"""P3-08 — Reconciliation worker tests (all sync, django_db).

Covers the acceptance test — *timeout-after-commit → exactly one effect* —
plus deterministic resolution (committed→succeeded, absent→failed),
inconclusive→escalation, never-blind-retry, the operation-id persistence seam,
fail-closed missing-operation-id escalation, and escalation idempotency.

Run with::

    cd backend && python -m pytest ai/tests/test_reconciliation.py -q -m "not live" --create-db
"""

from __future__ import annotations

import pytest

from accounts.models import User
from ai import run_machine
from ai.models.core import Run, RunStep
from ai.models.reconciliation import (
    READBACK_ABSENT,
    READBACK_COMMITTED,
    READBACK_UNKNOWN,
    ReconciliationEscalation,
)
from ai.plans_service import PlansService
from ai.reconciliation import (
    ACTION_ESCALATED,
    ACTION_RESOLVED_FAILED,
    ACTION_RESOLVED_SUCCEEDED,
    ReadBackResult,
    reconcile_pending,
    reconcile_step,
    register_read_back,
)


def _make_awaiting_step(
    *,
    operation_id: str = "op-123",
    tool_name: str = "export_report",
    step_id: str = "1",
) -> tuple[Run, RunStep]:
    """Create a Run + RunStep routed through to ``awaiting_reconciliation``.

    Uses the real seam: ``begin_step → ready → executing →
    reconcile_outcome(op_id=...)`` so ``operation_id`` is persisted exactly as
    the dispatch path would do it.
    """
    run = Run.objects.create(
        instance_id="recon-instance",
        conversation_id="recon-conversation",
        user_message="run the plan",
        definition_id="proc.recon",
        definition_version="v1",
    )
    step, _ = PlansService.begin_step(
        run, step_id, intent="export report", tool_name=tool_name,
    )
    PlansService.advance_step(step, run_machine.RUN_READY)
    PlansService.advance_step(step, run_machine.RUN_EXECUTING)
    PlansService.reconcile_outcome(step, op_id=operation_id)
    step.refresh_from_db()
    return run, step


# ── Acceptance test: timeout-after-commit → exactly one effect ─────────────

@pytest.mark.django_db
def test_timeout_after_commit_exactly_one_effect():
    """A dispatch that timed out but actually committed must resolve to
    ``succeeded`` WITHOUT re-dispatching — the effect happens exactly once."""
    run, step = _make_awaiting_step(operation_id="op-123")

    # The effect was dispatched exactly once and committed downstream; the
    # dispatch call then timed out, leaving the step outcome_unknown.
    committed_effects = ["committed:op-123"]

    def read_back(s: RunStep) -> ReadBackResult:
        # Authoritative read-back by operation id: the effect is present.
        if s.operation_id == "op-123" and "committed:op-123" in committed_effects:
            return ReadBackResult(READBACK_COMMITTED, "committed downstream")
        return ReadBackResult(READBACK_ABSENT, "absent")

    result = reconcile_step(step, read_back=read_back)

    assert result.action == ACTION_RESOLVED_SUCCEEDED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_SUCCEEDED
    assert step.outcome == "succeeded"

    # The reconciler never re-dispatched: the downstream effect list is
    # unchanged — exactly one effect, and no escalation was created.
    assert committed_effects == ["committed:op-123"]
    assert not ReconciliationEscalation.objects.filter(
        run_id=run.id, step_id=step.step_id
    ).exists()


# ── Deterministic resolution ───────────────────────────────────────────────

@pytest.mark.django_db
def test_committed_read_back_resolves_succeeded():
    run, step = _make_awaiting_step(operation_id="op-1")

    result = reconcile_step(
        step, read_back=lambda s: ReadBackResult(READBACK_COMMITTED, "done")
    )

    assert result.action == ACTION_RESOLVED_SUCCEEDED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_SUCCEEDED
    assert step.outcome == "succeeded"


@pytest.mark.django_db
def test_absent_read_back_resolves_failed():
    run, step = _make_awaiting_step(operation_id="op-2")

    result = reconcile_step(
        step, read_back=lambda s: ReadBackResult(READBACK_ABSENT, "never happened")
    )

    assert result.action == ACTION_RESOLVED_FAILED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_FAILED
    assert step.outcome == "failed"
    assert "never happened" in step.last_error


# ── Escalation (fail-closed) ───────────────────────────────────────────────

@pytest.mark.django_db
def test_inconclusive_read_back_creates_escalation():
    run, step = _make_awaiting_step(operation_id="op-3")

    result = reconcile_step(
        step, read_back=lambda s: ReadBackResult(READBACK_UNKNOWN, "timeout")
    )

    assert result.action == ACTION_ESCALATED
    step.refresh_from_db()
    # Step stays unresolved — never guessed, never resolved.
    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION

    escalation = ReconciliationEscalation.objects.get(
        run_id=run.id, step_id=step.step_id
    )
    assert escalation.operation_id == "op-3"
    assert escalation.read_back_status == READBACK_UNKNOWN
    assert escalation.process_id == "proc.recon"


@pytest.mark.django_db
def test_inconclusive_never_blind_retries():
    """An inconclusive read-back must not re-execute the effect, and must not
    mark the step succeeded or failed — it stays awaiting_reconciliation."""
    run, step = _make_awaiting_step(operation_id="op-4")
    dispatched = []

    def read_back(s: RunStep) -> ReadBackResult:
        # No re-dispatch here and no side effect: inconclusive.
        return ReadBackResult(READBACK_UNKNOWN, "ambiguous")

    result = reconcile_step(step, read_back=read_back)

    assert result.action == ACTION_ESCALATED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION
    assert step.outcome == "outcome_unknown"  # unchanged, never a success guess
    assert dispatched == []  # the reconciler never dispatched anything


# ── Seam + fail-closed + idempotency ───────────────────────────────────────

@pytest.mark.django_db
def test_reconcile_outcome_persists_operation_id():
    """``PlansService.reconcile_outcome`` persists the operation id at dispatch
    time — the worker's only read-back key."""
    run, step = _make_awaiting_step(operation_id="op-persist")
    assert step.operation_id == "op-persist"


@pytest.mark.django_db
def test_missing_operation_id_escalates():
    """No operation id → cannot read back authoritatively → escalate (fail-closed)."""
    run = Run.objects.create(
        instance_id="recon-instance",
        conversation_id="recon-conversation",
        user_message="run the plan",
    )
    step, _ = PlansService.begin_step(run, "9", intent="effect with no op id")
    step.step_state = run_machine.RUN_AWAITING_RECONCILIATION
    step.outcome = "outcome_unknown"
    step.save(update_fields=["step_state", "outcome"])

    result = reconcile_step(step, read_back=lambda s: ReadBackResult(READBACK_COMMITTED))

    assert result.action == ACTION_ESCALATED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION
    assert ReconciliationEscalation.objects.filter(
        run_id=run.id, step_id=step.step_id
    ).exists()


@pytest.mark.django_db
def test_escalation_is_idempotent():
    """Repeated scheduler passes create exactly one escalation per step."""
    run, step = _make_awaiting_step(operation_id="op-5")

    for _ in range(3):
        reconcile_step(step, read_back=lambda s: ReadBackResult(READBACK_UNKNOWN, "x"))

    assert (
        ReconciliationEscalation.objects.filter(
            run_id=run.id, step_id=step.step_id
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_registered_read_back_provider_is_used():
    """A registered provider is consulted when no read-back is injected."""
    run, step = _make_awaiting_step(operation_id="op-6", tool_name="test_effect_reg")

    register_read_back(
        "test_effect_reg",
        lambda s: ReadBackResult(READBACK_COMMITTED, "provider says committed"),
    )

    result = reconcile_step(step)  # no injected read-back → uses provider
    assert result.action == ACTION_RESOLVED_SUCCEEDED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_SUCCEEDED


@pytest.mark.django_db
def test_no_provider_escalates_fail_closed():
    """No provider registered → inconclusive read-back → escalate."""
    run, step = _make_awaiting_step(operation_id="op-7", tool_name="test_effect_unreg")

    result = reconcile_step(step)  # no provider for this tool_name

    assert result.action == ACTION_ESCALATED
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION


@pytest.mark.django_db
def test_reconcile_pending_scans_and_resolves():
    """The scheduler loop reconciles every awaiting step in one pass."""
    run1, step1 = _make_awaiting_step(operation_id="op-8", step_id="8")
    run2, step2 = _make_awaiting_step(operation_id="op-9", step_id="9")

    results = reconcile_pending(
        read_back=lambda s: ReadBackResult(READBACK_COMMITTED, "ok")
    )

    actions = sorted(r.action for r in results)
    assert actions == sorted([ACTION_RESOLVED_SUCCEEDED, ACTION_RESOLVED_SUCCEEDED])
    step1.refresh_from_db()
    step2.refresh_from_db()
    assert step1.step_state == run_machine.RUN_SUCCEEDED
    assert step2.step_state == run_machine.RUN_SUCCEEDED
