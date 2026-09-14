"""P4-05 — read-only ``inspect_case`` host tool + ``ai:inspect_case`` capability.

Covers:

  * ``ai:inspect_case`` is declared, registered, and implied by the
    operator/auditor/process-owner governance roles (no DB).
  * ``inspect_case`` returns run state, current activity, SLA, and journal
    event ids (django_db).
  * The inspection is strictly read-only — ``Run`` / ``RunStep`` /
    ``StepJournalEntry`` / ``ApprovalGrant`` counts are unchanged (django_db).
  * A missing ``ai:inspect_case`` refuses BEFORE any read (django_db).
  * An unknown run returns an error dict without raising (django_db).
  * ``ProcessRegistry.get_active_run`` bridges the engine port (django_db).

Run (from ``backend/``)::

    python -m pytest ai/tests/test_case_inspection.py -q -m "not live"
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from django.contrib.auth.models import Group

from accounts.models import ScopedRole, User
from ai.host_executor import CarbonHostExecutor
from ai.models.approval import ApprovalGrant
from ai.models.core import Run, RunStep
from ai.models.process import ProcessDefinition
from ai.models.step_journal import StepJournalEntry
from ai.registry_service import ProcessRegistry


# ── No-DB capability plumbing ───────────────────────────────────────────────


def test_inspect_case_capability_declared_and_registered():
    from accounts.capabilities import ALL_CAPABILITIES, AI_INSPECT_CASE

    assert AI_INSPECT_CASE.key == "ai:inspect_case"
    assert AI_INSPECT_CASE.key in ALL_CAPABILITIES


def test_inspect_case_implied_by_governance_roles():
    from accounts.capabilities import (
        AI_AUDITOR,
        AI_INSPECT_CASE,
        AI_OPERATOR,
        AI_PROCESS_OWNER,
        _expand_capabilities,
    )

    for role in (AI_OPERATOR, AI_AUDITOR, AI_PROCESS_OWNER):
        assert AI_INSPECT_CASE.key in _expand_capabilities({role.key})


# ── Seeding helpers ─────────────────────────────────────────────────────────


def _seed_definition(process_id: str, version: str) -> ProcessDefinition:
    return ProcessDefinition.objects.create(
        process_id=process_id,
        version=version,
        owner="process-owner",
        status="active",
        definition={
            "id": process_id,
            "version": version,
            "owner": "process-owner",
            "status": "active",
            "constraints": [
                "response(review) within 24 hours",
                "all emissions factors must be sourced",
            ],
            "policies": [
                {"refuse_if": "factor.is_active is False"},
                "reuse the latest approved factor",
            ],
            "exceptions": ["emergency factors may skip review"],
            "steps": [
                {"id": "step-0", "kind": "command", "capability": "dq.rule.validate"},
                {"id": "step-1", "kind": "command", "capability": "emissions.factor.commit"},
            ],
        },
    )


def _seed_run(user: User, run_id: str = "R-118") -> Run:
    return Run.objects.create(
        id=run_id,
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="where are we on R-118?",
        status="running",
        run_state="running",
        definition_id="proc.inspect",
        definition_version="1.0",
        plan_json={"steps": ["step-0", "step-1"]},
    )


def _seed_steps_and_journal(run_id: str) -> None:
    RunStep.objects.create(
        run_id=run_id,
        step_id="step-0",
        step_index=0,
        intent="validate factor",
        tool_name="dq.validate_rule",
        tool_args_json={},
        depends_on_json=[],
        status="completed",
        step_state="completed",
        operation_id="op-1",
        outcome="completed",
    )
    RunStep.objects.create(
        run_id=run_id,
        step_id="step-1",
        step_index=1,
        intent="commit factor",
        tool_name="emissions.factor.commit",
        tool_args_json={},
        depends_on_json=[],
        status="running",
        step_state="running",
        operation_id="op-2",
    )
    StepJournalEntry.objects.create(
        run_id=run_id,
        step_id="step-0",
        event_type="step_completed",
        sequence=1,
    )
    StepJournalEntry.objects.create(
        run_id=run_id,
        step_id="step-1",
        event_type="step_started",
        sequence=2,
    )


def _make_executor(user: User) -> CarbonHostExecutor:
    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token=f"inproc:carbon:{user.username}",
        host_user_id=str(user.pk),
    )


def _grant_inspect(user: User) -> None:
    """``ai_auditor_group`` grants ``ai:auditor``, which implies ``ai:inspect_case``."""
    group, _ = Group.objects.get_or_create(name="ai_auditor_group")
    ScopedRole.objects.create(user=user, group=group, is_active=True)


def _inspect(ex: CarbonHostExecutor, user: User, run_id: str) -> dict:
    return asyncio.run(
        ex.inspect_case_via_boundary(run_id=run_id, host_user_id=str(user.pk))
    )


# ── Boundary-backed inspection ─────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_inspect_case_returns_run_state_and_event_ids():
    user = User.objects.create_user(username="inspector", password="secret123")
    _grant_inspect(user)
    _seed_definition("proc.inspect", "1.0")
    _seed_run(user)
    _seed_steps_and_journal("R-118")

    ex = _make_executor(user)
    result = _inspect(ex, user, "R-118")

    assert result.get("run_id") == "R-118"
    assert result.get("run_state") == "running"
    assert result.get("status") == "running"
    assert result.get("process_id") == "proc.inspect"
    assert result.get("process_version") == "1.0"

    current = result.get("current_activity")
    assert current is not None
    assert current["step_state"] == "running"
    assert current["step_index"] == 1

    journal = list(StepJournalEntry.objects.filter(run_id="R-118").order_by("sequence"))
    event_ids = result.get("event_ids") or []
    assert {e["id"] for e in event_ids} == {j.id for j in journal}
    assert len(event_ids) == 2

    assert "op-1" in (result.get("operation_ids") or [])

    assert result.get("sla")
    assert result.get("sla", {}).get("constraints")
    assert result.get("applicable_sop_clause")


@pytest.mark.django_db(transaction=True)
def test_inspect_case_is_read_only():
    user = User.objects.create_user(username="reader", password="secret123")
    _grant_inspect(user)
    _seed_definition("proc.inspect", "1.0")
    _seed_run(user)
    _seed_steps_and_journal("R-118")

    before = (
        Run.objects.count(),
        RunStep.objects.count(),
        StepJournalEntry.objects.count(),
        ApprovalGrant.objects.count(),
    )

    ex = _make_executor(user)
    result = _inspect(ex, user, "R-118")

    after = (
        Run.objects.count(),
        RunStep.objects.count(),
        StepJournalEntry.objects.count(),
        ApprovalGrant.objects.count(),
    )
    assert after == before
    assert result.get("run_id") == "R-118"


@pytest.mark.django_db(transaction=True)
def test_inspect_case_requires_capability():
    user = User.objects.create_user(username="noaccess", password="secret123")
    _seed_definition("proc.inspect", "1.0")
    _seed_run(user)
    _seed_steps_and_journal("R-118")

    ex = _make_executor(user)
    result = _inspect(ex, user, "R-118")

    assert "error" in result
    assert "missing capability ai:inspect_case" in result["error"]
    assert "run_state" not in result
    assert "event_ids" not in result


@pytest.mark.django_db(transaction=True)
def test_inspect_case_unknown_run():
    user = User.objects.create_user(username="ghost", password="secret123")
    _grant_inspect(user)

    ex = _make_executor(user)
    result = _inspect(ex, user, "does-not-exist")

    assert "error" in result
    assert "run not found" in result["error"]
    assert result.get("run_id") == "does-not-exist"


@pytest.mark.django_db
def test_registry_get_active_run():
    user = User.objects.create_user(username="registry", password="secret123")
    _seed_run(user, run_id="R-118")

    record = asyncio.run(ProcessRegistry().get_active_run("R-118"))
    assert record is not None
    assert record["id"] == "R-118"
    assert record["state"] == "running"
    assert record["process_id"] == "proc.inspect"
    assert record["process_version"] == "1.0"
    assert record["context"] == {"steps": ["step-0", "step-1"]}

    assert asyncio.run(ProcessRegistry().get_active_run("nope")) is None
