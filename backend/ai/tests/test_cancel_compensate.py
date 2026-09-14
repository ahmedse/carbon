"""P3-11 — Cancellation semantics: ``cancel`` vs ``compensate``.

``cancel`` stops a run and starts no further work; ``compensate`` reverses
prior effects and requires its own authorization (a durable ``ApprovalGrant``
for capability ``run.compensate``). This suite proves the two semantics are
distinct, fail-closed, and auditable:

* ``cancel`` transitions a run to ``cancelled``, skips not-yet-started steps,
  runs no new effect, and is idempotent.
* ``compensate`` is refused fail-closed without its own grant; a ``cancel``
  authorization never satisfies it.
* ``compensate`` produces its own ``PolicyDecisionRow`` distinct from
  ``cancel`` and records a distinct compensation effect.

Run (from ``backend/``):

    cd backend && ../.venv/bin/python -m pytest ai/tests/test_cancel_compensate.py -q -m "not live" --create-db
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import User
from ai import run_machine
from ai.models.approval import ApprovalGrant, canonicalize_args
from ai.models.core import Run, RunStep
from ai.models.pdp import PolicyDecisionRow
from ai.plans_service import (
    CANCEL_MESSAGE,
    COMPENSATE_MESSAGE,
    PlanForbiddenError,
    PlansService,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_user(username: str) -> User:
    return User.objects.create_user(username=username, password="secret123")


def _make_run(user: User, *, status: str = "approved", run_state: str = "ready") -> Run:
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="cc-instance",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Compensate the prior import",
        status=status,
        run_state=run_state,
        plan_json={"steps": []},
    )


def _make_step(run: Run, *, step_index: int, status: str = "pending",
               step_state: str = "planned") -> RunStep:
    return RunStep.objects.create(
        run_id=run.id,
        step_index=step_index,
        intent=f"Step {step_index}",
        status=status,
        step_state=step_state,
    )


def _make_grant(run: Run, *, capability: str = "run.compensate",
                note: str = "", object_id: str | None = None,
                object_type: str | None = "plan") -> ApprovalGrant:
    return ApprovalGrant.objects.create(
        capability=capability,
        process_version="",
        capability_version="",
        canonical_args=canonicalize_args({"note": note}),
        object_revisions={},
        evidence_digest="",
        object_id=object_id if object_id is not None else str(run.id),
        object_type=object_type,
        expires_at=timezone.now() + timedelta(hours=1),
        status="active",
        granted_by="policy_owner@example.com",
    )


# ── cancel ─────────────────────────────────────────────────────────────────


def test_cancel_transitions_run_and_skips_not_started_steps():
    user = _make_user("cc-cancel")
    run = _make_run(user, status="approved", run_state="ready")
    planned = _make_step(run, step_index=0, status="pending", step_state="planned")
    ready = _make_step(run, step_index=1, status="pending", step_state="ready")
    executing = _make_step(run, step_index=2, status="running", step_state="executing")

    result = PlansService().cancel_plan(user, run.id)

    assert result["status"] == "cancelled"
    assert result["message"] == CANCEL_MESSAGE
    run.refresh_from_db()
    assert run.status == "cancelled"
    assert run.run_state == run_machine.RUN_CANCELLED

    planned.refresh_from_db()
    ready.refresh_from_db()
    executing.refresh_from_db()
    # Not-yet-started steps are skipped (never start executing afterward).
    assert planned.step_state == run_machine.RUN_CANCELLED
    assert planned.status == "skipped"
    assert ready.step_state == run_machine.RUN_CANCELLED
    assert ready.status == "skipped"
    # A step that already began is NOT re-marked or restarted.
    assert executing.step_state == run_machine.RUN_EXECUTING
    assert executing.status == "running"

    # The cancel action was authorized through the PDP (its own audit row).
    assert PolicyDecisionRow.objects.filter(
        action="cancel", stage="pdp"
    ).exists()


def test_cancel_is_idempotent():
    user = _make_user("cc-cancel-idem")
    run = _make_run(user, status="approved", run_state="ready")
    step = _make_step(run, step_index=0, status="pending", step_state="ready")

    service = PlansService()
    first = service.cancel_plan(user, run.id)
    second = service.cancel_plan(user, run.id)

    assert first["status"] == "cancelled"
    assert second["status"] == "cancelled"
    assert second["message"] == CANCEL_MESSAGE
    # The second call short-circuits before the boundary — exactly one cancel
    # authorization row is written.
    assert PolicyDecisionRow.objects.filter(action="cancel").count() == 1
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_CANCELLED
    assert step.status == "skipped"
    assert RunStep.objects.filter(run_id=run.id).count() == 1


# ── compensate ─────────────────────────────────────────────────────────────


def test_compensate_refused_without_own_grant():
    user = _make_user("cc-comp-no-grant")
    run = _make_run(user, status="failed", run_state="failed")

    service = PlansService()
    with pytest.raises(PlanForbiddenError):
        service.compensate_plan(user, run.id, note="revert the import")

    run.refresh_from_db()
    # No compensation record was written — fail-closed.
    assert not (run.working_notes or {}).get("compensation")
    # The refusal is attributed to the grant stage (not the PDP stage).
    assert PolicyDecisionRow.objects.filter(
        action="compensate", stage="grant"
    ).exists()


def test_cancel_authorization_does_not_authorize_compensate():
    user = _make_user("cc-comp-cancel-grant")
    run = _make_run(user, status="failed", run_state="failed")
    # A grant for ``run.cancel`` must never satisfy ``run.compensate``.
    _make_grant(run, capability="run.cancel", note="")

    service = PlansService()
    with pytest.raises(PlanForbiddenError):
        service.compensate_plan(user, run.id, note="revert the import")

    run.refresh_from_db()
    assert not (run.working_notes or {}).get("compensation")
    assert PolicyDecisionRow.objects.filter(
        action="compensate", stage="grant"
    ).exists()


def test_compensate_produces_distinct_pdp_row_and_record():
    user = _make_user("cc-comp-ok")
    run = _make_run(user, status="failed", run_state="failed")
    note = "revert the import"
    _make_grant(run, capability="run.compensate", note=note)

    result = PlansService().compensate_plan(user, run.id, note=note)

    assert result["message"] == COMPENSATE_MESSAGE
    compensation = result["compensation"]
    assert compensation["action"] == "compensate"
    assert compensation["status"] == "compensated"
    assert compensation["note"] == note
    assert compensation["capability"] == "run.compensate"

    run.refresh_from_db()
    assert (run.working_notes or {}).get("compensation", {}).get(
        "status"
    ) == "compensated"

    # Compensate has its own PDP authorization row — distinct from cancel.
    assert PolicyDecisionRow.objects.filter(
        action="compensate", stage="pdp"
    ).exists()
    assert not PolicyDecisionRow.objects.filter(action="cancel").exists()


def test_compensate_unreachable_via_cancel_path():
    user = _make_user("cc-comp-unreachable")
    run = _make_run(user, status="approved", run_state="ready")
    _make_step(run, step_index=0, status="pending", step_state="planned")

    service = PlansService()
    # Cancel the run — compensation must NOT be triggered by cancel.
    service.cancel_plan(user, run.id)
    run.refresh_from_db()
    assert run.status == "cancelled"
    assert not (run.working_notes or {}).get("compensation")

    # After cancel, compensate still requires its own (absent) grant.
    with pytest.raises(PlanForbiddenError):
        service.compensate_plan(user, run.id, note="revert")
    assert not (run.working_notes or {}).get("compensation")


# ── Boundary awareness (the "one door") ────────────────────────────────────


class _CountingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, command) -> dict:
        self.calls += 1
        return {"ok": True}


@pytest.mark.asyncio
async def test_boundary_cancel_requires_no_grant():
    from ai.command_boundary import Command, CommandBoundary
    from ai.pdp import PDP
    from ai.protocol import Scope

    executor = _CountingExecutor()
    boundary = CommandBoundary(
        pdp=PDP(),
        executor=executor,
        tool_catalog={
            "cancel": {"requires_grant": False, "required_capability": "run.cancel"}
        },
    )
    scope = Scope(
        user_identifier="u1", org_unit_ids=["*"], module_ids=["*"], is_superuser=True
    )
    command = Command(
        principal="u1", scope=scope, action="cancel", tool="cancel",
        objects=["run-1"], requires_confirmation=False,
    )
    outcome = await boundary.execute(command)
    assert outcome.status == "executed"
    assert executor.calls == 1


@pytest.mark.asyncio
async def test_boundary_compensate_requires_grant_fail_closed():
    from ai.command_boundary import Command, CommandBoundary
    from ai.grant import resolve_grant
    from ai.pdp import PDP
    from ai.protocol import Scope

    executor = _CountingExecutor()
    boundary = CommandBoundary(
        pdp=PDP(),
        executor=executor,
        tool_catalog={
            "compensate": {
                "requires_grant": True,
                "required_capability": "run.compensate",
            }
        },
        grant_resolver=resolve_grant,
    )
    scope = Scope(
        user_identifier="u1", org_unit_ids=["*"], module_ids=["*"], is_superuser=True
    )
    command = Command(
        principal="u1", scope=scope, action="compensate", tool="compensate",
        objects=["run-1"], requires_confirmation=True,
        confirmation_token="human:u1:run-1",
        requires_grant=True, capability="run.compensate",
        object_id="run-1", object_type="plan",
    )
    outcome = await boundary.execute(command)
    # No ApprovalGrant exists → the boundary refuses at the grant stage and the
    # executor never runs.
    assert outcome.status == "refused"
    assert "grant" in (outcome.error or "")
    assert executor.calls == 0
