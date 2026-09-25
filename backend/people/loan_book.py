"""Loan book: outstanding principal at as_of. Compensation-gated.

Remaining = unpaid principal portions (status != paid, or due after as_of).
No schedule → remaining = principal. Draft loans are included when status
is the dimension; default population is every visible loan.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.utils.dateparse import parse_date

from people.closed_agg import EMP_DIMENSIONS, employee_label, money, org_ids

DIMENSIONS = EMP_DIMENSIONS + ("loan_type", "status")
RETURNS = ("label", "count", "principal_total", "remaining_total")


def _remaining(loan, as_of) -> Decimal:
    if loan.status in ("paid_off", "cancelled"):
        return Decimal("0")
    paid = Decimal("0")
    has_sched = False
    for inst in loan.installments.all():
        has_sched = True
        if inst.status == "paid" and inst.due_date <= as_of:
            paid += inst.principal_portion
    if not has_sched:
        return loan.principal
    left = loan.principal - paid
    return left if left > 0 else Decimal("0")


def summarize_loan_book(user, *, as_of: str, dimension: str) -> tuple[int, dict[str, Any]]:
    from people.models import Loan

    dim = (dimension or "").strip()
    if dim not in DIMENSIONS:
        return 400, {
            "detail": f"Unknown dimension {dimension!r}. Allowed: {', '.join(DIMENSIONS)}",
        }
    parsed = parse_date((as_of or "").strip())
    if parsed is None:
        return 400, {"detail": "as_of is required (YYYY-MM-DD)."}

    ids = org_ids(user)
    qs = Loan.objects.select_related(
        "employee", "employee__org_unit", "employee__nationality",
        "employee__position", "loan_type",
    ).prefetch_related("installments")
    if ids is not None:
        qs = qs.filter(employee__org_unit_id__in=ids)

    grouped: dict[str, list] = defaultdict(list)
    for loan in qs:
        emp = loan.employee
        emp._loan_type = loan.loan_type
        emp._status = loan.status
        if dim == "loan_type":
            label = (getattr(loan.loan_type, "code", None) or "").strip() or "(blank)"
        elif dim == "status":
            label = loan.status
        else:
            label = employee_label(emp, dim)
        grouped[label].append(loan)

    breakdown = []
    for label in sorted(grouped):
        loans = grouped[label]
        principal = sum((ln.principal for ln in loans), Decimal("0"))
        remaining = sum((_remaining(ln, parsed) for ln in loans), Decimal("0"))
        breakdown.append({
            "label": label,
            "count": len(loans),
            "principal_total": money(principal),
            "remaining_total": money(remaining),
        })
    caveats = []
    if not breakdown:
        caveats.append("No loans visible for this as_of and dimension.")
    return 200, {
        "as_of": parsed.isoformat(),
        "dimension": dim,
        "breakdown": breakdown,
        "caveats": caveats,
    }
