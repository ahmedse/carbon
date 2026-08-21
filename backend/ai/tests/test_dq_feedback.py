"""Phase 24-D — DQ feedback loop tests.

Covers the capture → pipeline → learning loop:

  * capture idempotency (unique ``idempotency_key``)
  * engine signal taxonomy scoring (reuses ``quality_score_for``)
  * apply effects: suggest_accepted → explicit_positive (canonical promotion),
    suggest_rejected → explicit_negative, rule_corrected → correction +
    KgGoldenPair candidate, retire candidates → ``needs_review`` flag
  * pipeline idempotency (apply twice → no duplicate ledger rows)
  * revertibility (apply → revert restores pre-apply state)
  * RULE_21 confirmation gate (pipeline never mutates DQRule)
  * org-unit scope preservation on captured events

The store seam is pinned to the Django backend (durable) via an autouse
fixture that resets the cached Store singleton before and after each test.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.models import Module
from dataschema.models import DataField, DataTable
from dq.models import DQRule, DQSuggestion
from mdm.models import OrgUnit

from ai.feedback import (
    apply_event,
    apply_pending,
    capture_drift,
    capture_result_flag,
    capture_rule_correction,
    capture_suggestion_feedback,
    confirm_review,
    pending_count,
    revert_event,
    score_for,
)
from ai.models import DqFeedbackEvent, KgFeedbackRecord, KgGoldenPair
from ai.store import reset_store


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _django_store(settings):
    settings.AI_STORE_BACKEND = "django"
    reset_store()
    yield
    reset_store()


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(
        name="Feedback Org", slug=f"fb-org-{uuid4().hex[:8]}",
        code="FB", org_type="division",
    )


@pytest.fixture
def table(org, db):
    module = Module.objects.create(name="Feedback Module", org_unit=org)
    tbl = DataTable.objects.create(
        name="fuel_log", title="Fuel Log", module=module)
    DataField.objects.create(
        data_table=tbl, name="amount", label="Amount", type="number")
    return tbl


@pytest.fixture
def suggestion(table, db):
    return DQSuggestion.objects.create(
        data_table=table,
        payload={
            "schema_version": 1, "name": "amount required", "level": "field",
            "dimension": "validity", "type": "not_null", "severity": "error",
            "active": True, "params": {},
        },
        rationale="Every fuel entry needs an amount.",
        confidence=0.9,
    )


@pytest.fixture
def rule(table, db):
    return DQRule.objects.create(
        name="amount required", rule_type="not_null", params={},
        definition={
            "schema_version": 1, "name": "amount required", "level": "field",
            "dimension": "validity", "type": "not_null", "severity": "error",
            "active": True, "params": {},
        },
    )


# ── 1. Signal taxonomy ───────────────────────────────────────────────────


def test_score_taxonomy_matches_engine():
    # User-origin signals reuse the KG engine taxonomy.
    assert score_for("suggest_accepted") == 1.0
    assert score_for("suggest_rejected") == 0.1
    assert score_for("rule_corrected") == 0.0  # correction itself scores 1.0
    # Pipeline-heuristic signals carry their own scores.
    assert score_for("result_always_pass") == 0.0
    assert score_for("result_false_positive") == 0.0
    assert score_for("drift_detected") == 0.5


# ── 2. Capture idempotency ───────────────────────────────────────────────


def test_capture_suggestion_is_idempotent(suggestion):
    e1 = capture_suggestion_feedback(suggestion, "accepted")
    e2 = capture_suggestion_feedback(suggestion, "accepted")
    assert e1.id == e2.id
    assert DqFeedbackEvent.objects.count() == 1
    assert e1.event_type == "suggest_accepted"
    assert e1.signal_type == "explicit_positive"
    assert e1.suggestion_id == suggestion.id
    assert e1.table_id == suggestion.data_table.id
    assert e1.table_name == suggestion.data_table.name


def test_capture_reject_carries_reason(suggestion):
    e = capture_suggestion_feedback(suggestion, "rejected", reason="too strict")
    assert e.event_type == "suggest_rejected"
    assert e.signal_type == "explicit_negative"
    assert e.payload["reason"] == "too strict"


def test_capture_unknown_verdict_is_noop(suggestion):
    assert capture_suggestion_feedback(suggestion, "maybe") is None
    assert DqFeedbackEvent.objects.count() == 0


def test_capture_preserves_org_scope(suggestion, org):
    e = capture_suggestion_feedback(suggestion, "accepted")
    assert e.org_unit_id == org.id


# ── 3. Pipeline effects ──────────────────────────────────────────────────


def test_apply_suggest_accepted_promotes_canonical(suggestion):
    event = capture_suggestion_feedback(suggestion, "accepted")
    assert apply_event(event) is True

    event.refresh_from_db()
    assert event.applied_at is not None
    assert event.effect["type"] == "ledger"
    assert event.effect["signal_type"] == "explicit_positive"
    assert not event.needs_review

    rec = KgFeedbackRecord.objects.get(message_id=f"dq-{event.id}")
    assert rec.signal_type == "explicit_positive"
    assert rec.quality_score == 1.0  # canonical promotion score


def test_apply_suggest_rejected_is_explicit_negative(suggestion):
    event = capture_suggestion_feedback(suggestion, "rejected")
    apply_event(event)
    rec = KgFeedbackRecord.objects.get(message_id=f"dq-{event.id}")
    assert rec.signal_type == "explicit_negative"
    assert rec.quality_score == 0.1


def test_apply_rule_corrected_creates_golden_pair(rule):
    event = capture_rule_correction(
        rule_id=rule.id, rule_name=rule.name, table_id=1, table_name="fuel_log",
        corrected_definition={
            "schema_version": 1, "name": "amount 0-1000", "level": "field",
            "dimension": "validity", "type": "range",
            "params": {"min": 0, "max": 1000},
        },
        previous_definition=rule.definition,
        correction_text="Amount must be 0..1000.",
    )
    apply_event(event)

    event.refresh_from_db()
    assert event.effect["signal_type"] == "correction"
    assert event.effect.get("golden_pair_id")

    rec = KgFeedbackRecord.objects.get(message_id=f"dq-{event.id}")
    assert rec.signal_type == "correction"
    assert rec.corrected_sql is not None

    pair = KgGoldenPair.objects.get(source_feedback_id=rec.id)
    assert pair.review_status == "pending"  # human review before use


def test_apply_retire_candidate_flags_needs_review_only(rule):
    """RULE_21: pipeline flags, never mutates production rules."""
    before = DQRule.objects.count()
    event = capture_result_flag(
        flag_type="always_pass", rule_id=rule.id, rule_name=rule.name,
        table_id=1, table_name="fuel_log", window_key="2026-08-01",
        stats={"checks": 100, "failures": 0},
    )
    apply_event(event)

    event.refresh_from_db()
    assert event.needs_review is True
    assert event.review_status == "pending"
    assert event.effect["type"] == "retire_candidate"
    # No ledger write, no rule mutation.
    assert KgFeedbackRecord.objects.filter(message_id=f"dq-{event.id}").count() == 0
    assert DQRule.objects.count() == before
    assert DQRule.objects.get(id=rule.id).is_active is True


def test_confirm_review_gate(rule):
    event = capture_result_flag(
        flag_type="false_positive", rule_id=rule.id, rule_name=rule.name,
        table_id=1, table_name="fuel_log", window_key="2026-08-02",
    )
    apply_event(event)
    confirm_review(event, reviewer="qa-user", verdict="confirmed")
    event.refresh_from_db()
    assert event.review_status == "confirmed"
    assert event.reviewed_by == "qa-user"
    assert event.reviewed_at is not None


def test_confirm_review_rejects_bad_verdict(rule):
    event = capture_result_flag(
        flag_type="always_pass", rule_id=rule.id, rule_name=rule.name,
        table_id=1, table_name="fuel_log", window_key="2026-08-03",
    )
    apply_event(event)
    with pytest.raises(ValueError):
        confirm_review(event, reviewer="qa-user", verdict="maybe")


def test_apply_drift_records_only(org, table):
    event = capture_drift(
        table_id=table.id, table_name=table.name, field_name="amount",
        detected_at="2026-08-04T00:00:00Z", details={"p95": 9999}, org_unit_id=org.id,
    )
    apply_event(event)
    event.refresh_from_db()
    assert event.applied_at is not None
    assert event.effect["type"] == "record_only"
    assert KgFeedbackRecord.objects.filter(message_id=f"dq-{event.id}").count() == 0


# ── 4. Pipeline idempotency + sweep ──────────────────────────────────────


def test_apply_is_idempotent_no_duplicate_ledger(suggestion):
    event = capture_suggestion_feedback(suggestion, "accepted")
    assert apply_event(event) is True
    assert apply_event(event) is False  # applied_at guard
    assert KgFeedbackRecord.objects.filter(message_id=f"dq-{event.id}").count() == 1


def test_apply_pending_sweep_runs_twice(suggestion):
    capture_suggestion_feedback(suggestion, "accepted")
    capture_suggestion_feedback(suggestion, "rejected")
    assert pending_count() == 2

    assert apply_pending() == 2
    assert pending_count() == 0
    assert apply_pending() == 0  # second sweep is a no-op

    events = DqFeedbackEvent.objects.all()
    for e in events:
        assert KgFeedbackRecord.objects.filter(message_id=f"dq-{e.id}").count() == 1


# ── 5. Revertibility ─────────────────────────────────────────────────────


def test_revert_restores_state(suggestion):
    event = capture_suggestion_feedback(suggestion, "accepted")
    apply_event(event)
    rec_id = KgFeedbackRecord.objects.get(message_id=f"dq-{event.id}").id

    assert revert_event(event) is True
    assert KgFeedbackRecord.objects.filter(id=rec_id).count() == 0
    event.refresh_from_db()
    assert event.applied_at is None
    assert event.effect == {}
    assert event.revert_payload == {}

    # Re-apply after revert works and re-creates the ledger row.
    assert apply_event(event) is True
    assert KgFeedbackRecord.objects.filter(message_id=f"dq-{event.id}").count() == 1


def test_revert_rule_corrected_removes_golden_pair(rule):
    event = capture_rule_correction(
        rule_id=rule.id, rule_name=rule.name, table_id=1, table_name="fuel_log",
        corrected_definition={
            "schema_version": 1, "name": "amount 0-1000", "level": "field",
            "dimension": "validity", "type": "range",
            "params": {"min": 0, "max": 1000},
        },
    )
    apply_event(event)
    event.refresh_from_db()
    pair_id = event.effect["golden_pair_id"]
    assert KgGoldenPair.objects.filter(id=pair_id).count() == 1

    revert_event(event)
    assert KgGoldenPair.objects.filter(id=pair_id).count() == 0


def test_revert_retire_candidate_clears_flag(rule):
    event = capture_result_flag(
        flag_type="always_pass", rule_id=rule.id, rule_name=rule.name,
        table_id=1, table_name="fuel_log", window_key="2026-08-05",
    )
    apply_event(event)
    assert event.needs_review is True

    revert_event(event)
    event.refresh_from_db()
    assert event.needs_review is False
    assert event.applied_at is None
