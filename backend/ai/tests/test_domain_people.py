"""People & Payroll operations vertical (Gap #5) — manifest-only adapter.

Covers the people domain adapter added on the domain-protocol seam:
  - registration + lookup via ai.domain_protocol
  - identity (app_identifier / display_name)
  - supported task types (chat + report_draft only — no table-bound types)
  - payload validation (rejects ``table_id``; ``report_draft`` needs a topic)
  - DomainContext shape is non-empty
"""

from __future__ import annotations

from ai.domain.people import PeopleDomainAI
from ai.domain_protocol import get_domain, has_domain, list_domains


# ── Registration & lookup ─────────────────────────────────────────────────


def test_people_domain_registered():
    assert has_domain("people") is True


def test_get_domain_returns_correct_class():
    assert get_domain("people") is PeopleDomainAI


def test_list_domains_includes_people():
    assert "people" in list_domains()


# ── Identity ──────────────────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    assert PeopleDomainAI.app_identifier == "people"
    assert PeopleDomainAI.app_display_name == "People & Payroll"


# ── Manifest: task types stay advisory-only ───────────────────────────────


def test_supported_task_types_are_advisory_only():
    assert "chat" in PeopleDomainAI.supported_task_types
    assert "report_draft" in PeopleDomainAI.supported_task_types
    # No table-bound types for a non-data vertical.
    for table_type in ("dq_validate", "dq_suggest", "nl_query", "anomaly", "investigate"):
        assert table_type not in PeopleDomainAI.supported_task_types


def test_manifest_no_leaky_entry_points_but_has_starters():
    # Manifest-only vertical owns no AI entity pages: entry_points must stay
    # empty. Its AI surface is starter prompts only.
    assert PeopleDomainAI.entry_points == []
    assert "default" in PeopleDomainAI.starter_prompts
    assert len(PeopleDomainAI.starter_prompts["default"]) >= 1


# ── Payload validation ────────────────────────────────────────────────────


def test_validate_rejects_table_id():
    ok, reason = PeopleDomainAI().validate_task_payload("chat", {"table_id": "t1"})
    assert ok is False
    assert "table_id" in reason or "typed-model" in reason


def test_validate_report_draft_requires_topic():
    ok, _reason = PeopleDomainAI().validate_task_payload("report_draft", {})
    assert ok is False
    ok2, _reason2 = PeopleDomainAI().validate_task_payload("report_draft", {"topic": "Aug"})
    assert ok2 is True


def test_validate_chat_passes_without_payload():
    ok, _reason = PeopleDomainAI().validate_task_payload("chat", {})
    assert ok is True


# ── DomainContext ─────────────────────────────────────────────────────────


def test_domain_context_non_empty():
    ctx = PeopleDomainAI().get_domain_context()
    assert ctx.app_identifier == "people"
    assert ctx.domain_knowledge
    assert ctx.domain_config
