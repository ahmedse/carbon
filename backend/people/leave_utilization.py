"""Leave utilization: named days aggregate, no money.

Population: LeaveEntitlement rows for one year, employee org in scope.
Host sums entitled+carried, used, remaining. Pulse restates.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from people.closed_agg import EMP_DIMENSIONS, days, employee_label, org_ids, pct

DIMENSIONS = EMP_DIMENSIONS + ("leave_type",)
RETURNS = (
    "label", "headcount", "entitled_days", "used_days",
    "remaining_days", "utilization_pct",
)


def summarize_leave_utilization(user, *, year: str, dimension: str) -> tuple[int, dict[str, Any]]:
    from people.models import LeaveEntitlement

    dim = (dimension or "").strip()
    if dim not in DIMENSIONS:
        return 400, {
            "detail": f"Unknown dimension {dimension!r}. Allowed: {', '.join(DIMENSIONS)}",
        }
    try:
        yr = int(str(year).strip())
    except (TypeError, ValueError):
        return 400, {"detail": "year is required (integer)."}
    if yr < 2000 or yr > 2100:
        return 400, {"detail": "year out of range."}

    ids = org_ids(user)
    qs = LeaveEntitlement.objects.filter(year=yr).select_related(
        "employee", "employee__org_unit", "employee__nationality",
        "employee__position", "leave_type",
    )
    if ids is not None:
        qs = qs.filter(employee__org_unit_id__in=ids)

    grouped: dict[str, list] = defaultdict(list)
    for row in qs:
        emp = row.employee
        emp._leave_type = row.leave_type
        grouped[employee_label(emp, dim)].append(row)

    breakdown = []
    for label in sorted(grouped):
        rows = grouped[label]
        emps = {r.employee_id for r in rows}
        entitled = sum((r.entitled_days + r.carried_forward for r in rows), Decimal("0"))
        used = sum((r.used_days for r in rows), Decimal("0"))
        remaining = entitled - used
        breakdown.append({
            "label": label,
            "headcount": len(emps),
            "entitled_days": days(entitled),
            "used_days": days(used),
            "remaining_days": days(remaining),
            "utilization_pct": pct(used, entitled),
        })
    caveats = []
    if not breakdown:
        caveats.append("No leave entitlements for this year and dimension.")
    return 200, {
        "year": yr,
        "dimension": dim,
        "breakdown": breakdown,
        "caveats": caveats,
    }
