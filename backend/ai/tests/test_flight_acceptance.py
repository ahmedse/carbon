"""
Phase 25-C — acceptance checks + repair loop + report closure: unit tests.

Per ``docs/DESIGN-FLIGHT-DIRECTOR.md`` §3.4–§3.6:
  - ``created_entity`` criterion is met via read-only host re-queries
    (evidence = query + matched rows).
  - ``table_fields`` asserts the EXACT field set the brief demanded; a
    mismatch → ``partial`` with the actual ``missing``/``extra`` diff.
  - repair loop: ``missed`` → repair instructions with the ACTUAL diff →
    re-execute non-mutation steps → bounded by
    ``AI_FLIGHT_DIRECTOR_MAX_REPAIRS`` → escalate + ``escalations`` metric.
  - mutation steps are NEVER auto re-run (RULE_21) — their misses surface.
  - ``build_acceptance_report`` writes the durable ``AcceptanceReport`` row
    idempotently (re-closure updates, never duplicates).

Conventions mirror ``test_flight_director.py`` / ``test_flight_models.py``:
fake host executors for async unit paths; ``async_to_sync`` for the report
closure paths that need a real ``Run`` row.
"""
from __future__ import annotations

import uuid

import pytest
from asgiref.sync import async_to_sync

from accounts.models import User
from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.flight_director import (
    FlightDirector,
    WorkingMemoryLedger,
    _overall_status,
)
from ai.models.core import AcceptanceReport, Run, RunArtifact


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="flight-acceptance", password="secret123"
    )


@pytest.fixture
def run(user):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Create a water consumption DQ rule",
        status="completed",
        plan_json={
            "pattern": "custom",
            "source": "custom",
            "skill_name": None,
            "synthesis_instruction": "Summarize findings.",
            "steps": [],
        },
        final_response="All requirements met.",
    )


class _FakeExecutor:
    """Read-only host executor double: rules list + table detail."""

    def __init__(self, rules=None, tables=None, table_fields=None):
        self.rules = rules or []
        self.tables = tables or []
        # table_id (str) -> [field names]
        self.table_fields = table_fields or {}
        self.get_calls: list[tuple[str, str, dict]] = []

    async def _call_api(self, method, endpoint, params=None, body=None):
        self.get_calls.append((method, endpoint, params))
        ep = endpoint or ""
        if "dq/rules" in ep:
            return {"status_code": 200, "data": {"results": self.rules}}
        if "tables/detail" in ep:
            tid = str((params or {}).get("id") or "")
            if tid not in self.table_fields:
                return {"status_code": 404, "data": {"detail": "Table not found"}}
            return {
                "status_code": 200,
                "data": {
                    "id": tid,
                    "name": "water_table",
                    "fields": [{"name": n} for n in self.table_fields[tid]],
                },
            }
        if "tables" in ep:
            return {"status_code": 200, "data": {"results": self.tables}}
        return {"status_code": 200, "data": {"results": []}}


def _step(step_id, intent, tool_name="call_host_api", tool_args=None,
          is_mutation=False):
    return PlanStep(
        step_id=step_id,
        intent=intent,
        tool_name=tool_name,
        tool_args=tool_args or {},
        depends_on=[],
        is_mutation=is_mutation,
    )


def _plan(*steps):
    return Plan(
        pattern="custom",
        source="custom",
        skill_name=None,
        synthesis_instruction="Summarize findings.",
        steps=list(steps),
    )


# ── created_entity: host re-query evidence ───────────────────────────────


@pytest.mark.asyncio
async def test_created_entity_criterion_met_with_requery_evidence():
    """Ledger rule id exists on the host → met, evidence = query + matches."""
    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    step = _step(
        1, "Create a DQ rule 'Water consumption > 0'",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}},
    )
    plan = _plan(step)
    executor = _FakeExecutor(rules=[{"id": 129, "name": "Water consumption > 0"}])

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor, step_statuses={1: "completed"}
    )

    assert len(results) == 1
    r = results[0]
    assert r["step_id"] == 1
    assert r["criterion"]["type"] == "created_entity"
    assert r["verdict"] == "met"
    assert r["evidence"]["query"] == "GET /carbon-api/dq/rules/"
    assert r["evidence"]["matches"] == [
        {"id": 129, "name": "Water consumption > 0"}
    ]
    assert r["repairs"] == []
    assert r["escalated"] is False
    # The host list endpoint really was re-queried (fresh evidence).
    assert ("GET", "/carbon-api/dq/rules/", {}) in executor.get_calls


@pytest.mark.asyncio
async def test_created_entity_criterion_missed_when_absent_on_host():
    """Ledger id not on the host → missed (surfaces, never assumed met)."""
    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    step = _step(
        1, "Create a DQ rule 'Water consumption > 0'",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}},
    )
    plan = _plan(step)
    executor = _FakeExecutor(rules=[])

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor, step_statuses={1: "completed"}
    )

    assert results[0]["verdict"] == "missed"
    assert results[0]["evidence"]["matches"] == []


# ── table_fields: EXACT field set (water lesson) ─────────────────────────


@pytest.mark.asyncio
async def test_table_fields_exact_set_mismatch_partial_with_diff():
    """4 planned fields, 3 actual → partial with the real missing/extra diff."""
    fd = FlightDirector()
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)
    step = _step(
        0, "Create a water consumption table with 4 fields",
        tool_args={
            "api_name": "create_table",
            "body": {
                "fields": [
                    {"name": "period", "type": "string"},
                    {"name": "volume_m3", "type": "number"},
                    {"name": "source", "type": "string"},
                    {"name": "owner", "type": "string"},
                ]
            },
        },
    )
    plan = _plan(step)
    executor = _FakeExecutor(
        table_fields={"100": ["period", "volume_m3", "source"]}
    )

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor, step_statuses={0: "completed"}
    )

    assert len(results) == 1
    r = results[0]
    assert r["criterion"]["type"] == "table_fields"
    assert r["verdict"] == "partial"
    assert r["evidence"]["diff"]["missing"] == ["owner"]
    assert r["evidence"]["diff"]["extra"] == []
    assert r["evidence"]["diff"]["table_id"] == 100


@pytest.mark.asyncio
async def test_table_fields_exact_set_met_when_fields_match():
    """Exact field set (no missing, no extra) → met, empty diff."""
    fd = FlightDirector()
    fd.ledger.add("table", 100, name="Water consumption", step_index=0)
    step = _step(
        0, "Create a water consumption table",
        tool_args={
            "api_name": "create_table",
            "body": {
                "fields": [
                    {"name": "period", "type": "string"},
                    {"name": "volume_m3", "type": "number"},
                ]
            },
        },
    )
    plan = _plan(step)
    executor = _FakeExecutor(table_fields={"100": ["period", "volume_m3"]})

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor, step_statuses={0: "completed"}
    )

    r = results[0]
    assert r["verdict"] == "met"
    assert r["evidence"]["diff"] == {
        "missing": [], "extra": [], "table_id": 100
    }


# ── Repair loop ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_repair_succeeds_within_2_attempts():
    """Missed rule → repair instructions → runner heals host → met, no escalation."""
    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    step = _step(
        1, "Create a DQ rule 'Water consumption > 0'",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}},
    )
    plan = _plan(step)
    executor = _FakeExecutor(rules=[])

    async def runner(step, criterion, instructions):
        # First repair attempt creates the rule on the host.
        executor.rules.append({"id": 129, "name": "Water consumption > 0"})
        return {"ok": True, "created": 129}

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor,
        step_statuses={1: "completed"}, step_runner=runner,
    )

    r = results[0]
    assert r["verdict"] == "met"
    assert len(r["repairs"]) == 1
    assert "no matching rule" in r["repairs"][0]["instructions"]
    assert r["escalated"] is False
    assert fd.escalations == 0


@pytest.mark.asyncio
async def test_repair_exhausts_max_attempts_and_escalates():
    """Runner never heals → repair attempts bounded, escalated, verdict partial."""
    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    step = _step(
        1, "Create a DQ rule 'Water consumption > 0'",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}},
    )
    plan = _plan(step)
    executor = _FakeExecutor(rules=[])
    calls = []

    async def runner(step, criterion, instructions):
        calls.append(instructions)
        return {"ok": False, "error": "still missing"}

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor,
        step_statuses={1: "completed"}, step_runner=runner,
    )

    r = results[0]
    assert r["verdict"] == "partial"
    assert r["escalated"] is True
    assert len(r["repairs"]) == 2  # AI_FLIGHT_DIRECTOR_MAX_REPAIRS default
    assert len(calls) == 2
    assert fd.escalations == 1
    assert fd.escalated_steps == [1]


@pytest.mark.asyncio
async def test_mutation_step_never_auto_rerun_rule21():
    """A mutation step's miss surfaces as ``missed`` — the runner is NEVER called."""
    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    step = _step(
        1, "Create a DQ rule 'Water consumption > 0'",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}},
        is_mutation=True,
    )
    plan = _plan(step)
    executor = _FakeExecutor(rules=[])
    calls = []

    async def runner(step, criterion, instructions):
        calls.append(instructions)
        return {"ok": True}

    results = await fd.run_acceptance_checks(
        plan, None, fd.ledger, executor,
        step_statuses={1: "completed"}, step_runner=runner,
    )

    r = results[0]
    assert r["verdict"] == "missed"   # surfaces for human review — never fixed
    assert r["escalated"] is False
    assert calls == []                # RULE_21 — runner never invoked
    assert fd.escalations == 0


# ── Report closure (django_db) ───────────────────────────────────────────


def test_repair_exhausted_run_reports_escalation_metric(run):
    """Escalated miss → durable report status partial + escalations metric."""
    from django.test import override_settings

    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="Water consumption > 0", step_index=1)
    step = _step(
        1, "Create a DQ rule 'Water consumption > 0'",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "R"}},
    )
    plan = _plan(step)
    executor = _FakeExecutor(rules=[])

    async def runner(step, criterion, instructions):
        return {"ok": False, "error": "still missing"}

    with override_settings(AI_FLIGHT_DIRECTOR_MAX_REPAIRS=2):
        results = async_to_sync(fd.run_acceptance_checks)(
            plan, run, fd.ledger, executor,
            step_statuses={1: "completed"}, step_runner=runner,
        )
    metrics = {"escalations": fd.escalations, "retries": 0, "rewrites": 0,
               "vetoes": 0, "fidelity_failures": 0, "total_latency_ms": 1.0,
               "total_llm_calls": 1, "steps_total": 1, "steps_met": 0,
               "steps_partial": 1, "steps_missed": 0}
    report = fd.build_acceptance_report(run, results, metrics)

    assert report["status"] == "partial"
    assert report["requirements"][0]["escalated"] is True
    row = AcceptanceReport.objects.get(run_id=run.id)
    assert row.status == "partial"
    assert row.metrics_json["escalations"] == 1
    assert row.narrative == "All requirements met."
    # Outcome summary appended to the flight supervision state.
    flight = (run.working_notes or {}).get("flight") or {}
    assert flight["acceptance"]["status"] == "partial"
    assert flight["acceptance"]["requirements_missed"] == 0


def test_build_acceptance_report_idempotent_per_run(run):
    """Re-closure updates the same row — never duplicates (spec §3.6)."""
    fd = FlightDirector()
    step = _step(1, "Create a DQ rule", tool_args={"api_name": "create_dq_rule"})
    plan = _plan(step)
    executor = _FakeExecutor(rules=[{"id": 1, "name": "R"}])
    fd.ledger.add("rule", 1, name="R", step_index=1)

    results = async_to_sync(fd.run_acceptance_checks)(
        plan, run, fd.ledger, executor, step_statuses={1: "completed"}
    )
    metrics = {"retries": 0, "rewrites": 0, "vetoes": 0, "escalations": 0,
               "fidelity_failures": 0, "total_latency_ms": 1.0,
               "total_llm_calls": 1, "steps_total": 1, "steps_met": 1,
               "steps_partial": 0, "steps_missed": 0}
    fd.build_acceptance_report(run, results, metrics)
    fd.build_acceptance_report(run, results, metrics)  # re-closure

    assert AcceptanceReport.objects.filter(run_id=run.id).count() == 1


def test_artifact_criterion_met_from_durable_run_artifact(run):
    """artifact criterion → met when the run has a durable RunArtifact row."""
    RunArtifact.objects.create(
        run=run, step_index=1, name="report.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    fd = FlightDirector()
    step = _step(1, "Export the water report", tool_name="export_document")
    plan = _plan(step)

    results = async_to_sync(fd.run_acceptance_checks)(
        plan, run, fd.ledger, _FakeExecutor(), step_statuses={1: "completed"}
    )

    r = results[0]
    assert r["criterion"]["type"] == "artifact"
    assert r["verdict"] == "met"
    assert r["evidence"]["matches"][0]["name"] == "report.docx"


def test_reasoning_step_has_no_requirement(run):
    """Reasoning steps (no tool) produce no acceptance requirement."""
    fd = FlightDirector()
    step = PlanStep(step_id=1, intent="Decide the next action", tool_name=None)
    plan = _plan(step)

    results = async_to_sync(fd.run_acceptance_checks)(
        plan, run, fd.ledger, _FakeExecutor(), step_statuses={1: "completed"}
    )

    assert results == []


def test_skipped_step_is_excluded_from_acceptance(run):
    """A user-declined (skipped) step never counts as an acceptance miss."""
    fd = FlightDirector()
    fd.ledger.add("rule", 129, name="R", step_index=1)
    step = _step(1, "Create a DQ rule", tool_args={"api_name": "create_dq_rule"})
    plan = _plan(step)

    results = async_to_sync(fd.run_acceptance_checks)(
        plan, run, fd.ledger, _FakeExecutor(rules=[]),
        step_statuses={1: "skipped"},
    )

    assert results == []


# ── overall status derivation ────────────────────────────────────────────


def test_overall_status_derivation():
    assert _overall_status([]) == "met"
    assert _overall_status([
        {"verdict": "met"}, {"verdict": "met"},
    ]) == "met"
    assert _overall_status([
        {"verdict": "met"}, {"verdict": "partial"},
    ]) == "partial"
    assert _overall_status([
        {"verdict": "met"}, {"verdict": "missed"},
    ]) == "missed"
    # partial takes precedence over missed (repaired/exhausted surfaced as partial)
    assert _overall_status([
        {"verdict": "missed"}, {"verdict": "partial"},
    ]) == "partial"
