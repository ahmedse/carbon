"""Carbon AI Intelligence — HR Operations Domain (non-data vertical).

Gap #5: a non-data operations vertical on the domain-protocol seam. HR has no
tables in the trust platform, so this is a **manifest-only** adapter — the same
advisory/drafting surface as ``finance`` with an HR vocabulary.

Rules honored:
  * Advisory / drafting only — chat + report drafting. Never mutates records.
  * No table-bound task types; ``validate_task_payload`` rejects ``table_id``.
  * Never fabricate headcount, attrition, or payroll figures (RULE_16).
"""

from __future__ import annotations

from typing import Any

from ai.adapter.types import ToolDef
from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class HRDomainAI(DomainAIOperations):
    """HR operations domain AI — advisory + drafting, no data access."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "hr"
    app_display_name = "HR Operations"

    # ── Manifest: task types ──────────────────────────────────────────────
    supported_task_types = [
        "chat",
        "report_draft",
    ]

    # ── Manifest: entry-point buttons ─────────────────────────────────────
    # Manifest-only vertical: owns no entity pages, so no page entry points.
    # (The old "*" / "module" entries leaked HR actions onto catalog pages.)
    # AI surface = starter prompts + chat only.
    entry_points = []

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "default": [
            {
                "label": "Explain attrition",
                "prompt": "Explain how to interpret attrition for @{entity_name} and which drivers to separate.",
                "task_type": "chat",
            },
            {
                "label": "Draft a policy note",
                "prompt": "Draft a short HR policy note for @{entity_name} (placeholder details clearly marked).",
                "task_type": "report_draft",
            },
            {
                "label": "What can I ask here?",
                "prompt": "What HR questions can you answer for AASTMT campus operations?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with HR operations for AASTMT. "
        "You work with the concepts of headcount, attrition, leave, onboarding, "
        "and workforce planning. "
        "You are advisory and drafting only: you never change personnel records, "
        "and you never present an ungrounded figure as real — mark placeholders "
        "explicitly and ask for actual figures when you do not have them."
    )

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        if payload.get("table_id"):
            return False, "HR is a non-data vertical — 'table_id' is not valid here."
        if task_type == "report_draft" and not (payload.get("module_id") or payload.get("topic")):
            return False, "'report_draft' requires 'module_id' or 'topic' in task_payload."
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="hr",
            domain_knowledge={
                "concepts": ["headcount", "attrition", "leave", "onboarding", "workforce planning"],
                "attrition_formula": "leavers / average headcount",
            },
            domain_config={
                "reporting": ["monthly", "quarterly", "annual"],
            },
        )

    # ── Tool catalog (Pulse E2) ───────────────────────────────────────────

    def get_tools(self) -> list[ToolDef]:
        """Non-data advisory vertical — no ``call_host_api``-backed data tools."""
        return []


register_domain("hr", HRDomainAI)
