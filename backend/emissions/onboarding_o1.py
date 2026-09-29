"""Benchmark O1 checklist.

``evaluate_o1`` is pure: it does not read the database and it does not invent
kilograms. ``load_o1_inputs`` is the only database read. The onboarding screen
renders the returned codes. It does not re-decide the rules.
"""
from __future__ import annotations

import re
from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from emissions.views import CarbonBrandPermission

ELECTRICITY = "Smart Village electricity"
DIESEL = "Smart Village diesel"
APPROACHES = frozenset({"equity_share", "financial_control", "operational_control"})
OTHER_CAMPUSES = ("South Valley", "Abu Qir", "Alamein")
STREAM_WORDS = ("generators", "fleet")
_STREAM_RE = {word: re.compile(rf"\b{word}\b", re.IGNORECASE) for word in STREAM_WORDS}


def _check(rule_id: str, code: str, met: bool, **fields: Any) -> dict[str, Any]:
    row = {"id": rule_id, "code": code, "met": bool(met)}
    row.update(fields)
    return row


def _boundary(period: dict, boundaries: list[dict]) -> dict | None:
    ref = period.get("organizational_boundary")
    if ref in (None, ""):
        return None
    if isinstance(ref, dict):
        return ref
    for row in boundaries:
        if row.get("id") == ref:
            return row
    return None


def _source(sources: list[dict], name: str, scope: int) -> dict | None:
    for row in sources:
        if row.get("source_name") == name and int(row.get("scope") or 0) == scope:
            return row
    return None


def _status(statuses: list[dict], source: dict, period_id: Any) -> dict | None:
    for row in statuses:
        if row.get("source_id") == source.get("id") and str(row.get("reporting_period_id")) == str(period_id):
            return row
    return None


def _stream(description: str) -> str | None:
    found = [word for word, pattern in _STREAM_RE.items() if pattern.search(description or "")]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        return "both"
    return None


def _kg(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _source_checks(sources, statuses, period_id) -> list[dict]:
    rows = []
    for name, scope in ((ELECTRICITY, 2), (DIESEL, 1)):
        source = _source(sources, name, scope)
        if source is None:
            rows.append(_check("CR-SRC-01", "source_missing", False, name=name, scope=scope))
            continue
        status = _status(statuses, source, period_id)
        if status is None:
            rows.append(_check("CR-SRC-01", "source_no_status", False, name=name))
        elif status.get("status") == "excluded":
            rows.append(_check(
                "CR-EXC-01", "source_excluded", False,
                name=name, reason=status.get("exclusion_reason") or "—",
            ))
        elif status.get("status") == "covered":
            honest = int(status.get("linked_table_count") or 0) > 0
            rows.append(_check(
                "CR-COV-01",
                "source_covered" if honest else "source_covered_invalid",
                honest,
                name=name,
            ))
        else:
            rows.append(_check("CR-SRC-01", "source_declared", False, name=name))
        if name == DIESEL:
            stream = _stream(str(source.get("description") or ""))
            if stream == "both":
                rows.append(_check("CR-SRC-01", "diesel_stream_both", False, name=name))
            elif stream is None:
                rows.append(_check("CR-SRC-01", "diesel_stream_missing", False, name=name))
            else:
                rows.append(_check("CR-SRC-01", "diesel_stream_met", True, name=name, stream=stream))
    return rows


def _quote_checks(summary: dict | None) -> list[dict]:
    total = int((summary or {}).get("total_calculations") or 0)
    if total <= 0:
        return [_check("CR-PULSE-01", "no_calculation", False)]
    rows = []
    by_scope = (summary or {}).get("by_scope") or {}
    if isinstance(by_scope, dict):
        for scope, item in by_scope.items():
            kg = _kg((item or {}).get("total_co2e_kg") if isinstance(item, dict) else None)
            if kg is None:
                continue
            rows.append(_check("CR-PULSE-01", "summary_kg", True, scope=str(scope), kg=kg))
    rows.append(_check("CR-PULSE-01", "not_assured", False))
    return rows


def evaluate_o1(*, periods, boundaries, sources, statuses, summary) -> dict[str, Any]:
    """Return the O1 checklist. ``summary`` kilograms are copied, never computed here."""
    periods = list(periods or [])
    boundaries = list(boundaries or [])
    sources = list(sources or [])
    statuses = list(statuses or [])
    open_rows = [row for row in periods if row.get("status") == "open"]
    checks: list[dict] = []
    period = open_rows[0] if len(open_rows) == 1 else None

    if period is None:
        checks.append(_check("CR-PER-01", "open_period_count", False, count=len(open_rows)))
    else:
        start = str(period.get("start_date") or "")
        end = str(period.get("end_date") or "")
        name = period.get("name") or period.get("id")
        if not start or not end or start >= end:
            checks.append(_check("CR-PER-01", "open_period_dates", False, name=name))
        elif period.get("period_type") != "annual":
            checks.append(_check(
                "CR-PER-01", "open_period_type", False,
                name=name, period_type=period.get("period_type") or "—",
            ))
        else:
            checks.append(_check(
                "CR-PER-01", "open_period_met", True,
                name=name, start=start, end=end, period_type="annual",
            ))
        boundary = _boundary(period, boundaries)
        if boundary is None:
            checks.append(_check("CR-BND-01", "boundary_missing", False))
        elif boundary.get("consolidation_approach") not in APPROACHES:
            checks.append(_check(
                "CR-BND-01", "boundary_approach", False,
                name=boundary.get("name") or boundary.get("id"),
                approach=boundary.get("consolidation_approach") or "—",
            ))
        else:
            checks.append(_check(
                "CR-BND-01", "boundary_met", True,
                name=boundary.get("name") or boundary.get("id"),
                approach=boundary.get("consolidation_approach"),
            ))
        checks.extend(_source_checks(sources, statuses, period.get("id")))
        checks.extend(_quote_checks(summary))
        for source in sources:
            label = str(source.get("source_name") or "")
            if not any(campus in label for campus in OTHER_CAMPUSES):
                continue
            status = _status(statuses, source, period.get("id"))
            checks.append(_check(
                "CR-EXC-01", "other_campus", False,
                name=label, status=(status or {}).get("status") or "absent",
            ))

    return {
        "benchmark": "O1",
        "benchmark_status": "open",
        "open_period_id": None if period is None else period.get("id"),
        "writes": False,
        "checks": checks,
    }


def load_o1_inputs(user) -> dict[str, Any]:
    """Read periods, boundaries, sources, statuses, and the calculation summary."""
    from django.db.models import Count

    from emissions.models import InventorySource, InventorySourceStatus, OrganizationalBoundary, ReportingPeriod
    from emissions.services import CalculationSummaryService

    periods = [
        {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "start_date": row.start_date.isoformat() if row.start_date else "",
            "end_date": row.end_date.isoformat() if row.end_date else "",
            "period_type": row.period_type,
            "organizational_boundary": row.organizational_boundary_id,
        }
        for row in ReportingPeriod.objects.all().only(
            "id", "name", "status", "start_date", "end_date", "period_type", "organizational_boundary_id",
        )
    ]
    open_ids = [row["id"] for row in periods if row["status"] == "open"]
    boundaries = [
        {"id": row.id, "name": row.name, "consolidation_approach": row.consolidation_approach}
        for row in OrganizationalBoundary.objects.all().only("id", "name", "consolidation_approach")
    ]
    sources = [
        {
            "id": row.id,
            "source_name": row.source_name,
            "scope": row.scope,
            "description": row.description or "",
        }
        for row in InventorySource.objects.all().only("id", "source_name", "scope", "description")
    ]
    statuses: list[dict] = []
    summary = None
    if len(open_ids) == 1:
        period_id = open_ids[0]
        statuses = [
            {
                "source_id": row.source_id,
                "reporting_period_id": row.reporting_period_id,
                "status": row.status,
                "exclusion_reason": row.exclusion_reason,
                "notes": row.notes or "",
                "linked_table_count": row.linked_table_count,
            }
            for row in InventorySourceStatus.objects.filter(reporting_period_id=period_id).annotate(
                linked_table_count=Count("linked_tables"),
            )
        ]
        summary = CalculationSummaryService.get_summary(user, period_id)
    return evaluate_o1(
        periods=periods,
        boundaries=boundaries,
        sources=sources,
        statuses=statuses,
        summary=summary,
    )


class OnboardingO1APIView(APIView):
    """GET the O1 checklist. Does not create a period, a source, or a figure."""

    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request):
        return Response(load_o1_inputs(request.user))
