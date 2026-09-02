"""Carbon AI Intelligence — Finance Operations Domain (non-data vertical).

Gap #5: the domain-protocol seam historically only hosted *data-trust*
domains (``emissions``, ``water``, ``mdm``, ``data_product``). Finance is a
**non-data** operations vertical — there are no finance tables to isolate, so
this adapter is **manifest-only**: it registers conversation types, entry
points, starter chips, and a domain prompt extension, but never touches
``DataIsolationGuard`` tables.

Rules honored here (they are what make a non-data vertical safe):

  * Read-only / advisory only — chat + report drafting. The assistant never
    mutates ledgers, budgets, or GL data, and never fabricates figures it
    cannot ground (RULE_16).
  * No ``table_id``-gated task types (no DQ / NL-query) — there is no finance
    table to query; ``validate_task_payload`` rejects ``table_id`` payloads
    explicitly.
"""

from __future__ import annotations

from typing import Any

from ai.adapter.types import ToolDef
from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class FinanceDomainAI(DomainAIOperations):
    """Finance operations domain AI — advisory + drafting, no data access."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "finance"
    app_display_name = "Finance Operations"

    # ── Manifest: task types ──────────────────────────────────────────────
    # Non-data vertical: only the core advisory/drafting types. No table-bound
    # types (dq_*, nl_query, anomaly, investigate) because there is no finance
    # table in the trust platform.
    supported_task_types = [
        "chat",
        "report_draft",
    ]

    # ── Manifest: entry-point buttons ─────────────────────────────────────
    # Manifest-only vertical: owns no entity pages, so no page entry points.
    # (The old "*" / "module" entries leaked finance actions onto catalog pages.)
    # AI surface = starter prompts + chat only.
    entry_points = []

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "default": [
            {
                "label": "Explain budget variance",
                "prompt": "Explain how to analyze a budget variance for @{entity_name}: what drivers to isolate first.",
                "task_type": "chat",
            },
            {
                "label": "Draft a variance memo",
                "prompt": "Draft a budget variance memo for @{entity_name} (placeholder figures, clearly marked).",
                "task_type": "report_draft",
            },
            {
                "label": "What can I ask here?",
                "prompt": "What finance questions can you answer for AASTMT campus operations?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with finance operations for AASTMT. "
        "You work with the concepts of budgets, actuals, variances, cost centers, "
        "GL accounts, and accruals. "
        "You are advisory and drafting only: you never change financial records, "
        "and you never present an ungrounded figure as real — mark any placeholder "
        "number explicitly as a placeholder that the user must replace. "
        "When you are not given actual figures, say so and ask for them."
    )

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        # Finance is a non-data vertical: there is no table to scope against.
        if payload.get("table_id"):
            return False, "Finance is a non-data vertical — 'table_id' is not valid here."
        if task_type == "report_draft" and not (payload.get("module_id") or payload.get("topic")):
            return False, "'report_draft' requires 'module_id' or 'topic' in task_payload."
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="finance",
            domain_knowledge={
                "concepts": ["budget", "actuals", "variance", "accruals", "cost center"],
                "variance_formula": "(actual − budget) / budget",
                "currency": "EGP",
            },
            domain_config={
                "fiscal_year_start": "July",  # AASTMT academic/fiscal year convention
                "reporting": ["monthly", "quarterly", "annual"],
            },
        )

    # ── Tool catalog (Pulse E2) ───────────────────────────────────────────

    def get_tools(self) -> list[ToolDef]:
        """Non-data advisory vertical — no ``call_host_api``-backed data tools."""
        return []


register_domain("finance", FinanceDomainAI)
