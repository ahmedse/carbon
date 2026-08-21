"""Governance & policy assistance (Phase 24 Phase J).

DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md §5B Phase J: explain policy; draft
policy changes (draft only); map rules → policies → dimensions; flag drift.

  * ``explain_policy``     — policy explanation grounded in the live rule
                             catalog (active rules by DAMA dimension,
                             covered tables, dimension gaps)
  * ``list_policies``      — inventory with scope labels + usage counts
  * ``draft_policy_change``— DRAFT ONLY: returns a ``requires_confirmation``
                             payload with current vs proposed diff; never
                             writes (RULE_21)
  * ``map_rules_to_policies`` — rules → policies → dimensions projection
  * ``flag_policy_drift``  — unbound rules, stale policies (never enforced),
                             dimension gaps (zero active rules)

Imports are downward-only (``catalog``, ``dq``, ``dataschema``, ``mdm``) —
never imported by those domain apps (RULE_20). No writes.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from catalog.models import DataDomain, GovernancePolicy
from dataschema.models import DataTable
from dq.models import DQRule, RuleFieldAssignment

logger = logging.getLogger("carbon.ai.policy_advisor")


# ── Scope labels ────────────────────────────────────────────────────────────


def _scope_label(policy: GovernancePolicy) -> str:
    if policy.scope_type == "org_unit" and policy.org_unit_id:
        return f"org_unit:{policy.org_unit.name}"
    if policy.scope_type == "domain" and policy.domain_id:
        return f"domain:{policy.domain.name}"
    if policy.scope_type == "scope" and policy.emission_scope is not None:
        return f"emission_scope:{policy.emission_scope}"
    return "global"


def _policy_summary(policy: GovernancePolicy) -> dict:
    return {
        "policy_id": policy.id,
        "name": policy.name,
        "policy_type": policy.policy_type,
        "description": policy.description,
        "enabled": policy.enabled,
        "scope_type": policy.scope_type,
        "scope_label": _scope_label(policy),
        "usage_count": policy.usage_count,
        "error_message": policy.error_message,
        "remediation_steps": policy.remediation_steps,
        "config": policy.config,
    }


def _rule_summary(rule: DQRule) -> dict:
    d = rule.definition or {}
    return {
        "rule_id": rule.id,
        "name": rule.name or d.get("name"),
        "rule_type": rule.rule_type or d.get("type"),
        "rule_level": rule.rule_level,
        "dimension": rule.dimension,
        "severity": rule.severity,
        "is_active": rule.is_active,
    }


# ── Catalog grounding helpers ───────────────────────────────────────────────


def _active_rules():
    return DQRule.objects.filter(archived=False, is_active=True)


def _rules_by_dimension() -> dict[str, list[DQRule]]:
    grouped: dict[str, list[DQRule]] = {}
    for rule in _active_rules().order_by("dimension", "name"):
        grouped.setdefault(rule.dimension, []).append(rule)
    return grouped


def _dimension_gaps(grouped: dict[str, list[DQRule]]) -> list[str]:
    from dq.catalog import DIMENSION_CODES

    return sorted(set(DIMENSION_CODES) - set(grouped.keys()))


# ── Public queries (all read-only) ──────────────────────────────────────────


def explain_policy(policy_id: int) -> dict:
    """Explain ``policy_id`` grounded in the existing rule catalog."""
    policy = (
        GovernancePolicy.objects.select_related("org_unit", "domain")
        .filter(pk=policy_id).first()
    )
    if policy is None:
        return {"error": {"code": "not_found", "detail": f"Policy {policy_id} not found."}}

    grouped = _rules_by_dimension()
    active_count = sum(len(rules) for rules in grouped.values())
    covered_tables = (
        RuleFieldAssignment.objects
        .filter(rule__archived=False, rule__is_active=True)
        .values_list("data_table_id", flat=True).distinct().count()
    )

    return {
        "policy": _policy_summary(policy),
        "catalog_context": {
            "active_rule_count": active_count,
            "covered_tables": covered_tables,
            "rules_by_dimension": [
                {"dimension": dim, "label": dim, "rule_count": len(rules)}
                for dim, rules in sorted(grouped.items())
            ],
            "dimension_gaps": _dimension_gaps(grouped),
        },
    }


def list_policies(
    enabled: bool | None = None, scope_type: str | None = None
) -> dict:
    """Inventory of governance policies, optionally filtered."""
    qs = GovernancePolicy.objects.select_related("org_unit", "domain")
    if enabled is not None:
        qs = qs.filter(enabled=enabled)
    if scope_type:
        qs = qs.filter(scope_type=scope_type)
    policies = [_policy_summary(p) for p in qs.order_by("policy_type", "scope_type", "name")]
    return {
        "policies": policies,
        "count": len(policies),
        "filters": {"enabled": enabled, "scope_type": scope_type},
    }


DRAFTABLE_FIELDS = {
    "name", "description", "enabled", "config", "error_message", "remediation_steps",
}


def draft_policy_change(policy_id: int, proposed: dict) -> dict:
    """DRAFT a policy change. Never writes — RULE_21.

    ``proposed`` keys are validated against ``DRAFTABLE_FIELDS``; the reply
    carries a current-vs-proposed diff and ``requires_confirmation: True``.
    """
    policy = GovernancePolicy.objects.filter(pk=policy_id).first()
    if policy is None:
        return {"error": {"code": "not_found", "detail": f"Policy {policy_id} not found."}}

    if not proposed or not isinstance(proposed, dict):
        return {"error": {"code": "empty_draft", "detail": "proposed changes required."}}

    unknown = sorted(set(proposed) - DRAFTABLE_FIELDS)
    if unknown:
        return {
            "error": {
                "code": "field_not_draftable",
                "detail": f"Cannot draft changes to: {', '.join(unknown)}",
            }
        }

    current = _policy_summary(policy)
    diff = []
    for field in sorted(DRAFTABLE_FIELDS & set(proposed)):
        cur = current.get(field)
        new = proposed[field]
        diff.append({"field": field, "current": cur, "proposed": new, "changed": cur != new})

    changed = [d for d in diff if d["changed"]]
    return {
        "type": "policy_draft",
        "requires_confirmation": True,
        "summary": (
            f"Draft changes to policy '{policy.name}': "
            f"{len(changed)} field(s) differ from the current policy."
            if changed else
            f"Draft for '{policy.name}' proposes no actual changes."
        ),
        "proposal": {
            "policy_id": policy.id,
            "policy_name": policy.name,
            "current": {d["field"]: d["current"] for d in diff},
            "proposed": {d["field"]: d["proposed"] for d in diff},
            "diff": diff,
        },
        "never_executes": True,
    }


def map_rules_to_policies() -> dict:
    """Map rules → policies → dimensions (read-only projection)."""
    grouped = _rules_by_dimension()
    dimensions = [
        {
            "dimension": dim,
            "rule_count": len(rules),
            "rules": [_rule_summary(r) for r in rules],
        }
        for dim, rules in sorted(grouped.items())
    ]
    policies = [
        {
            **_policy_summary(p),
            "dimension_counts": {
                dim: len(rules) for dim, rules in grouped.items()
            },
        }
        for p in GovernancePolicy.objects.select_related("org_unit", "domain")
        .order_by("policy_type", "scope_type", "name")
    ]
    return {
        "dimensions": dimensions,
        "policies": policies,
        "counts": {
            "dimensions": len(dimensions),
            "policies": len(policies),
            "rules": sum(d["rule_count"] for d in dimensions),
        },
    }


def flag_policy_drift() -> dict:
    """Drift flags: unbound rules, stale policies, dimension gaps.

    * ``unbound_rule``   — active rule with zero RuleFieldAssignment
    * ``stale_policy``   — enabled policy that never blocked anything
    * ``dimension_gap``  — DAMA dimension with zero active rules
    """
    flags: list[dict[str, Any]] = []

    bound_rule_ids = set(
        RuleFieldAssignment.objects.values_list("rule_id", flat=True)
    )
    for rule in _active_rules().order_by("name"):
        if rule.id not in bound_rule_ids:
            flags.append({
                "type": "unbound_rule",
                "severity": "medium",
                "rule_id": rule.id,
                "name": rule.name,
                "rule_type": rule.rule_type,
                "dimension": rule.dimension,
                "detail": "Active rule is not bound to any table or field.",
                "action": "review",
            })

    for policy in GovernancePolicy.objects.filter(enabled=True).order_by("name"):
        if policy.usage_count == 0:
            flags.append({
                "type": "stale_policy",
                "severity": "low",
                "policy_id": policy.id,
                "name": policy.name,
                "policy_type": policy.policy_type,
                "detail": "Enabled policy has never blocked an action.",
                "action": "review",
            })

    for dim in _dimension_gaps(_rules_by_dimension()):
        flags.append({
            "type": "dimension_gap",
            "severity": "medium",
            "dimension": dim,
            "detail": "No active rules cover this DAMA DMBOK2 dimension.",
            "action": "review",
        })

    flags.sort(key=lambda f: (f["severity"], str(f.get("name", f.get("dimension", "")))))
    return {"flags": flags, "count": len(flags)}
