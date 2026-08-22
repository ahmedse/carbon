"""Carbon AI Intelligence — Platform Administration Domain.

AI CONTRACT §8 + DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md §5B Phase G:
domain-specific AI operations for the platform admin/ops surfaces.

Admin & ops are **both substrate and surface**: the correctness-critical rails
(scope enforcement, lineage truth, governance) remain exactly as they are, and
the assistant assists admins *on top of them* — suggest/draft ONLY, never
auto-mutation (§4, RULE_21). Every proposed write from this domain carries
``requires_confirmation``.

Surfaces covered by the manifest (the actual read-only analysis modules land
in later phases H–K under ``ai/knowledge/``):

  * access_query     — effective capability sets / reverse capability lookup
  * lineage_trace    — where does this field/table flow from/to
  * impact_analysis  — if I change X, what rules/tables break
  * policy_explain   — explain a governance policy, grounded in the catalog
  * policy_draft     — draft a policy change (draft only, never applied)
  * mdm_explain      — explain an entity's master record + gold-record confidence
  * mdm_dedup        — entity-resolution dedup suggestions (never auto-merge)
"""

from __future__ import annotations

from typing import Any

from ai.domain_protocol import (
    DomainAIOperations,
    DomainContext,
    register_domain,
)


class AdminDomainAI(DomainAIOperations):
    """Platform administration domain AI operations + AI workspace manifest."""

    # ── Identity ──────────────────────────────────────────────────────────
    app_identifier = "admin"
    app_display_name = "Platform Administration"

    # ── Manifest: task types supported by this domain ─────────────────────
    # Platform base types (chat, ...) stay valid; the admin-specific types
    # are declared here and flow into the conversation-type registry
    # (ADR-0010 — a new domain introduces new types with zero core changes).
    supported_task_types = [
        "chat",
        "access_query",
        "lineage_trace",
        "impact_analysis",
        "policy_explain",
        "policy_draft",
        "mdm_explain",
        "mdm_dedup",
    ]

    # ── Manifest: entry-point buttons on admin/ops pages ──────────────────
    entry_points = [
        {"label": "Check access",        "task_type": "access_query",     "on_entity": "user",   "icon": "AdminPanelSettings"},
        {"label": "Who can reach?",      "task_type": "access_query",     "on_entity": "table",  "icon": "ManageAccounts"},
        {"label": "Trace lineage",       "task_type": "lineage_trace",    "on_entity": "table",  "icon": "AccountTree"},
        {"label": "Impact analysis",     "task_type": "impact_analysis",  "on_entity": "table",  "icon": "Construction"},
        {"label": "Explain policy",      "task_type": "policy_explain",   "on_entity": "policy", "icon": "Gavel"},
        {"label": "Draft policy change", "task_type": "policy_draft",     "on_entity": "policy", "icon": "EditNote"},
        {"label": "Explain master record", "task_type": "mdm_explain",    "on_entity": "entity", "icon": "Badge"},
        {"label": "Suggest dedup",       "task_type": "mdm_dedup",        "on_entity": "entity", "icon": "JoinInner"},
    ]

    # ── Manifest: context-aware starter chips ─────────────────────────────
    starter_prompts = {
        "user": [
            {
                "label": "Effective capabilities",
                "prompt": "What is the effective capability set for @{entity_name} across their org scope?",
                "task_type": "access_query",
            },
            {
                "label": "Least-privilege grant",
                "prompt": "Propose the least-privilege grant so @{entity_name} can view data quality data.",
                "task_type": "access_query",
            },
        ],
        "group": [
            {
                "label": "What does this role grant?",
                "prompt": "Which capabilities does the role @{entity_name} grant, and who holds it?",
                "task_type": "access_query",
            },
        ],
        "org_unit": [
            {
                "label": "Access across subtree",
                "prompt": "Summarize effective access across @{entity_name} and its sub-units.",
                "task_type": "access_query",
            },
        ],
        "table": [
            {
                "label": "Where does this flow?",
                "prompt": "Trace the lineage for @{entity_name}: where does it come from and where does it flow?",
                "task_type": "lineage_trace",
            },
            {
                "label": "What breaks?",
                "prompt": "If I change @{entity_name}, which rules and tables are affected?",
                "task_type": "impact_analysis",
            },
        ],
        "policy": [
            {
                "label": "Explain policy",
                "prompt": "Explain the governance policy @{entity_name}: what it blocks, when, and for whom.",
                "task_type": "policy_explain",
            },
            {
                "label": "Draft change",
                "prompt": "Draft a change to policy @{entity_name} that permits <describe the need>.",
                "task_type": "policy_draft",
            },
        ],
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
        "default": [
            {
                "label": "What can I ask here?",
                "prompt": "What admin questions can you answer about users, access, lineage, policies, and master data?",
                "task_type": "chat",
            },
        ],
    }

    # ── Manifest: T0 system prompt extension ──────────────────────────────
    system_prompt_extension = (
        "You are assisting with platform administration for the AASTMT data trust platform. "
        "Access follows capability-based control: users receive capabilities through scoped "
        "roles over organizational units, groups, and modules. "
        "You only ever explain, analyze, or propose — you never change access, users, policies, "
        "or master records yourself; any proposed change requires explicit confirmation before "
        "it is applied. "
        "Prefer least-privilege grants, and flag over-granted or dormant access when you see it."
    )

    # ── Manifest: workspace context enrichment ────────────────────────────

    def build_workspace_context(
        self, user: Any, entity_type: str | None, entity_id: str | None
    ) -> dict[str, Any]:
        """Inject live admin/ops context into T1 tier.

        Resolves the current entity (user, group, org_unit, table, policy) and
        returns a compact dict included in the workspace context block.
        Read-only; never returns sensitive content (no capability lists).
        """
        ctx: dict[str, Any] = {}
        if not entity_type or not entity_id:
            return ctx

        try:
            if entity_type == "user":
                from accounts.models import User as AccountUser

                target = (
                    AccountUser.objects.filter(pk=entity_id)
                    .only("username", "is_active", "is_superuser")
                    .first()
                )
                if target:
                    ctx["username"] = target.username
                    ctx["is_active"] = target.is_active
                    ctx["scoped_role_count"] = target.scoped_roles.filter(is_active=True).count()
            elif entity_type == "group":
                from django.contrib.auth.models import Group

                group = Group.objects.filter(pk=entity_id).only("name").first()
                if group:
                    ctx["group_name"] = group.name
                    ctx["member_count"] = group.user_set.count()
            elif entity_type == "org_unit":
                from mdm.models import OrgUnit

                ou = OrgUnit.objects.filter(pk=entity_id).only("name", "org_type").first()
                if ou:
                    ctx["org_unit_name"] = ou.name
                    ctx["org_unit_type"] = ou.org_type
            elif entity_type == "table":
                from dataschema.models import DataTable

                table = DataTable.objects.filter(pk=entity_id).select_related("module").first()
                if table:
                    ctx["table_name"] = table.name
                    if table.module:
                        ctx["module_name"] = table.module.name
            elif entity_type == "policy":
                from catalog.models import GovernancePolicy

                policy = (
                    GovernancePolicy.objects.filter(pk=entity_id)
                    .only("name", "policy_type", "enabled")
                    .first()
                )
                if policy:
                    ctx["policy_name"] = policy.name
                    ctx["policy_type"] = policy.policy_type
                    ctx["policy_enabled"] = policy.enabled
        except Exception:  # noqa: BLE001 — never let context enrichment crash the turn
            pass

        return ctx

    # ── Manifest: payload validation ──────────────────────────────────────

    def validate_task_payload(
        self, task_type: str, payload: dict[str, Any]
    ) -> tuple[bool, str]:
        needs_user = {"access_query"}
        needs_table = {"lineage_trace", "impact_analysis"}
        needs_policy = {"policy_explain", "policy_draft"}
        needs_entity = {"mdm_explain", "mdm_dedup"}

        if task_type in needs_user and not payload.get("user_id"):
            return False, "'access_query' requires 'user_id' in task_payload."
        if task_type in needs_table and not payload.get("table_id"):
            return False, f"'{task_type}' requires 'table_id' in task_payload."
        if task_type in needs_policy and not payload.get("policy_id") and not payload.get("policy_type"):
            return False, f"'{task_type}' requires 'policy_id' or 'policy_type' in task_payload."
        if task_type in needs_entity and not (
            (payload.get("entity_type") and payload.get("entity_id"))
            or (payload.get("reference_set_id") and payload.get("code"))
        ):
            return False, (
                f"'{task_type}' requires 'entity_type'+'entity_id' or "
                "'reference_set_id'+'code' in task_payload."
            )
        return True, ""

    # ── Domain knowledge (original contract) ──────────────────────────────

    def get_domain_context(self) -> DomainContext:
        return DomainContext(
            app_identifier="admin",
            domain_knowledge={
                "access_model": "Capability-Based Access Control",
                "grant_units": ["global", "org_unit", "module"],
                "capability_shape": "{domain}:{action}",
                "principle": "least privilege",
                "mutation_rule": "assistants propose, humans confirm",
                "surfaces": [
                    "access_query",
                    "lineage_trace",
                    "impact_analysis",
                    "policy_explain",
                    "policy_draft",
                    "mdm_explain",
                    "mdm_dedup",
                ],
            },
            domain_config={
                "capability_gate_manage": "platform:manage_access",
                "capability_gate_view": "platform:view_audit",
                "read_only": True,
                "confirmation_required": True,
            },
        )


register_domain("admin", AdminDomainAI)
