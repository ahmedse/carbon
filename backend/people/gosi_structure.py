"""Committed GOSI totals: named aggregate, not a line_type on pay.

Same population rules as committed pay, line_type fixed to gosi.
people:view_compensation. Pulse restates.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.utils.dateparse import parse_date

from people.pay_structure import DIMENSIONS, _label, _median, _money, _org_ids
from people.models import PayrollRun, PayslipLine

RETURNS = (
    "label", "headcount", "average", "median", "min", "max", "total",
    "period_end", "dimension", "line_type", "status",
)
LINE_TYPE = "gosi"


def summarize_committed_gosi(
    user, *, period_end: str, dimension: str,
) -> tuple[int, dict[str, Any]]:
    dim = (dimension or "").strip()
    if dim not in DIMENSIONS:
        return 400, {
            "detail": f"Unknown dimension {dimension!r}. Allowed: {', '.join(DIMENSIONS)}",
        }
    parsed = parse_date((period_end or "").strip())
    if parsed is None:
        return 400, {"detail": "period_end is required (YYYY-MM-DD)."}

    org = _org_ids(user)
    runs = PayrollRun.objects.filter(status="committed", period_end=parsed)
    if org is not None:
        runs = runs.filter(org_unit_id__in=org)
    run_ids = list(runs.values_list("id", flat=True))
    empty = {
        "period_end": parsed.isoformat(),
        "dimension": dim,
        "line_type": LINE_TYPE,
        "status": "committed",
        "run_ids": run_ids,
        "omitted": 0,
        "caveats": ["No committed GOSI lines for this period and dimension."],
        "breakdown": [],
    }
    if not run_ids:
        return 200, empty

    lines = PayslipLine.objects.filter(
        payroll_run_id__in=run_ids, line_type__code=LINE_TYPE,
    ).select_related(
        "employee", "employee__org_unit", "employee__nationality", "employee__position",
    )
    if org is not None:
        lines = lines.filter(employee__org_unit_id__in=org)

    by_employee: dict[int, list] = defaultdict(list)
    for line in lines:
        by_employee[line.employee_id].append(line)

    omitted = 0
    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for emp_lines in by_employee.values():
        if len(emp_lines) != 1:
            omitted += 1
            continue
        line = emp_lines[0]
        grouped[_label(line.employee, dim)].append(line.amount)

    breakdown = []
    for label in sorted(grouped):
        amounts = grouped[label]
        total = sum(amounts, Decimal("0"))
        count = len(amounts)
        breakdown.append({
            "label": label,
            "headcount": count,
            "average": _money(total / count),
            "median": _money(_median(amounts)),
            "min": _money(min(amounts)),
            "max": _money(max(amounts)),
            "total": _money(total),
        })
    caveats = []
    if omitted:
        caveats.append(
            f"{omitted} employee(s) omitted: not exactly one gosi line in the period."
        )
    if not breakdown:
        caveats.append("No committed GOSI lines for this period and dimension.")
    return 200, {
        "period_end": parsed.isoformat(),
        "dimension": dim,
        "line_type": LINE_TYPE,
        "status": "committed",
        "run_ids": run_ids,
        "omitted": omitted,
        "caveats": caveats,
        "breakdown": breakdown,
    }
