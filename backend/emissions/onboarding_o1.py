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
_FACTOR_STREAMS = (
    (ELECTRICITY, 2, "kWh"),
    (DIESEL, 1, "litre"),
)
_GOAL_KEYS = frozenset({
    "id", "name", "scope", "completeness_definition", "min_quality_tier", "status", "target_year",
})


def _check(rule_id: str, code: str, met: bool, **fields: Any) -> dict[str, Any]:
    fields.pop("code", None)
    fields.pop("met", None)
    fields.pop("id", None)
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


def _open_period_entry(row: dict) -> dict[str, Any]:
    pid = row.get("id")
    name = row.get("name")
    if name is None or str(name).strip() == "":
        name = str(pid) if pid is not None else ""
    return {
        "id": pid,
        "name": name,
        "period_type": row.get("period_type") or "",
        "start_date": str(row.get("start_date") or ""),
        "end_date": str(row.get("end_date") or ""),
        "status": "open",
    }


def _campus_source(sources: list[dict], campus: str) -> dict | None:
    matches = [row for row in sources if campus in str(row.get("source_name") or "")]
    if not matches:
        return None
    return min(matches, key=lambda row: row.get("id", 0))


def _other_campus_check(sources: list[dict], statuses: list[dict], period_id: Any, campus: str) -> dict:
    source = _campus_source(sources, campus)
    if source is None:
        return _check("CR-EXC-01", "other_campus_absent", False, name=campus, status="absent")
    status_row = _status(statuses, source, period_id)
    if status_row is None:
        return _check("CR-EXC-01", "other_campus_no_status", False, name=campus)
    st = status_row.get("status")
    if st == "declared" and not status_row.get("exclusion_reason"):
        return _check("CR-EXC-01", "other_campus_declared", True, name=campus)
    if st == "excluded":
        reason = status_row.get("exclusion_reason")
        if reason in ("insufficient_data", "out_of_boundary"):
            return _check("CR-EXC-01", "other_campus_excluded", True, name=campus, reason=reason)
        if reason == "other":
            notes = str(status_row.get("notes") or "").strip()
            if notes:
                return _check("CR-EXC-01", "other_campus_excluded", True, name=campus, reason="other")
            return _check("CR-EXC-01", "other_campus_excluded_notes", False, name=campus)
        if reason == "not_material":
            return _check("CR-EXC-01", "other_campus_not_material", False, name=campus)
    if st == "covered":
        return _check("CR-EXC-01", "other_campus_covered", False, name=campus)
    return _check("CR-EXC-01", "other_campus_no_status", False, name=campus, status=st)


def _other_campus_checks(sources: list[dict], statuses: list[dict], period_id: Any) -> list[dict]:
    return [
        _other_campus_check(sources, statuses, period_id, campus)
        for campus in OTHER_CAMPUSES
    ]


def _canonical_unit(unit: Any) -> str:
    u = str(unit or "").strip().lower()
    if u == "kwh":
        return "kwh"
    if u in ("litre", "liter"):
        return "litre"
    return u


def _unit_matches(activity_unit: Any, stream_unit: str) -> bool:
    return _canonical_unit(activity_unit) == _canonical_unit(stream_unit)


def _factor_check_one(name: str, scope: int, unit: str, factors: list[dict]) -> dict:
    matches = [
        row for row in factors
        if int(row.get("scope") or 0) == scope and _unit_matches(row.get("activity_unit"), unit)
    ]
    if not matches:
        return _check("CR-FAC-01", "factor_missing", False, name=name, scope=scope, unit=unit)
    active = [row for row in matches if row.get("is_active")]
    if not active:
        pick = min(matches, key=lambda row: row.get("id", 0))
        return _check(
            "CR-FAC-01", "factor_inactive", False,
            record_id=pick.get("id"), name=pick.get("name"), scope=scope, unit=unit,
        )
    eligible = [
        row for row in active
        if str(row.get("country_code") or "").strip() in ("", "EGY")
    ]
    if not eligible:
        pick = min(active, key=lambda row: row.get("id", 0))
        return _check(
            "CR-FAC-01", "factor_country", False,
            record_id=pick.get("id"), name=pick.get("name"),
            country_code=str(pick.get("country_code") or "").strip(),
        )
    pick = min(eligible, key=lambda row: row.get("id", 0))
    source = pick.get("source")
    if source is None or str(source).strip() == "":
        return _check(
            "CR-FAC-01", "factor_source_blank", False,
            record_id=pick.get("id"), name=pick.get("name"),
        )
    country_code = str(pick.get("country_code") or "").strip()
    return _check(
        "CR-FAC-01", "factor_met", True,
        record_id=pick.get("id"), name=pick.get("name"), scope=scope, unit=unit,
        country_code=country_code,
    )


def _factor_checks(factors: list[dict]) -> list[dict]:
    return [
        _factor_check_one(name, scope, unit, factors)
        for name, scope, unit in _FACTOR_STREAMS
    ]


def _sanitize_goal(row: dict) -> dict:
    return {key: row[key] for key in _GOAL_KEYS if key in row}


def _coverage_goal_checks(sources: list[dict], goals: list[dict]) -> list[dict]:
    if _source(sources, ELECTRICITY, 2) is None or _source(sources, DIESEL, 1) is None:
        return []
    scoped = [_sanitize_goal(row) for row in goals if row.get("scope") == "1+2"]
    if not scoped:
        return [_check("CR-COV-01", "coverage_goal_absent", False)]
    goal = min(scoped, key=lambda row: row.get("id", 0))
    if goal.get("completeness_definition") != "materiality_bounded":
        return [_check(
            "CR-COV-01", "coverage_goal_completeness", False,
            record_id=goal.get("id"), name=goal.get("name"),
            completeness=goal.get("completeness_definition"),
        )]
    if goal.get("min_quality_tier") != 4:
        return [_check(
            "CR-COV-01", "coverage_goal_tier", False,
            record_id=goal.get("id"), name=goal.get("name"), tier=goal.get("min_quality_tier"),
        )]
    if goal.get("status") != "draft":
        return [_check(
            "CR-COV-01", "coverage_goal_status", False,
            record_id=goal.get("id"), name=goal.get("name"), status=goal.get("status"),
        )]
    return [_check(
        "CR-COV-01", "coverage_goal_met", True,
        record_id=goal.get("id"), name=goal.get("name"), scope="1+2",
        completeness="materiality_bounded", tier=4, status="draft",
        target_year=goal.get("target_year"),
    )]


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


def evaluate_o1(
    *,
    periods,
    boundaries,
    sources,
    statuses,
    summary,
    factors=None,
    goals=None,
) -> dict[str, Any]:
    """Return the O1 checklist. ``summary`` kilograms are copied, never computed here."""
    periods = list(periods or [])
    boundaries = list(boundaries or [])
    sources = list(sources or [])
    statuses = list(statuses or [])
    factors = list(factors or [])
    goals = list(goals or [])
    open_rows = [row for row in periods if row.get("status") == "open"]
    checks: list[dict] = []
    period = open_rows[0] if len(open_rows) == 1 else None

    if period is None:
        period_snapshots = sorted(
            (_open_period_entry(row) for row in open_rows),
            key=lambda item: item["id"],
        )
        checks.append(_check(
            "CR-PER-01", "open_period_count", False,
            count=len(open_rows), periods=period_snapshots,
        ))
        return {
            "benchmark": "O1",
            "benchmark_status": "open",
            "open_period_id": None,
            "writes": False,
            "checks": checks,
        }

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
    checks.extend(_other_campus_checks(sources, statuses, period.get("id")))
    checks.extend(_factor_checks(factors))
    checks.extend(_coverage_goal_checks(sources, goals))

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

    from emissions.models import (
        CoverageGoal,
        EmissionFactor,
        InventorySource,
        InventorySourceStatus,
        OrganizationalBoundary,
        ReportingPeriod,
    )
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
    factors: list[dict] = []
    goals: list[dict] = []
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
        factors = [
            {
                "id": row.id,
                "name": row.name,
                "scope": row.scope,
                "activity_unit": row.activity_unit,
                "country_code": row.country_code or "",
                "source": row.source,
                "is_active": row.is_active,
            }
            for row in EmissionFactor.objects.all().only(
                "id", "name", "scope", "activity_unit", "country_code", "source", "is_active",
            )
        ]
        goals = [
            {
                "id": row.id,
                "name": row.name,
                "scope": row.scope,
                "completeness_definition": row.completeness_definition,
                "min_quality_tier": row.min_quality_tier,
                "status": row.status,
                "target_year": row.target_year,
            }
            for row in CoverageGoal.objects.all().only(
                "id", "name", "scope", "completeness_definition",
                "min_quality_tier", "status", "target_year",
            )
        ]
    return evaluate_o1(
        periods=periods,
        boundaries=boundaries,
        sources=sources,
        statuses=statuses,
        summary=summary,
        factors=factors,
        goals=goals,
    )


class OnboardingO1APIView(APIView):
    """GET the O1 checklist. Does not create a period, a source, or a figure."""

    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request):
        return Response(load_o1_inputs(request.user))
