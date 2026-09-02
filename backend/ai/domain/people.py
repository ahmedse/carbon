"""Carbon AI Intelligence — People & Payroll Domain (non-data vertical).

Gap #5: a non-data operations vertical on the domain-protocol seam. People &
Payroll has typed models in its own hosted app (``people``), but those models
are NOT part of the trust platform's *data* tables — there is nothing to
isolate in ``DataIsolationGuard``. This adapter is therefore **manifest-only**:
it registers conversation types, entry points, starter chips, and a domain
prompt extension, but never touches ``DataIsolationGuard`` tables and never
imports ``people.models`` (Rule_3: sibling hosted-app imports are forbidden).

Rules honored:
  * Advisory / drafting only — chat + report drafting. The assistant never
    mutates payroll runs, payslips, leave, loans, or attendance records, and
    never fabricates figures it cannot ground (RULE_16).
  * No ``table_id``-gated task types (no DQ / NL-query / anomaly) — this is a
    typed-model vertical, not a data-table vertical; ``validate_task_payload``
    rejects ``table_id`` payloads explicitly.
  * No hardcoded statutory figures — GOSI / WPS percentages are described as
    rule-driven, never numeric constants.
"""

from __future__ import annotations

from typing import Any

from ai.adapter.types import ToolDef
from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class PeopleDomainAI(DomainAIOperations):
    """People & Payroll domain AI — advisory + drafting, no data access."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "people"
    app_display_name = "People & Payroll"

    # ── Manifest: task types ──────────────────────────────────────────────
    # Non-data vertical: only the core advisory/drafting types. No table-bound
    # types (dq_*, nl_query, anomaly, investigate) because there is no people
    # table in the trust platform's data trust.
    supported_task_types = [
        "chat",
        "report_draft",
    ]

    # ── Manifest: entry-point buttons ─────────────────────────────────────
    # Manifest-only vertical: owns no AI entity pages yet, so no page entry
    # points. AI surface = starter prompts + chat only.
    entry_points = []

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "default": [
            {
                "label": "Explain payroll reconciliation",
                "prompt": "Explain how to reconcile a net-pay figure for @{entity_name}: which payslip lines to check first.",
                "task_type": "chat",
            },
            {
                "label": "Draft a WPS/GOSI note",
                "prompt": "Draft a WPS/GOSI note for @{entity_name} (placeholder figures, clearly marked).",
                "task_type": "report_draft",
            },
            {
                "label": "What can I ask here?",
                "prompt": "What People & Payroll questions can you answer for AASTMT campus operations?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with People & Payroll operations for AASTMT. "
        "You work with the payroll run lifecycle (draft → compute → validate → "
        "commit), payslip line types (gross, gosi, loan_installment, net), "
        "GOSI employee and employer shares, the WPS (Wage Protection System) "
        "file format, leave calendar-split across periods, loan schedules, and "
        "net-pay reconciliation. "
        "Statutory details such as GOSI and WPS rates are rule-driven — describe "
        "them as rule-driven and never hardcode a percentage as a numeric "
        "constant. "
        "You are advisory and drafting only: you never change payroll, leave, "
        "loan, or attendance records, and you never present an ungrounded figure "
        "as real — mark placeholders explicitly and ask for actual figures when "
        "you do not have them."
    )

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        # People is a typed-model vertical: there is no trust-platform table to
        # scope against, so a ``table_id`` is meaningless here.
        if payload.get("table_id"):
            return False, "People is a typed-model vertical — 'table_id' is not valid here."
        if task_type == "report_draft" and not (payload.get("module_id") or payload.get("topic")):
            return False, "'report_draft' requires 'module_id' or 'topic' in task_payload."
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="people",
            domain_knowledge={
                "concepts": [
                    "payroll_run",
                    "payslip",
                    "gross",
                    "gosi",
                    "net",
                    "leave",
                    "loan_installment",
                    "attendance",
                    "certification",
                    "rotation",
                ],
                "payroll_run_lifecycle": ["draft", "compute", "validate", "commit"],
            },
            domain_config={
                "payroll_line_types": ["gross", "gosi", "loan_installment", "net"],
                "statutory": "rule-driven",
            },
        )

    # ── Tool catalog (Pulse E2) ───────────────────────────────────────────

    def get_tools(self) -> list[ToolDef]:
        """Typed-model advisory vertical — no ``call_host_api``-backed data tools."""
        return []


register_domain("people", PeopleDomainAI)