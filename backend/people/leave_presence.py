"""Org-wide leave presence for one calendar month. Not Team Who's Out.

Population: LeaveRecord overlapping the month with status submitted or
approved. Draft ESS stays on Team Who's Out. Days are stored leave days
prorated to the month overlap.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from people.closed_agg import EMP_DIMENSIONS, days, employee_label, org_ids


def _month_share(row, start: date, end: date) -> Decimal:
    lo = max(row.start_date, start)
    hi = min(row.end_date, end)
    if hi < lo:
        return Decimal("0")
    overlap = (hi - lo).days + 1
    span = (row.end_date - row.start_date).days + 1
    if span <= 0:
        return Decimal("0")
    return row.days * Decimal(overlap) / Decimal(span)

DIMENSIONS = EMP_DIMENSIONS + ("leave_type",)
RETURNS = ("label", "on_leave_count", "days")
ON_LEAVE = ("submitted", "approved")


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def summarize_leave_presence(
    user, *, year: str, month: str, dimension: str,
) -> tuple[int, dict[str, Any]]:
    from people.models import LeaveRecord

    dim = (dimension or "").strip()
    if dim not in DIMENSIONS:
        return 400, {
            "detail": f"Unknown dimension {dimension!r}. Allowed: {', '.join(DIMENSIONS)}",
        }
    try:
        yr = int(str(year).strip())
        mo = int(str(month).strip())
    except (TypeError, ValueError):
        return 400, {"detail": "year and month must be integers."}
    if mo < 1 or mo > 12 or yr < 2000 or yr > 2100:
        return 400, {"detail": "year/month out of range."}

    start, end = _month_bounds(yr, mo)
    ids = org_ids(user)
    qs = LeaveRecord.objects.filter(
        status__in=ON_LEAVE,
        start_date__lte=end,
        end_date__gte=start,
    ).select_related(
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
        breakdown.append({
            "label": label,
            "on_leave_count": len({r.employee_id for r in rows}),
            "days": days(sum((_month_share(r, start, end) for r in rows), Decimal("0"))),
        })
    caveats = []
    if not breakdown:
        caveats.append("No submitted or approved leave overlapping this month.")
    else:
        caveats.append("Days are the stored leave days prorated to the month overlap.")
    return 200, {
        "year": yr,
        "month": mo,
        "dimension": dim,
        "status": list(ON_LEAVE),
        "breakdown": breakdown,
        "caveats": caveats,
    }
