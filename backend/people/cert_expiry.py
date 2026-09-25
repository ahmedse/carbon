"""Certification expiry pipeline. No amounts.

horizon ∈ {30, 60, 90} days from as_of (default today).
expired: expiry < as_of. expiring: as_of ≤ expiry ≤ as_of+horizon.
current: expiry > as_of+horizon. Null expiry omitted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date

from people.closed_agg import EMP_DIMENSIONS, employee_label, org_ids

DIMENSIONS = EMP_DIMENSIONS + ("cert_type",)
HORIZONS = (30, 60, 90)
RETURNS = ("label", "expired", "expiring", "current")


def summarize_cert_expiry(
    user, *, horizon: str, dimension: str, as_of: str = "",
) -> tuple[int, dict[str, Any]]:
    from people.models import Certification

    dim = (dimension or "").strip()
    if dim not in DIMENSIONS:
        return 400, {
            "detail": f"Unknown dimension {dimension!r}. Allowed: {', '.join(str(d) for d in DIMENSIONS)}",
        }
    try:
        days_h = int(str(horizon).strip())
    except (TypeError, ValueError):
        return 400, {"detail": f"horizon must be one of {HORIZONS}."}
    if days_h not in HORIZONS:
        return 400, {"detail": f"Unknown horizon {horizon!r}. Allowed: {', '.join(map(str, HORIZONS))}"}

    parsed = parse_date((as_of or "").strip()) if as_of else timezone.localdate()
    if parsed is None:
        return 400, {"detail": "as_of must be YYYY-MM-DD."}
    cutoff = parsed + timedelta(days=days_h)

    ids = org_ids(user)
    qs = Certification.objects.select_related(
        "employee", "employee__org_unit", "employee__nationality",
        "employee__position", "cert_type",
    )
    if ids is not None:
        qs = qs.filter(employee__org_unit_id__in=ids)

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"expired": 0, "expiring": 0, "current": 0}
    )
    omitted = 0
    for cert in qs:
        if cert.expiry_date is None:
            omitted += 1
            continue
        emp = cert.employee
        if dim == "cert_type":
            label = (getattr(cert.cert_type, "code", None) or "").strip() or "(blank)"
        else:
            label = employee_label(emp, dim)
        if cert.expiry_date < parsed:
            buckets[label]["expired"] += 1
        elif cert.expiry_date <= cutoff:
            buckets[label]["expiring"] += 1
        else:
            buckets[label]["current"] += 1

    breakdown = [
        {"label": label, **buckets[label]}
        for label in sorted(buckets)
    ]
    caveats = []
    if omitted:
        caveats.append(f"{omitted} certification(s) omitted: no expiry_date.")
    if not breakdown:
        caveats.append("No certifications with an expiry date in this scope.")
    return 200, {
        "as_of": parsed.isoformat(),
        "horizon": days_h,
        "dimension": dim,
        "breakdown": breakdown,
        "omitted": omitted,
        "caveats": caveats,
    }
