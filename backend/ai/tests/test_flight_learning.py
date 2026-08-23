"""
Phase 25-D — Grow loop: outcome → learning + playbook (spec §3.6).

Unit tests for ``FlightDirector.enqueue_learning_from_report``:
  - each deterministic matcher fires on the right report:
      missing acceptance_criteria → "planner: always emit acceptance_criteria"
      fidelity_failures > 0      → "worker: never stop before all declared calls run"
      repaired_refs non-empty    → "planner: resolve created ids from prior step outputs"
  - apply = upsert ``PlaybookBlock(block_type="flight_director")``
    (version N+1 if exists, provenance=run.id) + mark ``LearningOutcome``
    ``applied`` with ``applied_at``.
  - dedup: a second call for the same (run, pattern) is a no-op
    (1 outcome + 1 block still).
  - terminal-status guard mirrors ``feed_run_feedback`` — non-terminal runs
    (paused/cancelled) create nothing.
  - a report with none of the three signals creates nothing.

Conventions mirror ``test_flight_models.py`` / ``test_flight_acceptance.py``:
a ``User`` + ``Run`` fixture (``host_user_id`` = owner, CBAC), engine seams
untouched.
"""
from __future__ import annotations

import uuid

import pytest

from accounts.models import User
from ai.flight_director import (
    _PATTERN_GUIDANCE,
    enqueue_learning_from_report,
)
from ai.models import LearningOutcome, PlaybookBlock
from ai.models.core import Run

PATTERN_PLANNER_CRITERIA = "planner: always emit acceptance_criteria"
PATTERN_WORKER_FIDELITY = "worker: never stop before all declared calls run"
PATTERN_PLANNER_IDS = "planner: resolve created ids from prior step outputs"

_CRITERION = {"type": "created_entity", "kind": "rule", "expect_status": 201}


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="flight-learning", password="secret123")


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


def _requirement(step_id, criterion="__unset__", verdict="met",
                 intent="Create a DQ rule"):
    """A single per-requirement result entry (``report_json.requirements``).

    ``criterion="__unset__"`` omits the key entirely (planner emitted no
    acceptance_criteria); pass ``criterion=None`` for an explicit null.
    """
    req = {"step_id": step_id, "intent": intent, "verdict": verdict}
    if criterion != "__unset__":
        req["criterion"] = criterion
    return req


def _report(requirements=None, metrics=None, supervision=None, status="met"):
    return {
        "status": status,
        "requirements": requirements if requirements is not None else [],
        "metrics": metrics or {},
        "final_response": "All requirements met.",
        "supervision": supervision or {},
    }


def _clean_metrics(fidelity_failures=0):
    return {
        "retries": 0, "rewrites": 0, "vetoes": 0, "escalations": 0,
        "fidelity_failures": fidelity_failures, "total_latency_ms": 1.0,
        "total_llm_calls": 1, "steps_total": 1, "steps_met": 1,
        "steps_partial": 0, "steps_missed": 0,
    }


# ── Matcher 1: step missing acceptance_criteria → planner pattern ───────


def test_missing_acceptance_criteria_fires_planner_pattern(run):
    """A requirement with no criterion (and an explicit null) → planner pattern."""
    report = _report(requirements=[
        _requirement(1, intent="Create a DQ rule"),
        _requirement(2, criterion=None, intent="Bind the rule to a table"),
    ])

    applied = enqueue_learning_from_report(report, run=run)

    assert [a["pattern"] for a in applied] == [PATTERN_PLANNER_CRITERIA]
    assert applied[0]["target"] == "playbook"
    assert applied[0]["applied"] is True

    outcome = LearningOutcome.objects.get(
        run=run, pattern=PATTERN_PLANNER_CRITERIA
    )
    assert outcome.target == "playbook"
    assert outcome.status == "applied"
    assert outcome.applied_at is not None
    assert outcome.payload_json["provenance"] == run.id
    assert outcome.payload_json["guidance"] == _PATTERN_GUIDANCE[PATTERN_PLANNER_CRITERIA]

    block = PlaybookBlock.objects.get(
        block_type="flight_director", title=PATTERN_PLANNER_CRITERIA
    )
    assert block.version == 1  # new block
    assert block.provenance == run.id
    assert block.content == _PATTERN_GUIDANCE[PATTERN_PLANNER_CRITERIA]


# ── Matcher 2: fidelity_failures > 0 → worker pattern ───────────────────


def test_fidelity_failures_fire_worker_pattern(run):
    """metrics.fidelity_failures > 0 → the worker fidelity pattern."""
    report = _report(
        requirements=[_requirement(1, criterion=_CRITERION)],
        metrics=_clean_metrics(fidelity_failures=2),
    )

    applied = enqueue_learning_from_report(report, run=run)

    assert [a["pattern"] for a in applied] == [PATTERN_WORKER_FIDELITY]
    outcome = LearningOutcome.objects.get(run=run, pattern=PATTERN_WORKER_FIDELITY)
    assert outcome.status == "applied"
    assert outcome.applied_at is not None
    block = PlaybookBlock.objects.get(
        block_type="flight_director", title=PATTERN_WORKER_FIDELITY
    )
    assert block.version == 1
    assert block.provenance == run.id


def test_fidelity_failures_fallback_to_flight_state(run):
    """Report metrics omit fidelity → the flight state's failures still fire."""
    report = _report(requirements=[_requirement(1, criterion=_CRITERION)])
    flight_state = {
        "ledger": [], "repairs": [], "escalations": 0,
        "fidelity": {"failures": 1, "escalated_steps": []},
        "contract": {},
    }

    applied = enqueue_learning_from_report(
        report, flight_state=flight_state, run=run
    )

    assert [a["pattern"] for a in applied] == [PATTERN_WORKER_FIDELITY]


# ── Matcher 3: repaired_refs non-empty → planner ids pattern ────────────


def test_repaired_refs_fire_planner_ids_pattern(run):
    """Non-empty repaired_refs in the flight state → planner ids pattern."""
    report = _report(
        requirements=[_requirement(1, criterion=_CRITERION)],
        metrics=_clean_metrics(fidelity_failures=0),
    )
    flight_state = {
        "ledger": [
            {"kind": "rule", "id": 129, "name": "Water consumption > 0",
             "step_index": 3}
        ],
        "repairs": [{"step": 4, "kind": "rule", "stale_id": 125,
                     "corrected_id": 129}],
        "escalations": 0,
        "fidelity": {"failures": 0, "escalated_steps": []},
        "contract": {},
    }

    applied = enqueue_learning_from_report(
        report, flight_state=flight_state, run=run
    )

    assert [a["pattern"] for a in applied] == [PATTERN_PLANNER_IDS]
    outcome = LearningOutcome.objects.get(run=run, pattern=PATTERN_PLANNER_IDS)
    assert outcome.status == "applied"
    block = PlaybookBlock.objects.get(
        block_type="flight_director", title=PATTERN_PLANNER_IDS
    )
    assert block.version == 1
    assert block.provenance == run.id


def test_repaired_refs_fallback_to_report_supervision(run):
    """No flight_state passed → report.supervision.repairs still fires."""
    report = _report(
        requirements=[_requirement(1, criterion=_CRITERION)],
        metrics=_clean_metrics(fidelity_failures=0),
        supervision={"repairs": [{"step": 4, "kind": "rule",
                                  "stale_id": 125, "corrected_id": 129}]},
    )

    applied = enqueue_learning_from_report(report, run=run)

    assert [a["pattern"] for a in applied] == [PATTERN_PLANNER_IDS]


# ── Combined: all three signals → three outcomes + three blocks ─────────


def test_all_three_signals_create_three_outcomes(run):
    """A report with all three signals produces 3 applied outcomes + 3 blocks."""
    report = _report(
        requirements=[_requirement(1, intent="Create a DQ rule")],
        metrics=_clean_metrics(fidelity_failures=1),
        supervision={"repairs": [{"step": 4, "kind": "rule",
                                  "stale_id": 125, "corrected_id": 129}]},
    )

    applied = enqueue_learning_from_report(report, run=run)

    assert {a["pattern"] for a in applied} == {
        PATTERN_PLANNER_CRITERIA,
        PATTERN_WORKER_FIDELITY,
        PATTERN_PLANNER_IDS,
    }
    assert LearningOutcome.objects.filter(run=run).count() == 3
    assert (
        LearningOutcome.objects.filter(run=run, status="applied").count() == 3
    )
    assert PlaybookBlock.objects.filter(block_type="flight_director").count() == 3


# ── Dedup: (run, pattern) unique constraint → second call is a no-op ─────


def test_second_call_same_run_pattern_is_noop(run):
    """Re-calling for the same (run, pattern) creates no new rows (idempotent)."""
    report = _report(requirements=[_requirement(1, intent="Create a DQ rule")])

    first = enqueue_learning_from_report(report, run=run)
    second = enqueue_learning_from_report(report, run=run)

    assert len(first) == 1
    assert second == []  # nothing new applied
    assert LearningOutcome.objects.filter(run=run).count() == 1
    outcome = LearningOutcome.objects.get(run=run)
    assert outcome.status == "applied"
    assert outcome.applied_at is not None
    # Block untouched by the no-op — still version 1, still provenance of run.
    block = PlaybookBlock.objects.get(
        block_type="flight_director", title=PATTERN_PLANNER_CRITERIA
    )
    assert PlaybookBlock.objects.filter(block_type="flight_director").count() == 1
    assert block.version == 1


# ── Playbook upsert: version N+1 on an existing flight_director block ────


def test_playbook_version_bump_on_existing_block(run):
    """Existing flight_director block with the same title → version N+1."""
    PlaybookBlock.objects.create(
        instance_id="carbon",
        block_type="flight_director",
        title=PATTERN_PLANNER_CRITERIA,
        content="outdated guidance",
        version=3,
        provenance="older-run-id",
    )
    report = _report(requirements=[_requirement(1, intent="Create a DQ rule")])

    applied = enqueue_learning_from_report(report, run=run)

    assert [a["pattern"] for a in applied] == [PATTERN_PLANNER_CRITERIA]
    blocks = PlaybookBlock.objects.filter(
        block_type="flight_director", title=PATTERN_PLANNER_CRITERIA
    )
    assert blocks.count() == 1  # upsert, never a duplicate row
    block = blocks.get()
    assert block.version == 4  # 3 + 1
    assert block.content == _PATTERN_GUIDANCE[PATTERN_PLANNER_CRITERIA]
    assert block.provenance == run.id
    assert block.is_active is True


# ── Terminal-status guard (mirrors feed_run_feedback) ───────────────────


@pytest.mark.parametrize("status", ["paused", "cancelled", "pending_approval"])
def test_non_terminal_run_creates_no_outcomes(user, status):
    """Non-terminal runs no-op — no outcomes, no playbook blocks."""
    run = Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Create a water consumption DQ rule",
        status=status,
        final_response=None,
    )
    report = _report(requirements=[_requirement(1, intent="Create a DQ rule")])

    applied = enqueue_learning_from_report(report, run=run)

    assert applied == []
    assert LearningOutcome.objects.filter(run=run).count() == 0
    assert PlaybookBlock.objects.filter(block_type="flight_director").count() == 0


def test_no_run_is_noop():
    """No run → no-op (never raises, nothing written)."""
    report = _report(requirements=[_requirement(1, intent="Create a DQ rule")])
    assert enqueue_learning_from_report(report) == []


# ── No signal → no learning ─────────────────────────────────────────────


def test_report_with_no_signals_creates_no_outcomes(run):
    """None of the three signals → nothing to learn, no rows written."""
    report = _report(
        requirements=[_requirement(1, criterion=_CRITERION)],
        metrics=_clean_metrics(fidelity_failures=0),
        supervision={"repairs": []},
    )
    flight_state = {
        "ledger": [{"kind": "rule", "id": 129, "name": "R", "step_index": 1}],
        "repairs": [],
        "escalations": 0,
        "fidelity": {"failures": 0, "escalated_steps": []},
        "contract": {},
    }

    applied = enqueue_learning_from_report(
        report, flight_state=flight_state, run=run
    )

    assert applied == []
    assert LearningOutcome.objects.filter(run=run).count() == 0
    assert PlaybookBlock.objects.filter(block_type="flight_director").count() == 0
