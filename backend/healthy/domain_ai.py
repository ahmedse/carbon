"""Healthy Foods Factory domain AI + AI-workspace manifest.

Registers ``healthy`` with the platform domain registry so the AI workspace
(``ai/domain_protocol.py``) can enrich the scope whenever ``scope.active_apps``
contains ``"healthy"``. No scope checks live inside this class — the registry
and the AI scoping layer apply the guards automatically (dispatch §8.6).

Mirrors ``ai/domain/emissions.py``. ``ai/domain_protocol.py`` is untouched.
"""
from __future__ import annotations

from typing import Any

from ai.domain_protocol import DomainAIOperations, DomainContext, register_domain


class HealthyDomainAI(DomainAIOperations):
    """Healthy Foods Factory domain operations + manifest."""

    app_identifier = "healthy"
    app_display_name = "Healthy Foods Factory"

    supported_task_types = ["chat", "nl_query", "anomaly", "report_draft"]

    # Manifest: entry-point buttons on domain pages.
    entry_points = [
        {"label": "Ask about this", "task_type": "chat", "on_entity": "*", "icon": "Chat"},
        {"label": "Draft load-out", "task_type": "report_draft", "on_entity": "module", "icon": "Description"},
        {"label": "Investigate anomalies", "task_type": "anomaly", "on_entity": "table", "icon": "ManageSearch"},
    ]

    # Manifest: context-aware starter chips.
    starter_prompts = {
        "table": [
            {
                "label": "Why did returns spike?",
                "prompt": "Explain the returns trend for @{entity_name} and what the rep should adjust next week.",
                "task_type": "chat",
            },
            {
                "label": "Investigate anomalies",
                "prompt": "",
                "task_type": "anomaly",
            },
        ],
        "module": [
            {
                "label": "Summarize AR health",
                "prompt": "Summarize the AR aging and slow-moving stock status for @{entity_name}. What needs attention?",
                "task_type": "chat",
            },
            {
                "label": "Draft load-out plan",
                "prompt": "",
                "task_type": "report_draft",
            },
        ],
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What questions can you answer about the Healthy Foods Factory operations data?",
                "task_type": "chat",
            },
        ],
    }

    system_prompt_extension = (
        "You are assisting with fresh-food direct-store-delivery operations. "
        "Use DSD, rep_code, loadout_sheet, and AR-aging vocabulary from the "
        "healthy domain. Always ground answers in the latest approved dataset "
        "versions and never invent customer balances or demand numbers."
    )

    default_model_id = "healthy-food-ops"

    def get_domain_context(self) -> DomainContext:
        """Static domain knowledge/config — no DB access (safe at import time)."""
        return DomainContext(
            app_identifier=self.app_identifier,
            domain_knowledge={
                "DSD": "Direct-Store-Delivery — van delivery to small shops/supermarkets.",
                "rep_code": "Sales representative identifier in the legacy ERP.",
                "loadout_sheet": "Van loading plan — how much of each item a rep should carry.",
                "churn_probability": "Modeled risk a rep will stop ordering within 4 weeks.",
                "visit_coverage": "Share of assigned customers visited in the week.",
                "AR_aging": "Accounts-receivable buckets by days overdue (30/60/90+).",
                "dead_stock": "Items with zero movement over a rolling window.",
                "freshness_sla": "Healthy datasets require freshness ≤ 7 days (168h).",
            },
            domain_config={
                "modules": [
                    "healthy-sales",
                    "healthy-returns",
                    "healthy-inventory",
                    "healthy-collections",
                    "healthy-production",
                ],
                "pipelines": [
                    "returns",
                    "churn",
                    "sales-lines",
                    "ar-aging",
                    "transaction-classifier",
                ],
                "unit_of_measure": "EGP",
                "timezone": "Africa/Cairo",
            },
        )

    def validate_task_payload(self, task_type: str, payload: dict[str, Any]) -> tuple[bool, str]:
        """Per-task payload validation for healthy domain tasks."""
        if task_type == "report_draft":
            report = (payload or {}).get("report", "")
            if not report:
                return False, "report_draft requires a 'report' key."
            return True, ""
        return True, ""


register_domain("healthy", HealthyDomainAI)
