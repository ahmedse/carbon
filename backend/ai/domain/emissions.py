"""Carbon AI Intelligence — Emissions (Carbon Footprint) Domain.

AI CONTRACT §8: domain-specific AI operations for the emissions app.
"""

from __future__ import annotations

from typing import Any

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class EmissionsDomainAI(DomainAIOperations):
    """Emissions (carbon footprint) domain AI operations + AI workspace manifest."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "emissions"
    app_display_name = "Carbon Footprint"

    # ── Manifest: task types supported by this domain ─────────────────────
    supported_task_types = [
        "chat",
        "dq_validate",
        "dq_suggest",
        "nl_query",
        "anomaly",
        "investigate",
        "nl_rule_test",
        "report_draft",
    ]

    # ── Manifest: entry-point buttons on domain pages ─────────────────────
    # on_entity: the entity type on whose detail/list page this button appears.
    entry_points = [
        {"label": "Validate DQ",    "task_type": "dq_validate",  "on_entity": "table",  "icon": "FactCheck"},
        {"label": "Suggest Rules",  "task_type": "dq_suggest",   "on_entity": "table",  "icon": "AutoFixHigh"},
        {"label": "Investigate",    "task_type": "investigate",   "on_entity": "table",  "icon": "ManageSearch"},
        {"label": "Draft Report",   "task_type": "report_draft",  "on_entity": "module", "icon": "Description"},
        {"label": "Ask about this", "task_type": "chat",          "on_entity": "*",      "icon": "Chat"},
    ]

    # ── Manifest: context-aware starter chips ─────────────────────────────
    # "@{entity_name}" is replaced client-side with the actual entity name.
    starter_prompts = {
        "table": [
            {
                "label": "Why is quality score low?",
                "prompt": "Explain the current data quality issues for @{entity_name} and what I should fix first.",
                "task_type": "chat",
            },
            {
                "label": "Suggest DQ rules",
                "prompt": "",
                "task_type": "dq_suggest",
            },
            {
                "label": "Investigate anomalies",
                "prompt": "",
                "task_type": "investigate",
            },
        ],
        "module": [
            {
                "label": "Summarize data quality",
                "prompt": "Summarize the data quality status across all tables in @{entity_name}. What needs attention?",
                "task_type": "chat",
            },
            {
                "label": "Draft GHG report",
                "prompt": "",
                "task_type": "report_draft",
            },
            {
                "label": "Why did emissions change?",
                "prompt": "Compare total emissions for @{entity_name} between this month and the same period last year. What changed?",
                "task_type": "nl_query",
            },
        ],
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What questions can you answer about the Carbon emissions data for AASTMT?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are analyzing Carbon emissions data for AASTMT university campus. "
        "The data follows the GHG Protocol Corporate Standard (Scope 1/2/3, IPCC AR6). "
        "Emission factors are in tCO₂e per unit activity. "
        "Electricity is measured in kWh (Scope 2), water in m³ (Scope 3), "
        "chilled water in TR (Scope 2). "
        "Key campus buildings: Building 401, Building 2401 (Smart Village). "
        "Reporting periods follow the fiscal year. "
        "Always cite the specific table, field, and row counts when making data claims."
    )

    # ── Manifest: workspace context enrichment ────────────────────────────

    def build_workspace_context(
        self, user: Any, entity_type: str | None, entity_id: str | None
    ) -> dict[str, Any]:
        """Inject live emissions domain context into T1 tier.

        Resolves the current entity (table or module) and returns a compact
        dict that the context_assembler includes in the workspace context block.
        """
        ctx: dict[str, Any] = {}
        if not entity_type or not entity_id:
            return ctx

        try:
            if entity_type == "table":
                from dataschema.models import DataTable
                table = DataTable.objects.filter(pk=entity_id).select_related("module").first()
                if table:
                    ctx["table_name"] = table.name
                    ctx["row_count"] = table.rows.count()
                    if table.module:
                        ctx["module_name"] = table.module.name
                        ctx["module_scope"] = table.module.scope
            elif entity_type == "module":
                from core.models import Module
                module = Module.objects.filter(pk=entity_id).select_related("org_unit").first()
                if module:
                    ctx["module_name"] = module.name
                    ctx["module_scope"] = module.scope
                    if module.org_unit:
                        ctx["org_unit_name"] = module.org_unit.name
        except Exception:  # noqa: BLE001 — never let context enrichment crash the turn
            pass

        return ctx

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        needs_table = {"dq_validate", "dq_suggest", "investigate", "nl_rule_test", "anomaly"}
        needs_module = {"report_draft"}

        if task_type in needs_table and not payload.get("table_id"):
            return False, f"'{task_type}' requires 'table_id' in task_payload."
        if task_type in needs_module and not payload.get("module_id") and not payload.get("period_id"):
            return False, "'report_draft' requires 'module_id' or 'period_id' in task_payload."
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="emissions",
            domain_knowledge={
                "protocol": "GHG Protocol Corporate Standard",
                "scopes": {
                    "scope_1": "Direct emissions from owned/controlled sources",
                    "scope_2": "Indirect emissions from purchased energy",
                    "scope_3": "All other indirect emissions in value chain",
                },
                "ar_version": "IPCC AR6",
                "units": ["tCO2e", "kgCO2e", "MtCO2e"],
                "calculation_methods": ["location-based", "market-based"],
            },
            domain_config={
                "default_gwp_version": "AR6",
                "boundary_approaches": ["operational", "equity share", "financial control"],
            },
        )


register_domain("emissions", EmissionsDomainAI)
