"""P3-07a — Durable run machine tests (all sync, django_db).

Covers the closed state-transition table (property test), idempotent
``begin_step``, write-once definition-version pinning, kill-switch preflight,
PDP authorization re-check, and the ``outcome_unknown →
awaiting_reconciliation`` route. Run with::

    cd backend && python -m pytest ai/tests/test_run_machine.py -q -m "not live" --create-db
"""

from __future__ import annotations

import pytest

from accounts.models import User
from ai import run_machine
from ai.models.core import Run, RunStep
from ai.models.process import ProcessDefinition
from ai.plans_service import PlansService
from ai.registry_service import ProcessRegistry


def _make_run(user: User | None = None, **kwargs) -> Run:
    return Run.objects.create(
        instance_id="rm-instance",
        conversation_id="rm-conversation",
        user_message="run the plan",
        host_user_id=str(user.pk) if user is not None else None,
        **kwargs,
    )


# ── State-transition property tests ─────────────────────────────────────────

@pytest.mark.django_db
def test_transition_table_is_closed():
    """Every (current, target) pair not in the table is rejected; every pair
    in the table is accepted. Terminal states have no outgoing edges."""
    for kind, table in (
        ("run", run_machine.RUN_TRANSITIONS),
        ("step", run_machine.STEP_TRANSITIONS),
    ):
        states = sorted(run_machine.RUN_STATES)
        # Table keys are exactly the known states.
        assert set(table.keys()) == set(run_machine.RUN_STATES), kind
        for current in states:
            for target in states:
                expected = target in table.get(current, frozenset())
                assert run_machine.can_transition(current, target, kind=kind) is expected, (
                    f"{kind}: {current!r}→{target!r} expected {expected}"
                )
        # Terminal states have no outgoing edges.
        for terminal in run_machine.TERMINAL_STATES:
            assert table.get(terminal, frozenset()) == frozenset(), (kind, terminal)


@pytest.mark.django_db
def test_allowed_targets_matches_table():
    for kind, table in (
        ("run", run_machine.RUN_TRANSITIONS),
        ("step", run_machine.STEP_TRANSITIONS),
    ):
        for current in run_machine.RUN_STATES:
            assert run_machine.allowed_targets(current, kind=kind) == table.get(
                current, frozenset()
            ), (kind, current)


@pytest.mark.django_db
def test_illegal_transitions_rejected():
    with pytest.raises(run_machine.InvalidStateTransition):
        run_machine.assert_transition("succeeded", "executing")
    with pytest.raises(run_machine.InvalidStateTransition):
        run_machine.assert_transition("cancelled", "planned")
    # Steps cannot jump straight from executing to awaiting_reconciliation.
    with pytest.raises(run_machine.InvalidStateTransition):
        run_machine.assert_transition(
            "executing", "awaiting_reconciliation", kind="step"
        )


@pytest.mark.django_db
def test_legal_linear_chain():
    chain = ["planned", "awaiting_approval", "ready", "executing", "succeeded"]
    for current, target in zip(chain, chain[1:]):
        assert run_machine.can_transition(current, target, kind="run"), (
            current,
            target,
        )


# ── Durable model + service integration ────────────────────────────────────

@pytest.mark.django_db
def test_begin_step_is_idempotent():
    user = User.objects.create_user(username="rm-begin", password="secret123")
    run = _make_run(user)

    first, created_first = PlansService.begin_step(run, "5", intent="export report")
    second, created_second = PlansService.begin_step(run, "5", intent="export report")

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert first.step_state == run_machine.RUN_PLANNED
    # Exactly one row keyed on (run_id, step_id) — no duplicate, no re-run.
    assert RunStep.objects.filter(run_id=run.id, step_id="5").count() == 1


@pytest.mark.django_db
def test_definition_version_pin_write_once():
    run = _make_run()
    assert run.definition_version == ""
    assert run.definition_id == ""

    assert run.pin_definition_version("v1") is True
    assert run.definition_version == "v1"
    # Second write is refused — version is immutable after first set.
    assert run.pin_definition_version("v2") is False
    assert run.definition_version == "v1"

    run.pin_definition("proc-1", "v3")
    assert run.definition_id == "proc-1"
    assert run.definition_version == "v1"  # version already pinned wins
    run.pin_definition("proc-2", "v4")
    assert run.definition_id == "proc-1"  # id is also write-once


@pytest.mark.django_db
def test_advance_step_rejects_illegal_transition():
    user = User.objects.create_user(username="rm-advance", password="secret123")
    run = _make_run(user)
    step, _ = PlansService.begin_step(run, "1", intent="do work")

    PlansService.advance_step(step, run_machine.RUN_READY)
    PlansService.advance_step(step, run_machine.RUN_EXECUTING)
    PlansService.advance_step(
        step, run_machine.RUN_SUCCEEDED, outcome="succeeded"
    )
    assert step.step_state == run_machine.RUN_SUCCEEDED

    with pytest.raises(run_machine.InvalidStateTransition):
        PlansService.advance_step(step, run_machine.RUN_EXECUTING)


@pytest.mark.django_db
def test_outcome_unknown_routes_to_awaiting_reconciliation():
    user = User.objects.create_user(username="rm-reconcile", password="secret123")
    run = _make_run(user)
    step, _ = PlansService.begin_step(run, "1", intent="read-back")

    PlansService.advance_step(step, run_machine.RUN_READY)
    PlansService.advance_step(step, run_machine.RUN_EXECUTING)
    PlansService.reconcile_outcome(step)
    step.refresh_from_db()

    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION
    assert step.outcome == "outcome_unknown"

    # Idempotent — a second call is a no-op.
    PlansService.reconcile_outcome(step)
    step.refresh_from_db()
    assert step.step_state == run_machine.RUN_AWAITING_RECONCILIATION


@pytest.mark.django_db
def test_run_state_transition_via_machine():
    run = _make_run()
    run_machine.transition(run, run_machine.RUN_AWAITING_APPROVAL, kind="run", field="run_state")
    assert run.run_state == run_machine.RUN_AWAITING_APPROVAL
    run.save(update_fields=["run_state", "updated_at"])
    run.refresh_from_db()
    assert run.run_state == run_machine.RUN_AWAITING_APPROVAL

    with pytest.raises(run_machine.InvalidStateTransition):
        run_machine.transition(run, run_machine.RUN_SUCCEEDED, kind="run", field="run_state")


# ── Preflight: kill switch + authorization re-check ────────────────────────

@pytest.mark.django_db
def test_kill_switch_preflight_blocks_effect():
    user = User.objects.create_user(username="rm-owner", password="secret123")
    operator = User.objects.create_superuser(username="rm-operator", password="secret123")

    ProcessDefinition.objects.create(
        process_id="proc.killswitch",
        version="v1",
        owner="rm-owner",
        status="active",
        definition={
            "id": "proc.killswitch",
            "version": "v1",
            "owner": "rm-owner",
            "status": "active",
            "steps": [],
            "kill_switch": False,
        },
    )
    run = _make_run(user, definition_id="proc.killswitch")

    # No kill switch: allowed (with a high autonomy dial so the PDP permits).
    result = PlansService.preflight(run, action="run", autonomy="auto")
    assert result["allowed"] is True

    # Flip the kill switch through the real registry path.
    ProcessRegistry().set_kill_switch("proc.killswitch", True, operator)
    assert ProcessRegistry().is_killed("proc.killswitch") is True

    result = PlansService.preflight(run, action="run", autonomy="auto")
    assert result["allowed"] is False
    assert result["decision"] == "refuse"
    run.refresh_from_db()
    assert run.kill_switched_at is not None

    # Disabling the kill switch unblocks (subject to the PDP).
    ProcessRegistry().set_kill_switch("proc.killswitch", False, operator)
    result = PlansService.preflight(run, action="run", autonomy="auto")
    assert result["allowed"] is True


@pytest.mark.django_db
def test_preflight_rechecks_authorization():
    user = User.objects.create_user(username="rm-auth", password="secret123")
    run = _make_run(user)

    # "auto" autonomy dial → mutating action is ALLOWed.
    result = PlansService.preflight(run, action="run", autonomy="auto")
    assert result["allowed"] is True
    assert result["decision"] == "allow"

    # "human_only" dial → mutating action is ASK (blocked pre-effect).
    result = PlansService.preflight(run, action="run", autonomy="human_only")
    assert result["allowed"] is False
    assert result["decision"] == "ask"
