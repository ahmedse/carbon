"""P3-04 — Process-owner interview kit tests.

Covers the acceptance criteria:
  * the kit lists the four pilot topics (from the domain-pack question bank)
  * ``record_answers`` merges answers into the definition fields AND persists
    durable provenance (who / when) in ``ProcessInterview.answers``
  * an invalid merged definition is rejected (nothing saved)
  * ``sign_definition`` records ``signed_by`` / ``signed_at`` / digest
  * provenance survives a re-fetch (durable, not in-memory)

All tests are synchronous and use the real pack (``dq.rule.release`` pilot) so
``validate_definition`` resolves the step capabilities through the P3-01 loader.
"""
from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from ai.engine.ports.domain import load_domain_pack
from ai.models.capability import default_pack_dir
from ai.models.process import ProcessDefinition
from ai.models.process_interview import STATUS_SIGNED, ProcessInterview
from ai.process_interview import (
    build_interview_kit,
    load_questions,
    record_answers,
    sign_definition,
)

PACK_DIR = default_pack_dir()

QUESTION_IDS = {
    "emergency_waivers",
    "approval_validity_after_edit",
    "reconciliation_owner",
    "sla",
}


def _pilot_doc() -> dict:
    pack = load_domain_pack(PACK_DIR)
    doc = next(p for p in pack.processes() if p.get("id") == "dq.rule.release")
    return dict(doc)


def _seed(process_id: str) -> ProcessDefinition:
    """Persist a valid definition (the pilot doc) under a unique process id."""
    doc = _pilot_doc()
    doc["id"] = process_id
    pd = ProcessDefinition.from_document(doc)
    pd.save()
    return pd


@pytest.mark.django_db
def test_kit_lists_four_pilot_topics():
    _seed("interview.kit")

    questions = load_questions()
    assert {q["id"] for q in questions} == QUESTION_IDS
    assert all(q.get("field") for q in questions)

    kit = build_interview_kit("interview.kit")
    assert {q["id"] for q in kit["questions"]} == QUESTION_IDS
    assert kit["definition"] is not None
    assert kit["definition"]["id"] == "interview.kit"


@pytest.mark.django_db
def test_record_answers_merges_fields_and_persists_provenance():
    _seed("interview.merge")

    result = record_answers(
        "interview.merge",
        {
            "sla": "review within 2 business days",
            "reconciliation_owner": "alice@example.com",
            "approval_validity_after_edit": "re-approval required after any edit",
            "emergency_waivers": ["severe-outage"],
        },
        answered_by="bob",
    )

    doc = result["definition"]
    assert doc["constraints"]["sla"] == "review within 2 business days"
    assert doc["owner"] == "alice@example.com"
    assert doc["scope"]["approval_validity"] == "re-approval required after any edit"
    assert doc["exceptions"] == ["severe-outage"]

    # durable provenance (who / when), not just the merged fields
    row = ProcessInterview.objects.get(process_id="interview.merge")
    assert len(row.answers) == 4
    by_id = {r["question_id"]: r for r in row.answers}
    assert by_id["sla"]["answer"] == "review within 2 business days"
    assert by_id["sla"]["answered_by"] == "bob"
    assert by_id["sla"]["answered_at"]

    # the definition row itself is updated
    persisted = ProcessDefinition.objects.get(process_id="interview.merge")
    assert persisted.definition["owner"] == "alice@example.com"
    assert persisted.owner == "alice@example.com"


@pytest.mark.django_db
def test_invalid_merge_is_rejected_without_saving():
    _seed("interview.invalid")

    with pytest.raises(ValidationError):
        # empty owner makes the merged definition fail the required-field check
        record_answers(
            "interview.invalid",
            {"reconciliation_owner": ""},
            answered_by="bob",
        )

    # nothing was persisted: definition still has the original owner
    persisted = ProcessDefinition.objects.get(process_id="interview.invalid")
    assert persisted.owner == _pilot_doc()["owner"]
    assert not ProcessInterview.objects.filter(process_id="interview.invalid").exists()


@pytest.mark.django_db
def test_sign_records_signature():
    _seed("interview.sign")

    result = sign_definition("interview.sign", "alice@example.com")

    assert result["signed_by"] == "alice@example.com"
    assert result["signed_at"]
    assert result["signature_digest"]
    assert result["status"] == STATUS_SIGNED

    row = ProcessInterview.objects.get(process_id="interview.sign")
    assert row.status == STATUS_SIGNED
    assert row.signed_by == "alice@example.com"
    assert row.signed_at is not None
    assert row.signature_digest == result["signature_digest"]


@pytest.mark.django_db
def test_provenance_durable_across_refetch():
    _seed("interview.durable")

    record_answers(
        "interview.durable",
        {"sla": "48h"},
        answered_by="bob",
    )

    # a fresh fetch (new query, no shared in-memory object) still sees provenance
    kit = build_interview_kit("interview.durable")
    interview = kit["interview"]
    assert interview is not None
    assert interview["status"] == "open"
    assert any(
        r["question_id"] == "sla" and r["answered_by"] == "bob" and r["answer"] == "48h"
        for r in interview["answers"]
    )
