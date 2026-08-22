"""Carbon AI Intelligence — Customer Operations Domain (non-data vertical).

Gap #5: a non-data operations vertical on the domain-protocol seam. Customer
ops has no tables in the trust platform, so this is a **manifest-only**
adapter — the same advisory/drafting surface as ``finance`` / ``hr`` with a
customer-service vocabulary.

Rules honored:
  * Advisory / drafting only — chat + report drafting. Never mutates records.
  * No table-bound task types; ``validate_task_payload`` rejects ``table_id``.
  * Never fabricate customer, ticket, or SLA figures (RULE_16).
"""

from __future__ import annotations

from typing import Any

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class CustomerOpsDomainAI(DomainAIOperations):
    """Customer operations domain AI — advisory + drafting, no data access."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "customer"
    app_display_name = "Customer Operations"

    # ── Manifest: task types ──────────────────────────────────────────────
    supported_task_types = [
        "chat",
        "report_draft",
    ]

    # ── Manifest: entry-point buttons ─────────────────────────────────────
    # Manifest-only vertical: owns no entity pages, so no page entry points.
    # (The old "*" / "module" entries leaked customer actions onto catalog pages.)
    # AI surface = starter prompts + chat only.
    entry_points = []

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "default": [
            {
                "label": "Explain SLA metrics",
                "prompt": "Explain how to interpret first-response and resolution SLA metrics for @{entity_name}.",
                "task_type": "chat",
            },
            {
                "label": "Draft a reply",
                "prompt": "Draft a customer reply for @{entity_name} (placeholder details clearly marked).",
                "task_type": "report_draft",
            },
            {
                "label": "What can I ask here?",
                "prompt": "What customer operations questions can you answer for AASTMT campus services?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with customer operations for AASTMT campus services. "
        "You work with the concepts of tickets, first-response time, resolution "
        "time, CSAT, and service-level agreements. "
        "You are advisory and drafting only: you never change customer records, "
        "and you never present an ungrounded figure as real — mark placeholders "
        "explicitly and ask for actual figures when you do not have them."
    )

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        if payload.get("table_id"):
            return False, "Customer ops is a non-data vertical — 'table_id' is not valid here."
        if task_type == "report_draft" and not (payload.get("module_id") or payload.get("topic")):
            return False, "'report_draft' requires 'module_id' or 'topic' in task_payload."
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="customer",
            domain_knowledge={
                "concepts": ["ticket", "first-response", "resolution", "CSAT", "SLA"],
            },
            domain_config={
                "sla_targets": {"first_response": "4 business hours", "resolution": "3 business days"},
            },
        )


register_domain("customer", CustomerOpsDomainAI)
