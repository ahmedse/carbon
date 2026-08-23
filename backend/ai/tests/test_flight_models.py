"""
Phase 25-A — Flight Director schema (AcceptanceReport + LearningOutcome).

Model-level tests per ``docs/DESIGN-FLIGHT-DIRECTOR.md`` §2:
  - AcceptanceReport: defaults, FK cascade, ``related_name``, app_label.
  - LearningOutcome: creation defaults, (run, pattern) unique constraint
    rejects a duplicate, app_label.

Conventions mirror ``test_plans.py`` / ``test_schedule_steering.py``:
a ``User`` + ``Run`` fixture (``host_user_id`` = owner, CBAC), engine seams
untouched.
"""
from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError

from accounts.models import User
from ai.models import AcceptanceReport, LearningOutcome
from ai.models.core import Run


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="flight-models", password="secret123")


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
            "pattern": "root_cause",
            "source": "llm_decompose",
            "skill_name": None,
            "synthesis_instruction": "Summarize findings.",
            "steps": [],
        },
        final_response="All steps executed.",
    )


# ── AcceptanceReport ─────────────────────────────────────────────────────


def test_acceptance_report_defaults_and_related_name(run):
    report = AcceptanceReport.objects.create(run=run)

    assert report.id
    assert report.app_identifier == "carbon"
    assert report.status == "met"
    assert report.report_json == {}
    assert report.metrics_json == {}
    assert report.narrative == ""
    assert report.created_at is not None
    # FK related_name per spec §2
    assert list(run.acceptance_reports.all()) == [report]


def test_acceptance_report_fk_cascade(run):
    report = AcceptanceReport.objects.create(run=run, status="partial")
    report_id = report.id

    run.delete()

    assert not AcceptanceReport.objects.filter(id=report_id).exists()


# ── LearningOutcome ──────────────────────────────────────────────────────


def test_learning_outcome_created_with_defaults(run):
    outcome = LearningOutcome.objects.create(
        run=run,
        pattern="planner: always emit acceptance_criteria",
    )

    assert outcome.id
    assert outcome.app_identifier == "carbon"
    assert outcome.pattern == "planner: always emit acceptance_criteria"
    assert outcome.target == "playbook"
    assert outcome.payload_json == {}
    assert outcome.status == "queued"
    assert outcome.applied_at is None
    assert outcome.created_at is not None


def test_learning_outcome_unique_run_pattern(run):
    LearningOutcome.objects.create(
        run=run, pattern="worker: never stop before all declared calls run"
    )

    with pytest.raises(IntegrityError):
        LearningOutcome.objects.create(
            run=run, pattern="worker: never stop before all declared calls run"
        )


# ── app_label ────────────────────────────────────────────────────────────


def test_app_labels_are_ai():
    assert AcceptanceReport._meta.app_label == "ai"
    assert LearningOutcome._meta.app_label == "ai"
