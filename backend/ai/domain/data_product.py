"""Carbon AI Intelligence — Data Products Domain.

Registers ``data_product`` as a first-class AI coworker domain (Phase 24 —
remaining domains segment). Mirrors the admin domain pattern: manifest
surface + workspace context + payload validation + domain knowledge.

Surfaces: explain a data product, product health, draft a new version
(draft only — RULE_21, never auto-mutates). Grounded in ``catalog.Dataset`` /
``DatasetVersion`` (the governed, versioned data-product hub).
"""

from __future__ import annotations

from typing import Any

from ai.adapter.types import ToolDef
from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class DataProductDomainAI(DomainAIOperations):
    """Data Products domain AI operations + AI workspace manifest."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "data_product"
    app_display_name = "Data Products"

    # ── Manifest: task types supported by this domain ─────────────────────
    supported_task_types = [
        "chat",
        "product_explain",
        "product_health",
        "product_draft",
    ]

    # ── Manifest: entry-point buttons on domain pages ─────────────────────
    entry_points = [
        {"label": "Explain product",   "task_type": "product_explain", "on_entity": "module", "icon": "Info"},
        {"label": "Product health",    "task_type": "product_health",  "on_entity": "module", "icon": "HealthAndSafety"},
        {"label": "Draft new version", "task_type": "product_draft",   "on_entity": "module", "icon": "PostAdd"},
    ]

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "dataset": [
            {
                "label": "Explain product",
                "prompt": "Explain the data product @{entity_name}: what it contains, who owns it, and its lifecycle state.",
                "task_type": "product_explain",
            },
            {
                "label": "Product health",
                "prompt": "What is the data quality health of @{entity_name} across the DQ dimensions?",
                "task_type": "product_health",
            },
            {
                "label": "Draft new version",
                "prompt": "Draft the next version of @{entity_name} with a fresh data quality review.",
                "task_type": "product_draft",
            },
        ],
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What questions can you answer about governed data products and their versions?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with governed data products for the AASTMT data trust platform. "
        "A data product (Dataset) is a named, governed, versioned collection of data backed by "
        "DataTables. It follows a lifecycle: draft -> active -> deprecated -> archived. "
        "Each DatasetVersion is immutable once approved; new data means a new version, and "
        "versions carry a health score (0..1) with per-dimension detail (completeness, "
        "validity, freshness). Lineage records source, upstream versions, and transforms. "
        "You only explain, analyze, or draft — you never create, approve, or deprecate "
        "products or versions yourself; any proposed change requires explicit confirmation."
    )

    # ── Manifest: workspace context enrichment ────────────────────────────

    def build_workspace_context(
        self, user: Any, entity_type: str | None, entity_id: str | None
    ) -> dict[str, Any]:
        """Inject live data-product context into T1 tier.

        Resolves ``dataset`` (a catalog.Dataset) and returns a compact dict.
        Read-only.
        """
        ctx: dict[str, Any] = {}
        if not entity_type or not entity_id:
            return ctx

        try:
            if entity_type == "dataset":
                from catalog.models import Dataset

                dataset = Dataset.objects.filter(pk=entity_id).select_related("domain", "current_version").first()
                if dataset:
                    ctx["dataset_name"] = dataset.name
                    ctx["dataset_status"] = dataset.status
                    ctx["dataset_classification"] = dataset.classification
                    if dataset.domain_id:
                        ctx["domain_name"] = dataset.domain.name
                    if dataset.current_version_id:
                        ctx["current_version_number"] = dataset.current_version.version_number
                        if dataset.current_version.health_score is not None:
                            ctx["current_version_health"] = dataset.current_version.health_score
        except Exception:  # noqa: BLE001 — never let context enrichment crash the turn
            pass

        return ctx

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        needs_dataset = {"product_explain", "product_health", "product_draft"}

        if task_type in needs_dataset and not payload.get("dataset_id"):
            return False, f"'{task_type}' requires 'dataset_id' in task_payload."
        return True, ""

    # ── Tool catalog (Pulse E2) ───────────────────────────────────────────

    def get_tools(self) -> list[ToolDef]:
        """Data-product tools backed by ``call_host_api`` (read + one mutation)."""
        return [
            ToolDef(
                id="data_product.get_data_product_details",
                description="Get the data tables belonging to a data product (module).",
                required_capability="catalog:view",
                is_mutation=False,
                domain="data_product",
                input_schema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Module/data-product id."},
                    },
                },
                output_description="Data tables in the data product (module).",
            ),
            ToolDef(
                id="data_product.list_data_tables",
                description="List data tables visible to the user, optionally filtered by module_id.",
                required_capability="dataschema:view",
                is_mutation=False,
                domain="data_product",
                input_schema={
                    "type": "object",
                    "properties": {
                        "module_id": {"type": "string", "description": "Optional module id filter."},
                    },
                },
                output_description="Data tables with name, module, and schema.",
            ),
            ToolDef(
                id="data_product.create_table",
                description="Create a new data table (schema change) — requires explicit confirmation.",
                required_capability="dataschema:manage",
                is_mutation=True,
                domain="data_product",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "module": {"type": "string", "description": "Module id."},
                        "fields": {"type": "array", "items": {"type": "object"}},
                    },
                },
                output_description="The created data table.",
            ),
        ]

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="data_product",
            domain_knowledge={
                "model": "Dataset (UUID) with immutable approved DatasetVersions",
                "lifecycle": ["draft", "active", "deprecated", "archived"],
                "version_statuses": ["pending", "approved", "rejected"],
                "versioning_rule": "versions freeze on approval; new data = new version",
                "health_dimensions": ["completeness", "validity", "freshness"],
                "health_score": "0..1 composite over health_detail",
                "lineage_shape": {"source": {"type": "erp_snapshot|csv_upload|api", "ref": "..."}, "upstream_version_ids": [], "transforms": []},
                "cbac_anchor": "Dataset.module is the primary scope anchor",
                "mutation_rule": "assistants propose, humans confirm",
                "surfaces": ["product_explain", "product_health", "product_draft"],
            },
            domain_config={
                "capability_gate_view": "catalog:view",
                "capability_gate_manage": "catalog:manage_products",
                "read_only": True,
                "confirmation_required": True,
            },
        )


register_domain("data_product", DataProductDomainAI)
