"""Non-data operations verticals (Gap #5) — finance / hr / customer.

Covers the manifest-only domain adapters added on the domain-protocol seam:
  - registration + lookup via ai.domain_protocol
  - identity (app_identifier / display_name)
  - supported task types (chat + report_draft only — no table-bound types)
  - payload validation (rejects ``table_id``; ``report_draft`` needs a topic)
  - DomainContext shape is non-empty
"""

from __future__ import annotations

from ai.domain.customer import CustomerOpsDomainAI
from ai.domain.finance import FinanceDomainAI
from ai.domain.hr import HRDomainAI
from ai.domain_protocol import get_domain, has_domain, list_domains


NON_DATA_DOMAINS = [
    ("finance", "Finance Operations", FinanceDomainAI),
    ("hr", "HR Operations", HRDomainAI),
    ("customer", "Customer Operations", CustomerOpsDomainAI),
]


# ── Registration & lookup ─────────────────────────────────────────────────


def test_non_data_domains_registered():
    for app_id, _display, _cls in NON_DATA_DOMAINS:
        assert has_domain(app_id) is True


def test_get_domain_returns_correct_classes():
    for app_id, _display, cls in NON_DATA_DOMAINS:
        assert get_domain(app_id) is cls


def test_list_domains_includes_non_data_verticals():
    domains = list_domains()
    for app_id, _display, _cls in NON_DATA_DOMAINS:
        assert app_id in domains


# ── Identity ──────────────────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    for app_id, display, cls in NON_DATA_DOMAINS:
        assert cls.app_identifier == app_id
        assert cls.app_display_name == display


# ── Manifest: task types stay advisory-only ───────────────────────────────


def test_supported_task_types_are_advisory_only():
    for _app_id, _display, cls in NON_DATA_DOMAINS:
        assert "chat" in cls.supported_task_types
        assert "report_draft" in cls.supported_task_types
        # No table-bound types for a non-data vertical.
        for table_type in ("dq_validate", "dq_suggest", "nl_query", "anomaly", "investigate"):
            assert table_type not in cls.supported_task_types


def test_manifest_no_leaky_entry_points_but_has_starters():
    # Manifest-only verticals own no entity pages: entry_points must stay
    # empty (the old "*" / "module" entries leaked HR/finance/customer
    # actions onto catalog pages). Their AI surface is starter prompts only.
    for _app_id, _display, cls in NON_DATA_DOMAINS:
        assert cls.entry_points == []
        assert "default" in cls.starter_prompts
        assert len(cls.starter_prompts["default"]) >= 1


# ── Payload validation ────────────────────────────────────────────────────


def test_validate_rejects_table_id():
    for _app_id, _display, cls in NON_DATA_DOMAINS:
        ok, reason = cls().validate_task_payload("chat", {"table_id": "t1"})
        assert ok is False
        assert "non-data" in reason


def test_validate_report_draft_requires_topic():
    for _app_id, _display, cls in NON_DATA_DOMAINS:
        ok, _reason = cls().validate_task_payload("report_draft", {})
        assert ok is False
        ok2, _reason2 = cls().validate_task_payload("report_draft", {"topic": "Q3"})
        assert ok2 is True


def test_validate_chat_passes_without_payload():
    for _app_id, _display, cls in NON_DATA_DOMAINS:
        ok, _reason = cls().validate_task_payload("chat", {})
        assert ok is True


# ── DomainContext ─────────────────────────────────────────────────────────


def test_domain_context_non_empty():
    for _app_id, _display, cls in NON_DATA_DOMAINS:
        ctx = cls().get_domain_context()
        assert ctx.app_identifier == cls.app_identifier
        assert ctx.domain_knowledge
        assert ctx.domain_config
