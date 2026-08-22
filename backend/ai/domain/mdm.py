"""Carbon AI Intelligence — Master Data (MDM) Domain.

Registers ``mdm`` as a first-class AI coworker domain (Phase 24 — remaining
domains segment). Mirrors the admin domain pattern: manifest surface +
workspace context + payload validation + domain knowledge.

Surfaces: explain a master record / gold-record confidence, dedup
suggestions, draft a merge (draft only — RULE_21, never auto-mutates).
The read logic lives in ``ai.knowledge.mdm_advisor`` (Phase K); this module
wires it into the domain ABC so Pulse can offer it as a coworker surface.
"""

from __future__ import annotations

from typing import Any

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class MdmDomainAI(DomainAIOperations):
    """Master Data (MDM) domain AI operations + AI workspace manifest."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "mdm"
    app_display_name = "Master Data"

    # ── Manifest: task types supported by this domain ─────────────────────
    # mdm_explain / mdm_dedup are shared with the admin domain (both may
    # offer them); mdm_merge_draft is MDM-specific (draft-only merge).
    supported_task_types = [
        "chat",
        "mdm_explain",
        "mdm_dedup",
        "mdm_merge_draft",
    ]

    # ── Manifest: entry-point buttons on domain pages ─────────────────────
    entry_points = [
        {"label": "Explain master record", "task_type": "mdm_explain",    "on_entity": "entity",       "icon": "Badge"},
        {"label": "Suggest dedup",         "task_type": "mdm_dedup",      "on_entity": "entity",       "icon": "JoinInner"},
        {"label": "Draft merge",           "task_type": "mdm_merge_draft", "on_entity": "entity",      "icon": "Merge"},
    ]

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "entity": [
            {
                "label": "Explain master record",
                "prompt": "Explain the master record for @{entity_name} and its gold-record confidence.",
                "task_type": "mdm_explain",
            },
            {
                "label": "Suggest dedup",
                "prompt": "Suggest deduplication candidates for @{entity_name}.",
                "task_type": "mdm_dedup",
            },
        ],
        "reference_set": [
            {
                "label": "Deduplicate this set",
                "prompt": "Find duplicate reference values in the @{entity_name} reference set.",
                "task_type": "mdm_dedup",
            },
        ],
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What questions can you answer about master data and reference sets?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with master data management for the AASTMT data trust platform. "
        "Master records are reference values inside reference sets (e.g. emission factors, "
        "units, codes) that follow a lifecycle: draft -> active -> deprecated -> archived. "
        "A reference value can be valid in a date window (valid_from/valid_to) and carries a "
        "deterministic gold-record confidence. "
        "You only explain, suggest, or draft — you never create, merge, deprecate, or archive "
        "master records yourself; any proposed change requires explicit confirmation."
    )

    # ── Manifest: workspace context enrichment ────────────────────────────

    def build_workspace_context(
        self, user: Any, entity_type: str | None, entity_id: str | None
    ) -> dict[str, Any]:
        """Inject live master-data context into T1 tier.

        Resolves ``entity`` (a ReferenceValue) or ``reference_set`` (a
        ReferenceSet) and returns a compact dict. Read-only; no sensitive
        content.
        """
        ctx: dict[str, Any] = {}
        if not entity_type or not entity_id:
            return ctx

        try:
            if entity_type == "entity":
                from mdm.models import ReferenceValue

                value = (
                    ReferenceValue.objects.filter(pk=entity_id)
                    .select_related("reference_set")
                    .first()
                )
                if value:
                    ctx["value_code"] = value.code
                    ctx["value_label"] = value.label
                    ctx["value_active"] = value.is_active
                    ctx["reference_set_name"] = value.reference_set.name
                    ctx["reference_set_lifecycle"] = value.reference_set.lifecycle_state
            elif entity_type == "reference_set":
                from mdm.models import ReferenceSet

                rs = ReferenceSet.objects.filter(pk=entity_id).first()
                if rs:
                    ctx["reference_set_name"] = rs.name
                    ctx["reference_set_lifecycle"] = rs.lifecycle_state
                    ctx["active_value_count"] = rs.get_active_values().count()
        except Exception:  # noqa: BLE001 — never let context enrichment crash the turn
            pass

        return ctx

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        needs_entity = {"mdm_explain", "mdm_dedup"}
        needs_merge = {"mdm_merge_draft"}

        if task_type in needs_entity and not (
            (payload.get("entity_type") and payload.get("entity_id"))
            or (payload.get("reference_set_id") and payload.get("code"))
        ):
            return False, (
                f"'{task_type}' requires 'entity_type'+'entity_id' or "
                "'reference_set_id'+'code' in task_payload."
            )
        if task_type in needs_merge and not (
            payload.get("set_id")
            and payload.get("duplicate_value_id")
            and payload.get("gold_value_id")
        ):
            return False, (
                "'mdm_merge_draft' requires 'set_id', 'duplicate_value_id', "
                "and 'gold_value_id' in task_payload."
            )
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="mdm",
            domain_knowledge={
                "model": "reference sets of reference values",
                "lifecycle": ["draft", "active", "deprecated", "archived"],
                "transition_rules": {
                    "draft": ["active"],
                    "active": ["deprecated"],
                    "deprecated": ["active", "archived"],
                    "archived": [],
                },
                "gold_record_confidence": "deterministic 0..1 score over activity, validity window, label uniqueness, metadata, near-duplicates, and set lifecycle",
                "dedup_basis": ["normalized code", "label similarity"],
                "mutation_rule": "assistants propose, humans confirm",
                "surfaces": ["mdm_explain", "mdm_dedup", "mdm_merge_draft"],
            },
            domain_config={
                "capability_gate_view": "mdm:view",
                "capability_gate_manage": "mdm:manage",
                "read_only": True,
                "confirmation_required": True,
            },
        )


register_domain("mdm", MdmDomainAI)
