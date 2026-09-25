"""KOC Kuwaitization quota: one named aggregate, closed population, declared fields.

Population: live employees with ``kuwaitization=True`` (the boolean, not
nationality KWT) whose org unit maps to an active KOC contract. Host computes
required / actual / deficit / fill_rate. Pulse restates. No reimbursement
amounts on this GET.
"""
from __future__ import annotations

from typing import Any

from people.permissions import is_global_admin

RETURNS = (
    "label", "contract_no", "required", "actual", "deficit",
    "fill_rate_pct", "status",
)

# Stable GOFSCO map: koc-contract code → org unit names (host of record).
KOC_CONTRACT_ORG_UNITS: dict[str, list[str]] = {
    "coiled_tubing": ["Coiled Tubing", "Coiled Tubing - KIRI"],
    "drilling_60": ["Drilling"],
    "drilling_61": ["Drilling Rig 61"],
    "pcp": ["Progressive Cavity Pump (PCP)"],
    "swt_intl": ["Surface Well Testing International", "Surface Well Testing - International"],
    "swt_local": ["Surface Well Testing"],
    "wireline": ["Wireline Logging Operation", "Wire Line"],
}


def _scoped_employees(user):
    from people.models import Employee

    qs = Employee.objects.all()
    if is_global_admin(user):
        return qs
    from accounts.rbac_utils import org_scope_for_capability
    from mdm.models import OrgUnit

    scope = org_scope_for_capability(user, "people:view")
    if scope.unrestricted:
        ids = list(OrgUnit.objects.filter(is_active=True).values_list("id", flat=True))
    else:
        ids = list(scope.ids)
    if not ids:
        return qs.none()
    return qs.filter(org_unit_id__in=ids)


def _required(meta: dict) -> int:
    raw = (meta or {}).get("required", 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def quota_for_contract(rv, employees) -> dict[str, Any]:
    """One contract row. ``employees`` is already org-scoped (or unscoped for audit)."""
    from mdm.models import OrgUnit

    meta = rv.metadata or {}
    required = _required(meta)
    org_names = KOC_CONTRACT_ORG_UNITS.get(rv.code, [])
    org_units = OrgUnit.objects.filter(name__in=org_names)
    actual = employees.filter(kuwaitization=True, org_unit__in=org_units).count()
    deficit = max(0, required - actual)
    return {
        "label": (rv.label or rv.code or "").strip() or "(blank)",
        "contract_no": meta.get("contract_no"),
        "required": required,
        "actual": actual,
        "deficit": deficit,
        "fill_rate_pct": round(100 * actual / required, 1) if required else 100.0,
        "status": "compliant" if actual >= required else "non_compliant",
    }


def summarize_kuwaitization(user) -> tuple[int, dict[str, Any]]:
    """``(status, payload)`` for GET /people/compliance/kuwaitization/."""
    from mdm.models import OrgUnit, ReferenceSet

    rs = ReferenceSet.objects.filter(slug="koc-contract").first()
    if rs is None:
        return 200, {
            "dimension": "koc_contract",
            "flag": "kuwaitization",
            "breakdown": [],
            "caveats": ["No KOC contract reference set is configured."],
        }

    employees = _scoped_employees(user)
    visible_org_ids = None
    if not is_global_admin(user):
        from accounts.rbac_utils import org_scope_for_capability

        scope = org_scope_for_capability(user, "people:view")
        if scope.unrestricted:
            visible_org_ids = set(
                OrgUnit.objects.filter(is_active=True).values_list("id", flat=True)
            )
        else:
            visible_org_ids = set(scope.ids)

    breakdown: list[dict[str, Any]] = []
    omitted = 0
    for rv in rs.values.filter(is_active=True).order_by("sort_order", "code"):
        org_names = KOC_CONTRACT_ORG_UNITS.get(rv.code, [])
        mapped = OrgUnit.objects.filter(name__in=org_names)
        if visible_org_ids is not None:
            mapped = mapped.filter(id__in=visible_org_ids)
            if not mapped.exists():
                omitted += 1
                continue
        breakdown.append(quota_for_contract(rv, employees))

    caveats: list[str] = []
    if not breakdown:
        caveats.append("No KOC Kuwaitization quotas are visible in this org scope.")
    if omitted:
        caveats.append(
            f"{omitted} contract(s) omitted — their org units are outside this scope."
        )
    return 200, {
        "dimension": "koc_contract",
        "flag": "kuwaitization",
        "breakdown": breakdown,
        "caveats": caveats,
    }
