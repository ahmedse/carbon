"""Campus intake for O2, O3, O4, O5, market-based Scope 2, and P1.

CR-INT-01. Product Carbon on AASTMT. Date 1 Oct 2026.
Quotes cells from named files. Stores a kilogram only when an uploaded
row matches the single open period and the factor is legal. Does not
open a second ReportingPeriod. Does not mark a benchmark passed.
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

CAMPUS_COLUMNS = (
    "campus",
    "source_name",
    "scope",
    "activity_unit",
    "quantity",
    "stream",
    "period_start",
    "period_end",
)
WASTE_COLUMNS = (
    "source_name",
    "quantity_tonne",
    "treatment",
    "period_start",
    "period_end",
)
FACTOR_COLUMNS = (
    "factor_code",
    "factor_value",
    "activity_unit",
    "source",
    "valid_from",
    "treatment",
)
DIESEL_STREAMS = frozenset({"generators", "fleet"})
OPEN_PERIOD_FILES = {
    "O2": "raw/Carbon footprint app/csv/south_valley_inventory.csv",
    "O3": "raw/Carbon footprint app/csv/abu_qir_inventory.csv",
    "O4": "raw/Carbon footprint app/csv/new_alamein_inventory.csv",
}
WASTE_FACTOR_FILE = "raw/Carbon footprint app/csv/smart_village_waste_factor.csv"
SV_SCOPE12 = "raw/Carbon footprint app/csv/south_valley_scope12_fy2526.csv"
SV_SCOPE3 = "raw/Carbon footprint app/csv/south_valley_scope3_fy2526.csv"
AQ_ELEC = "raw/Carbon footprint app/csv/abu_qir_monthly_electricity_fy2526.csv"
AQ_FUEL = "raw/Carbon footprint app/csv/abu_qir_fuel_fy2526.csv"
SV_INVENTORY = "raw/Carbon footprint app/csv/smart_village_inventory_fy2324.csv"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def academy_period() -> dict[str, str]:
    path = repo_root() / "domain_packs" / "carbon" / "assurance" / "benchmarks" / "O1-smart-village.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    window = (data.get("close") or {}).get("period") or {}
    return {
        "start_date": str(window.get("start_date") or ""),
        "end_date": str(window.get("end_date") or ""),
    }


def _read_csv(rel: str) -> list[dict[str, str]]:
    path = repo_root() / rel
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [
            {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _basename(rel: str) -> str:
    return Path(rel).name


def _activity(label: str, quantity: str, unit: str, source_file: str) -> dict[str, str]:
    return {
        "label": label,
        "quantity": quantity,
        "unit": unit,
        "source_file": _basename(source_file),
    }


def _exclusion(code: str, **params: str) -> dict[str, str]:
    row = {"code": code}
    row.update({key: str(value) for key, value in params.items() if value is not None})
    return row


def _waiting(rel: str, columns: tuple[str, ...]) -> dict[str, Any]:
    return {
        "file": _basename(rel),
        "path": rel,
        "exists": (repo_root() / rel).is_file(),
        "columns": list(columns),
    }


def _leaf_shell(leaf_id: str, title: str, org_unit_name: str) -> dict[str, Any]:
    return {
        "id": leaf_id,
        "title": title,
        "outcome": "b",
        "status": "closed",
        "passed": False,
        "kilograms": None,
        "calculated": False,
        "org_unit_name": org_unit_name,
        "product": "Carbon on AASTMT",
        "locked": "2026-10-01",
    }


def _o2() -> dict[str, Any]:
    period = academy_period()
    leaf = _leaf_shell("O2", "South Valley electricity and diesel", "South Valley")
    leaf["tonnes_co2e"] = "0"
    leaf["waiting"] = _waiting(OPEN_PERIOD_FILES["O2"], CAMPUS_COLUMNS)
    leaf["template_columns"] = list(CAMPUS_COLUMNS)
    rows = []
    exclusions = []
    for raw in _read_csv(SV_SCOPE12):
        label = raw.get("activity_data") or raw.get("source") or ""
        quantity = raw.get("quantity") or ""
        unit = raw.get("unit") or ""
        source = raw.get("source") or ""
        rows.append(_activity(f"{source} {label}".strip(), quantity, unit, SV_SCOPE12))
        if label == "Diesel" and "generator" in source.lower():
            continue
        if label == "Diesel" and "vehicle" in source.lower():
            continue
        if label == "Electricity":
            continue
        exclusions.append(_exclusion(
            "outside_named_source", label=label, quantity=quantity, unit=unit,
        ))
    diesel = [row for row in _read_csv(SV_SCOPE12) if row.get("activity_data") == "Diesel"]
    if len(diesel) >= 2:
        by_source = {row.get("source") or "": row.get("quantity") or "" for row in diesel}
        exclusions.append(_exclusion(
            "diesel_stream_both",
            generators_l=by_source.get("On-site generators", ""),
            mobile_l=next((qty for name, qty in by_source.items() if "vehicle" in name.lower()), ""),
        ))
    exclusions.append(_exclusion(
        "period_mismatch",
        file=_basename(SV_SCOPE12),
        file_period="fy2526",
        start=period["start_date"],
        end=period["end_date"],
    ))
    if _read_csv(SV_SCOPE3):
        exclusions.append(_exclusion(
            "outside_named_source",
            label="south_valley_scope3_fy2526.csv",
            quantity="",
            unit="not this leaf",
        ))
    leaf["activity_rows"] = rows
    leaf["exclusions"] = exclusions
    leaf["discovered_files"] = [_basename(SV_SCOPE12)]
    return leaf


def _o3() -> dict[str, Any]:
    period = academy_period()
    leaf = _leaf_shell("O3", "Abu Qir electricity and diesel", "Abu Qir")
    leaf["tonnes_co2e"] = "0"
    leaf["waiting"] = _waiting(OPEN_PERIOD_FILES["O3"], CAMPUS_COLUMNS)
    leaf["template_columns"] = list(CAMPUS_COLUMNS)
    rows = []
    exclusions = []
    for raw in _read_csv(AQ_ELEC):
        month = raw.get("month") or ""
        kwh = raw.get("total_kwh") or ""
        if kwh:
            rows.append(_activity(month, kwh, "kWh", AQ_ELEC))
        else:
            exclusions.append(_exclusion("month_blank", month=month))
    for raw in _read_csv(AQ_FUEL):
        month = raw.get("month") or ""
        if raw.get("diesel_l"):
            rows.append(_activity(f"{month} diesel", raw["diesel_l"], "L", AQ_FUEL))
        if raw.get("gasoline_92_l"):
            exclusions.append(_exclusion(
                "outside_named_source",
                label=f"{month} gasoline 92",
                quantity=raw["gasoline_92_l"],
                unit="L",
            ))
        if raw.get("gasoline_95_l"):
            exclusions.append(_exclusion(
                "outside_named_source",
                label=f"{month} gasoline 95",
                quantity=raw["gasoline_95_l"],
                unit="L",
            ))
    exclusions.append(_exclusion("diesel_stream_unlabelled"))
    exclusions.append(_exclusion(
        "period_mismatch",
        file=_basename(AQ_ELEC),
        file_period="fy2526",
        start=period["start_date"],
        end=period["end_date"],
    ))
    leaf["activity_rows"] = rows
    leaf["exclusions"] = exclusions
    leaf["discovered_files"] = [_basename(AQ_ELEC), _basename(AQ_FUEL)]
    return leaf


def _o4() -> dict[str, Any]:
    leaf = _leaf_shell("O4", "New Alamein electricity and diesel", "New Alamein")
    leaf["tonnes_co2e"] = "0"
    waiting = _waiting(OPEN_PERIOD_FILES["O4"], CAMPUS_COLUMNS)
    leaf["waiting"] = waiting
    leaf["template_columns"] = list(CAMPUS_COLUMNS)
    leaf["activity_rows"] = []
    leaf["discovered_files"] = []
    leaf["exclusions"] = [_exclusion(
        "file_absent",
        file=waiting["file"],
        columns=", ".join(CAMPUS_COLUMNS),
    )]
    return leaf


def _o5() -> dict[str, Any]:
    leaf = _leaf_shell("O5", "Smart Village waste disposal", "Smart Village")
    leaf["tonnes_co2e"] = "0"
    leaf["waiting"] = _waiting(WASTE_FACTOR_FILE, FACTOR_COLUMNS)
    leaf["template_columns"] = list(WASTE_COLUMNS)
    rows = []
    for raw in _read_csv(SV_INVENTORY):
        label = (raw.get("activity_data") or raw.get("source_of_emission") or "").strip()
        if label == "Waste Disposal" and (raw.get("unit") or "").lower() == "ton":
            rows.append(_activity("Waste Disposal", raw.get("quantity") or "", "ton", SV_INVENTORY))
    leaf["activity_rows"] = rows
    leaf["discovered_files"] = [_basename(SV_INVENTORY)]
    quantity = rows[0]["quantity"] if rows else ""
    leaf["exclusions"] = [_exclusion(
        "factor_file_absent",
        file=_basename(WASTE_FACTOR_FILE),
        columns=", ".join(FACTOR_COLUMNS),
        quantity=quantity,
        unit="ton",
    )]
    return leaf


def _s2() -> dict[str, Any]:
    leaf = _leaf_shell("S2MB", "Market-based Scope 2", "Smart Village")
    leaf["tonnes_co2e"] = None
    leaf["method"] = "absent"
    leaf["reason"] = "no_distinct_contractual_factor"
    leaf["template_columns"] = []
    leaf["activity_rows"] = []
    leaf["discovered_files"] = []
    leaf["waiting"] = {
        "file": "ContractualScope2Factor",
        "path": "",
        "exists": False,
        "columns": ["factor_code", "factor_value", "activity_unit", "source", "valid_from"],
    }
    leaf["exclusions"] = [_exclusion("market_absent")]
    return leaf


def _p1() -> dict[str, Any]:
    leaf = _leaf_shell("P1", "External assurance", "")
    leaf["tonnes_co2e"] = None
    leaf["not_assured_met"] = False
    leaf["template_columns"] = [
        "assurer_name", "engagement_type", "standard", "opinion_date", "statement_id",
    ]
    leaf["activity_rows"] = []
    leaf["discovered_files"] = []
    leaf["waiting"] = {
        "file": "AssuranceEngagement",
        "path": "",
        "exists": False,
        "columns": leaf["template_columns"],
    }
    leaf["exclusions"] = [_exclusion("not_assured")]
    return leaf


def intake_catalogue() -> dict[str, Any]:
    return {
        "product": "Carbon on AASTMT",
        "locked": "2026-10-01",
        "open_period": academy_period(),
        "leaves": [_o2(), _o3(), _o4(), _o5(), _s2(), _p1()],
    }


def template_csv(leaf_id: str) -> str:
    columns = {
        "O2": CAMPUS_COLUMNS,
        "O3": CAMPUS_COLUMNS,
        "O4": CAMPUS_COLUMNS,
        "O5": WASTE_COLUMNS,
    }.get(leaf_id)
    if not columns:
        return ""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    return buffer.getvalue()


def _decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def validate_template(leaf_id: str, rows: list[dict]) -> dict[str, Any]:
    """Accept a template upload. A period mismatch is an exclusion, not a kilogram."""
    period = academy_period()
    errors: list[str] = []
    exclusions: list[dict[str, str]] = []
    if leaf_id not in {"O1", "O2", "O3", "O4", "O5"}:
        return {"ok": False, "errors": ["leaf has no activity template"], "exclusions": [], "rows": []}
    columns = WASTE_COLUMNS if leaf_id == "O5" else CAMPUS_COLUMNS
    if not rows:
        errors.append("no rows")
    streams = set()
    cleaned = []
    for index, raw in enumerate(rows):
        item = {key: str(raw.get(key) or "").strip() for key in columns}
        missing = [key for key in columns if not item[key]]
        if missing:
            errors.append(f"row {index} missing {', '.join(missing)}")
            continue
        if item["period_start"] != period["start_date"] or item["period_end"] != period["end_date"]:
            exclusions.append(_exclusion(
                "period_mismatch",
                file="upload",
                file_period=f"{item['period_start']} to {item['period_end']}",
                start=period["start_date"],
                end=period["end_date"],
            ))
            continue
        if leaf_id == "O5":
            qty = _decimal(item["quantity_tonne"])
            if qty is None or qty <= 0:
                errors.append(f"row {index} quantity")
                continue
        else:
            qty = _decimal(item["quantity"])
            if qty is None or qty <= 0:
                errors.append(f"row {index} quantity")
                continue
            stream = item["stream"].lower()
            unit = item["activity_unit"]
            if unit == "litre":
                if stream not in DIESEL_STREAMS:
                    errors.append(f"row {index} stream")
                    continue
                streams.add(stream)
            elif unit == "kWh":
                if stream not in {"location-based", "location_based", "market-based", "market_based"}:
                    errors.append(f"row {index} stream")
                    continue
            else:
                errors.append(f"row {index} unit")
                continue
        cleaned.append(item)
    if len(streams) > 1:
        errors.append("diesel stream both")
    ok = not errors and not exclusions and bool(cleaned)
    return {"ok": ok, "errors": errors, "exclusions": exclusions, "rows": cleaned if ok else []}


def market_kg(activity: Any, contractual_value: Any, grid_value: Any, *, source: str, same_row: bool) -> Decimal | None:
    """Activity times a contractual factor. A grid copy or residual mix returns None."""
    if same_row:
        return None
    if "residual" in (source or "").lower():
        return None
    activity_d = _decimal(activity)
    factor_d = _decimal(contractual_value)
    grid_d = _decimal(grid_value)
    if activity_d is None or factor_d is None or grid_d is None:
        return None
    if factor_d == grid_d:
        return None
    return activity_d * factor_d


def assurance_status(fields: dict | None, period_end) -> dict[str, Any]:
    """not_assured stays unmet until all five VVB fields are present and dated."""
    fields = fields or {}
    missing = []
    if not str(fields.get("assurer_name") or "").strip():
        missing.append("assurer_name")
    engagement = str(fields.get("engagement_type") or "").strip().lower()
    if engagement not in {"limited", "reasonable"}:
        missing.append("engagement_type")
    if str(fields.get("standard") or "").strip() != "ISO 14064-3":
        missing.append("standard")
    opinion = fields.get("opinion_date")
    if not opinion:
        missing.append("opinion_date")
    elif period_end and str(opinion) < str(period_end):
        missing.append("opinion_date")
    if not str(fields.get("statement_id") or "").strip():
        missing.append("statement_id")
    return {"not_assured_met": not missing, "missing": missing, "passed": False}


def user_may_write(user, org_unit_name: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    from accounts.rbac_utils import org_scope_for_capability
    from mdm.models import OrgUnit

    scope = org_scope_for_capability(user, "carbon:enter_data")
    if scope.unrestricted:
        return True
    org = OrgUnit.objects.filter(name=org_unit_name, is_active=True).first()
    return bool(org and org.id in set(scope.ids))


def _open_period_or_none():
    from emissions.models import ReportingPeriod

    periods = list(ReportingPeriod.objects.filter(status="open").order_by("id"))
    if len(periods) != 1:
        return None
    return periods[0]


_BENCHMARK_FILES = (
    "O1-smart-village.yaml",
    "O2-south-valley.yaml",
    "O3-abu-qir.yaml",
    "O4-new-alamein.yaml",
    "O5-scope3-waste.yaml",
)
_LATER_YEAR_FILES = {
    "O2": ["south_valley_scope12_fy2526.csv"],
    "O3": ["abu_qir_monthly_electricity_fy2526.csv", "abu_qir_fuel_fy2526.csv"],
}


def _activity_type(unit: str) -> str:
    if unit == "kWh":
        return "electricity"
    if unit == "litre":
        return "diesel"
    if unit in {"tonne", "ton"}:
        return "waste"
    return "activity"


def required_stream_specs() -> list[dict[str, Any]]:
    """Required streams from the locked benchmark files. No kilograms."""
    specs = []
    root = repo_root() / "domain_packs" / "carbon" / "assurance" / "benchmarks"
    for filename in _BENCHMARK_FILES:
        data = yaml.safe_load((root / filename).read_text(encoding="utf-8")) or {}
        leaf_id = str(data.get("id") or "")
        campus = str(data.get("campus") or "")
        for source in data.get("sources") or []:
            unit = str(source.get("activity_unit") or "")
            scope = int(source["scope"])
            specs.append({
                "id": f"{leaf_id}:{source.get('name')}",
                "leaf_id": leaf_id,
                "campus": campus,
                "org_unit_name": str(source.get("org_unit_name") or campus),
                "source_name": str(source.get("name") or ""),
                "scope": scope,
                "scope3_category": source.get("scope3_category"),
                "activity_unit": unit,
                "activity_type": _activity_type(unit),
                "method": "location_based" if scope == 2 else "",
                "later_year_files": list(_LATER_YEAR_FILES.get(leaf_id) or []),
            })
    return specs


def _blank_result(**extra) -> dict[str, Any]:
    payload = {
        "written": False,
        "kilograms": None,
        "errors": [],
        "exclusions": [],
        "archived_ids": [],
        "current": [],
    }
    payload.update(extra)
    return payload


def _distinct_contractual(factor) -> bool:
    if factor is None or not getattr(factor, "is_active", False):
        return False
    if "residual" in str(getattr(factor, "source", "") or "").lower():
        return False
    from emissions.models import ContractualScope2Factor

    row = (
        ContractualScope2Factor.objects.filter(is_active=True, emission_factor=factor)
        .select_related("grid_factor")
        .first()
    )
    if row is None or row.grid_factor_id == factor.id:
        return False
    if row.grid_factor.factor_value == factor.factor_value:
        return False
    return True


def _source_for(org, spec: dict):
    from emissions.models import InventorySource

    scope3 = spec.get("scope3_category")
    qs = InventorySource.objects.filter(
        org_unit=org,
        scope=spec["scope"],
        source_name=spec["source_name"],
    )
    if scope3 is None:
        qs = qs.filter(scope3_category__isnull=True)
    else:
        qs = qs.filter(scope3_category=scope3)
    return qs.order_by("id").first()


LATER_START = "2025-07-01"
LATER_END = "2026-06-30"


def _locked_later_period():
    """The locked FY 2025-26 period. This does not create it and does not open it."""
    from datetime import date

    from emissions.models import ReportingPeriod

    return (
        ReportingPeriod.objects.filter(
            status="locked",
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
        )
        .order_by("id")
        .first()
    )


def _add_file_row(rows: list[dict[str, str]], **fields: str) -> None:
    rows.append({key: "" if value is None else str(value) for key, value in fields.items()})


def file_activity_rows() -> list[dict[str, str]]:
    """Copy quantities from the named files. A blank cell is not a row and not zero."""
    rows: list[dict[str, str]] = []
    diesel_hits = []
    for raw in _read_csv(SV_SCOPE12):
        label = raw.get("activity_data") or ""
        quantity = raw.get("quantity") or ""
        unit = raw.get("unit") or ""
        source = raw.get("source") or ""
        scope = raw.get("scope") or ""
        if not quantity:
            continue
        if label == "Electricity":
            _add_file_row(
                rows,
                campus="South Valley",
                org_unit_name="South Valley",
                source_name="South Valley electricity",
                named="true",
                leaf_id="O2",
                scope=scope,
                unit=unit,
                quantity=quantity,
                stream=source,
                month="",
                source_file=_basename(SV_SCOPE12),
                period_role="locked",
                in_scope_total="false",
                reason="",
            )
        elif label == "Diesel":
            diesel_hits.append((source, quantity, unit, scope))
        else:
            _add_file_row(
                rows,
                campus="South Valley",
                org_unit_name="South Valley",
                source_name=label or source,
                named="false",
                leaf_id="",
                scope=scope,
                unit=unit,
                quantity=quantity,
                stream=source,
                month="",
                source_file=_basename(SV_SCOPE12),
                period_role="locked",
                in_scope_total="false",
                reason="outside_named_source",
            )
    both = len(diesel_hits) >= 2
    for source, quantity, unit, scope in diesel_hits:
        _add_file_row(
            rows,
            campus="South Valley",
            org_unit_name="South Valley",
            source_name="South Valley diesel",
            named="true",
            leaf_id="O2",
            scope=scope,
            unit=unit,
            quantity=quantity,
            stream=source,
            month="",
            source_file=_basename(SV_SCOPE12),
            period_role="locked",
            in_scope_total="false",
            reason="diesel_stream_both" if both else "",
        )
    for raw in _read_csv(AQ_ELEC):
        month = raw.get("month") or ""
        kwh = raw.get("total_kwh") or ""
        if not kwh:
            continue
        _add_file_row(
            rows,
            campus="Abu Qir",
            org_unit_name="Abu Qir",
            source_name="Abu Qir electricity",
            named="true",
            leaf_id="O3",
            scope="",
            unit="kWh",
            quantity=kwh,
            stream="",
            month=month,
            source_file=_basename(AQ_ELEC),
            period_role="locked",
            in_scope_total="false",
            reason="",
        )
    for raw in _read_csv(AQ_FUEL):
        month = raw.get("month") or ""
        diesel = raw.get("diesel_l") or ""
        if diesel:
            _add_file_row(
                rows,
                campus="Abu Qir",
                org_unit_name="Abu Qir",
                source_name="Abu Qir diesel",
                named="true",
                leaf_id="O3",
                scope="",
                unit="L",
                quantity=diesel,
                stream="",
                month=month,
                source_file=_basename(AQ_FUEL),
                period_role="locked",
                in_scope_total="false",
                reason="diesel_stream_unlabelled",
            )
        for column, label in (("gasoline_92_l", "gasoline 92"), ("gasoline_95_l", "gasoline 95")):
            qty = raw.get(column) or ""
            if not qty:
                continue
            _add_file_row(
                rows,
                campus="Abu Qir",
                org_unit_name="Abu Qir",
                source_name=label,
                named="false",
                leaf_id="",
                scope="",
                unit="L",
                quantity=qty,
                stream="",
                month=month,
                source_file=_basename(AQ_FUEL),
                period_role="locked",
                in_scope_total="false",
                reason="outside_named_source",
            )
    for raw in _read_csv(SV_INVENTORY):
        label = (raw.get("activity_data") or raw.get("source_of_emission") or "").strip()
        quantity = raw.get("quantity") or ""
        if label == "Waste Disposal" and (raw.get("unit") or "").lower() == "ton" and quantity:
            _add_file_row(
                rows,
                campus="Smart Village",
                org_unit_name="Smart Village",
                source_name="Smart Village waste disposal",
                named="true",
                leaf_id="O5",
                scope=raw.get("scope") or "",
                unit=raw.get("unit") or "ton",
                quantity=quantity,
                stream="",
                month="",
                source_file=_basename(SV_INVENTORY),
                period_role="open",
                in_scope_total="false",
                reason="awaiting_factor",
            )
    return rows


def _base_stream(spec: dict, user) -> dict[str, Any]:
    org_name = spec["org_unit_name"]
    return {
        "id": spec["id"],
        "leaf_id": spec["leaf_id"],
        "campus": spec["campus"],
        "org_unit_name": org_name,
        "source_name": spec["source_name"],
        "scope": spec["scope"],
        "scope3_category": spec["scope3_category"],
        "activity_type": spec["activity_type"],
        "activity_unit": spec["activity_unit"],
        "method": spec["method"] or None,
        "status": "missing",
        "reason": None,
        "inventory_kg": None,
        "in_scope_total": False,
        "later_year_files": spec["later_year_files"],
        "writable": user_may_write(user, org_name) if user is not None else False,
        "screen": "/carbon/onboarding/intake",
    }


def _stream_for(spec: dict, period, user) -> dict[str, Any]:
    """Status for one required stream on one period. Kilograms only from that period's calculations."""
    from dataschema.models import DataRow
    from emissions.models import Calculation, InventorySourceStatus
    from mdm.models import OrgUnit

    row = _base_stream(spec, user)
    row["period_id"] = period.id
    row["period_name"] = period.name
    row["period_status"] = period.status
    org = OrgUnit.objects.filter(name=spec["org_unit_name"], is_active=True).first()
    source = _source_for(org, spec) if org is not None else None
    status = None
    if source is not None:
        status = (
            InventorySourceStatus.objects.filter(source=source, reporting_period=period)
            .order_by("id")
            .first()
        )
    if status is not None and status.status == "excluded" and status.exclusion_reason:
        notes = (status.notes or "").strip()
        if status.exclusion_reason == "other" and not notes:
            row["reason"] = "exclusion_notes"
        else:
            row["status"] = "excluded"
            row["reason"] = status.exclusion_reason
        return row
    linked_ids = []
    if status is not None:
        linked_ids = list(status.linked_tables.values_list("id", flat=True))
    calcs = Calculation.objects.none()
    if linked_ids:
        calcs = Calculation.objects.filter(
            reporting_period=period,
            is_stale=False,
            superseded_by__isnull=True,
            data_row__is_archived=False,
            data_row__data_table_id__in=linked_ids,
        )
    if linked_ids and calcs.exists():
        total = sum((calc.co2e_kg for calc in calcs), Decimal("0"))
        row["status"] = "entered"
        row["inventory_kg"] = format(total, "f")
        row["in_scope_total"] = True
        if spec["scope"] == 2:
            methods = {calc.scope2_method for calc in calcs if calc.scope2_method}
            row["method"] = next(iter(methods), "location_based")
        return row
    start = period.start_date.isoformat()
    end = period.end_date.isoformat()
    live = DataRow.objects.filter(
        is_archived=False,
        values__source_name=spec["source_name"],
        values__period_start=start,
        values__period_end=end,
    )
    if org is not None:
        live = live.filter(data_table__module__org_unit=org)
    if not live.exists():
        return row
    reasons = {(item.values or {}).get("reason") or "" for item in live}
    reasons.discard("")
    row["inventory_kg"] = None
    row["in_scope_total"] = False
    if spec["leaf_id"] == "O5" or "awaiting_factor" in reasons:
        row["status"] = "awaiting_factor"
        row["reason"] = "awaiting_factor"
        return row
    row["status"] = "entered"
    if "diesel_stream_both" in reasons:
        row["reason"] = "diesel_stream_both"
    elif "diesel_stream_unlabelled" in reasons:
        row["reason"] = "diesel_stream_unlabelled"
    return row


def _period_board(period, user, role: str) -> dict[str, Any]:
    return {
        "id": period.id,
        "name": period.name,
        "status": period.status,
        "role": role,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "streams": [_stream_for(spec, period, user) for spec in required_stream_specs()],
    }


def coverage_board(user=None) -> dict[str, Any]:
    """Required streams for the open period and, when it exists, locked FY 2025-26.

    A percent is not returned. Inventory kilograms come only from calculations
    on that same period. Later-year activity does not mark the open period entered.
    """
    period = _open_period_or_none()
    locked = _locked_later_period()
    periods = []
    if period is not None:
        periods.append(_period_board(period, user, "open"))
    if locked is not None and (period is None or locked.id != period.id):
        periods.append(_period_board(locked, user, "locked"))
    if period is None:
        streams = []
        for spec in required_stream_specs():
            row = _base_stream(spec, user)
            row["reason"] = "open_period_count"
            streams.append(row)
    else:
        streams = next(item["streams"] for item in periods if item["role"] == "open")
    return {
        "product": "Carbon on AASTMT",
        "locked": "2026-10-01",
        "coverage_complete": False,
        "open_period": None if period is None else {
            "id": period.id,
            "name": period.name,
            "status": period.status,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "periods": periods,
        "streams": streams,
    }


def open_period_inventory_kg() -> dict[str, str] | None:
    """Sum of Calculation.co2e_kg on the single open period. Later years are not included."""
    period = _open_period_or_none()
    if period is None:
        return None
    from emissions.models import Calculation

    totals: dict[str, Decimal] = {}
    calcs = Calculation.objects.filter(
        reporting_period=period,
        is_stale=False,
        superseded_by__isnull=True,
        data_row__is_archived=False,
    )
    for calc in calcs:
        key = str(calc.scope)
        totals[key] = totals.get(key, Decimal("0")) + calc.co2e_kg
    return {key: format(value, "f") for key, value in totals.items()}


def store_discovered_activity(*, user) -> dict[str, Any]:
    """Store file quantities on the period they belong to. Never calculates them.

    FY 2025-26 rows land on the locked period. Waste 73.0 ton lands on the
    open period with inventory kg absent. This does not open a period, does
    not archive an existing row, and does not create a Calculation.
    """
    from django.conf import settings

    from core.models import Module
    from dataschema.models import DataField, DataRow, DataTable, normalize_name
    from mdm.models import OrgUnit

    if getattr(settings, "EMISSIONS_AUTO_CALC", False):
        return _blank_result(errors=["auto calc"])
    open_period = _open_period_or_none()
    locked = _locked_later_period()
    window = academy_period()
    exclusions: list[dict[str, str]] = []
    if locked is None:
        exclusions.append(_exclusion("locked_period_absent"))
    if open_period is None:
        exclusions.append(_exclusion("open_period_count"))
    elif (
        open_period.start_date.isoformat() != window["start_date"]
        or open_period.end_date.isoformat() != window["end_date"]
    ):
        exclusions.append(_exclusion(
            "period_mismatch",
            file="open",
            file_period="dates",
            start=window["start_date"],
            end=window["end_date"],
        ))
        open_period = None
    stored = []
    skipped = []
    for item in file_activity_rows():
        target = locked if item["period_role"] == "locked" else open_period
        if target is None:
            skipped.append(item["source_name"])
            continue
        if item["period_role"] == "locked" and target.status != "locked":
            skipped.append(item["source_name"])
            continue
        if "fy2526" in item["source_file"] and open_period is not None and target.id == open_period.id:
            exclusions.append(_exclusion(
                "period_mismatch",
                file=item["source_file"],
                file_period="fy2526",
                start=open_period.start_date.isoformat(),
                end=open_period.end_date.isoformat(),
            ))
            continue
        if not user_may_write(user, item["org_unit_name"]):
            skipped.append(item["source_name"])
            continue
        org = OrgUnit.objects.filter(name=item["org_unit_name"], is_active=True).first()
        if org is None:
            exclusions.append(_exclusion("org_absent", label=item["org_unit_name"]))
            skipped.append(item["source_name"])
            continue
        start = target.start_date.isoformat()
        end = target.end_date.isoformat()
        activity_key = "|".join([
            item["source_file"], item["source_name"], item["month"], item["quantity"], item["unit"], item["stream"], start,
        ])
        already = DataRow.objects.filter(is_archived=False, values__activity_key=activity_key)
        if item["leaf_id"] == "O5":
            already = already | DataRow.objects.filter(
                is_archived=False,
                values__source_name=item["source_name"],
                values__quantity_tonne=item["quantity"],
                values__period_start=start,
            )
        if already.exists():
            skipped.append(activity_key)
            continue
        label = item["source_name"] if item["named"] == "true" else f"{item['campus']} {item['source_name']}"
        module, _ = Module.objects.get_or_create(
            name=f"Campus intake {label}"[:100],
            defaults={"description": "P-26", "scope": 3 if item["leaf_id"] == "O5" else (2 if item["unit"] == "kWh" else 1), "org_unit": org},
        )
        if module.org_unit_id != org.id:
            module.org_unit = org
            module.save(update_fields=["org_unit"])
        table_name = normalize_name(f"intake {label}")[:64]
        table, _ = DataTable.objects.get_or_create(
            module=module,
            name=table_name,
            defaults={"title": label},
        )
        values = {
            "campus": item["campus"],
            "source_name": item["source_name"],
            "scope": item["scope"],
            "unit": item["unit"],
            "quantity": item["quantity"],
            "stream": item["stream"],
            "month": item["month"],
            "source_file": item["source_file"],
            "period_start": start,
            "period_end": end,
            "in_scope_total": item["in_scope_total"],
            "reason": item["reason"],
            "activity_key": activity_key,
        }
        if item["leaf_id"] == "O5":
            values["quantity_tonne"] = item["quantity"]
        for column, kind in (
            ("campus", "text"),
            ("source_name", "text"),
            ("scope", "text"),
            ("unit", "text"),
            ("quantity", "text"),
            ("quantity_tonne", "text"),
            ("stream", "text"),
            ("month", "text"),
            ("source_file", "text"),
            ("period_start", "text"),
            ("period_end", "text"),
            ("in_scope_total", "text"),
            ("reason", "text"),
            ("activity_key", "text"),
        ):
            DataField.objects.get_or_create(
                data_table=table,
                name=column,
                defaults={"label": column, "type": kind},
            )
        created = DataRow.objects.create(
            data_table=table,
            values=values,
            created_by=user if getattr(user, "pk", None) else None,
            version=1,
        )
        if item["named"] == "true":
            spec = next((candidate for candidate in required_stream_specs() if candidate["source_name"] == item["source_name"]), None)
            if spec is not None:
                _sync_coverage(
                    org=org,
                    spec=spec,
                    period=target,
                    table=table,
                    calculated=False,
                    stream_word="",
                )
        stored.append({
            "id": created.id,
            "source_name": item["source_name"],
            "quantity": item["quantity"],
            "unit": item["unit"],
            "source_file": item["source_file"],
            "campus": item["campus"],
            "period_id": target.id,
            "period_status": target.status,
        })
    if locked is not None:
        locked.refresh_from_db()
    if open_period is not None:
        open_period.refresh_from_db()
    return {
        "written": bool(stored),
        "kilograms": None,
        "errors": [],
        "exclusions": exclusions,
        "archived_ids": [],
        "current": stored,
        "skipped": skipped,
    }


def _sync_coverage(*, org, spec: dict, period, table, calculated: bool, stream_word: str):
    if org is None or period is None:
        return
    from emissions.models import InventorySource, InventorySourceStatus

    source = _source_for(org, spec)
    if source is None:
        source = InventorySource(
            org_unit=org,
            scope=spec["scope"],
            scope3_category=spec.get("scope3_category"),
            source_name=spec["source_name"],
            description=stream_word if spec["activity_unit"] == "litre" else "",
            scope2_method="location_based" if spec["scope"] == 2 else "",
        )
        source.save()
    elif spec["activity_unit"] == "litre" and stream_word in DIESEL_STREAMS:
        if source.description != stream_word:
            source.description = stream_word
            source.save(update_fields=["description"])
    status, _ = InventorySourceStatus.objects.get_or_create(
        source=source,
        reporting_period=period,
        defaults={
            "status": "covered" if calculated else "declared",
            "data_quality_tier": 4 if calculated else None,
        },
    )
    if calculated:
        status.status = "covered"
        status.data_quality_tier = status.data_quality_tier or 4
        status.exclusion_reason = None
        status.save(update_fields=["status", "data_quality_tier", "exclusion_reason"])
        status.linked_tables.add(table)
        return
    if status.status != "excluded":
        status.status = "declared"
        status.save(update_fields=["status"])


def apply_template(*, leaf_id: str, rows: list[dict], user, factor=None) -> dict[str, Any]:
    """Append-only restatement. Writes nothing when validation fails.

    A factor produces a Calculation only when the row matches the single
    open period and the factor unit is legal. EMISSIONS_AUTO_CALC is not
    changed. The module is the campus org, so My Data lists the same rows.
    """
    check = validate_template(leaf_id, rows)
    if not check["ok"]:
        return _blank_result(errors=check["errors"], exclusions=check["exclusions"])
    org_name = {
        "O1": "Smart Village",
        "O2": "South Valley",
        "O3": "Abu Qir",
        "O4": "New Alamein",
        "O5": "Smart Village",
    }[leaf_id]
    if not user_may_write(user, org_name):
        return _blank_result(errors=["org scope"])
    period = _open_period_or_none()
    if period is None:
        return _blank_result(errors=["open period count"], exclusions=[_exclusion("open_period_count")])
    open_start = period.start_date.isoformat()
    open_end = period.end_date.isoformat()
    if any(item["period_start"] != open_start or item["period_end"] != open_end for item in check["rows"]):
        return _blank_result(exclusions=[_exclusion(
            "period_mismatch",
            file="upload",
            file_period="open period dates differ",
            start=open_start,
            end=open_end,
        )])
    from core.models import Module
    from dataschema.models import DataField, DataRow, DataTable, normalize_name
    from emissions.models import Calculation
    from mdm.models import OrgUnit

    source_name = check["rows"][0]["source_name"]
    scope_value = 3 if leaf_id == "O5" else int(check["rows"][0]["scope"])
    org = OrgUnit.objects.filter(name=org_name, is_active=True).first()
    module, _ = Module.objects.get_or_create(
        name=f"Campus intake {source_name}"[:100],
        defaults={"description": "CR-INT-01", "scope": scope_value, "org_unit": org},
    )
    dirty = []
    if module.scope != scope_value:
        module.scope = scope_value
        dirty.append("scope")
    if org is not None and module.org_unit_id != org.id:
        module.org_unit = org
        dirty.append("org_unit")
    if dirty:
        module.save(update_fields=dirty)
    table_name = normalize_name(f"intake {source_name}")[:64]
    table, _ = DataTable.objects.get_or_create(
        module=module,
        name=table_name,
        defaults={"title": source_name},
    )
    quantity_name = "quantity_tonne" if leaf_id == "O5" else "quantity"
    columns = WASTE_COLUMNS if leaf_id == "O5" else CAMPUS_COLUMNS
    for column in columns:
        DataField.objects.get_or_create(
            data_table=table,
            name=column,
            defaults={"label": column, "type": "number" if column in {"quantity", "quantity_tonne"} else "text"},
        )
    holds = []
    accepted = []
    for item in check["rows"]:
        stream_word = str(item.get("stream") or "").lower()
        if stream_word.replace("_", "-") == "market-based" and not _distinct_contractual(factor):
            holds.append(_exclusion("market_absent"))
            continue
        accepted.append(item)
    if not accepted:
        return _blank_result(exclusions=holds)
    source_names = {item["source_name"] for item in accepted}
    archived_ids = []
    live = [
        old for old in DataRow.objects.filter(data_table=table, is_archived=False).order_by("id")
        if (old.values or {}).get("source_name") in source_names
    ]
    next_version = 1
    for old in live:
        old.is_archived = True
        old.save(update_fields=["is_archived"])
        archived_ids.append(old.id)
        next_version = max(next_version, int(old.version or 1) + 1)
    current = []
    kilograms = []
    calculated = False
    stream_word = ""
    for item in accepted:
        values = {key.lower(): value for key, value in item.items()}
        stream_word = str(item.get("stream") or "").lower()
        wants_market = stream_word.replace("_", "-") == "market-based"
        row = DataRow.objects.create(
            data_table=table,
            values=values,
            created_by=user if getattr(user, "pk", None) else None,
            version=next_version,
        )
        current.append({"id": row.id, "values": row.values})
        qty = _decimal(item.get(quantity_name))
        unit_ok = False
        if factor is not None and qty is not None:
            unit_ok = (
                (leaf_id == "O5" and factor.activity_unit == "tonne" and int(factor.scope) == 3)
                or (
                    leaf_id != "O5"
                    and factor.activity_unit == item["activity_unit"]
                    and factor.is_active
                    and str(factor.source or "").strip()
                    and factor.valid_from
                )
            )
        if unit_ok:
            method = "market_based" if wants_market else "location_based"
            calc = Calculation.create_from_data_row(
                data_row=row,
                emission_factor=factor,
                activity_value=qty,
                activity_unit=factor.activity_unit,
                reporting_year=period.start_date.year,
                reporting_period=period,
                calculated_by=user if getattr(user, "pk", None) else None,
                scope2_method=method if int(factor.scope) == 2 else None,
            )
            kilograms.append(str(calc.co2e_kg))
            calculated = True
        else:
            holds.append(_exclusion(
                "awaiting_factor",
                quantity=str(item.get(quantity_name) or ""),
                unit=item.get("activity_unit") or ("tonne" if leaf_id == "O5" else ""),
            ))
    if not current and holds:
        return _blank_result(errors=[], exclusions=holds, archived_ids=archived_ids)
    spec = next((item for item in required_stream_specs() if item["source_name"] == source_name and item["leaf_id"] == leaf_id), None)
    if spec is None and leaf_id != "O1":
        spec = {
            "source_name": source_name,
            "scope": scope_value,
            "scope3_category": 5 if leaf_id == "O5" else None,
            "activity_unit": "tonne" if leaf_id == "O5" else check["rows"][0].get("activity_unit"),
        }
    if spec is not None:
        _sync_coverage(
            org=org,
            spec=spec,
            period=period,
            table=table,
            calculated=calculated,
            stream_word=stream_word,
        )
    return {
        "written": True,
        "kilograms": kilograms or None,
        "errors": [],
        "exclusions": holds,
        "archived_ids": archived_ids,
        "current": current,
    }


def enter_activity(*, user, fields: dict, factor=None) -> dict[str, Any]:
    """One missing stream, same DataRow path as a template upload."""
    source_name = str((fields or {}).get("source_name") or "").strip()
    spec = next((item for item in required_stream_specs() if item["source_name"] == source_name), None)
    if spec is None:
        return _blank_result(errors=["source"])
    if not user_may_write(user, spec["org_unit_name"]):
        return _blank_result(errors=["org scope"])
    period = academy_period()
    method = str((fields or {}).get("method") or "location_based").strip().lower().replace("-", "_")
    if spec["scope"] == 2 and method == "market_based" and not _distinct_contractual(factor):
        return _blank_result(exclusions=[_exclusion("market_absent")])
    if spec["leaf_id"] == "O5":
        row = {
            "source_name": source_name,
            "quantity_tonne": str((fields or {}).get("quantity") or "").strip(),
            "treatment": str((fields or {}).get("treatment") or "unspecified").strip() or "unspecified",
            "period_start": period["start_date"],
            "period_end": period["end_date"],
        }
    else:
        stream = str((fields or {}).get("stream") or "").strip().lower()
        if spec["activity_unit"] == "kWh":
            stream = "market-based" if method == "market_based" else "location-based"
        elif stream not in DIESEL_STREAMS:
            return _blank_result(errors=["stream"])
        row = {
            "campus": spec["campus"],
            "source_name": source_name,
            "scope": str(spec["scope"]),
            "activity_unit": spec["activity_unit"],
            "quantity": str((fields or {}).get("quantity") or "").strip(),
            "stream": stream,
            "period_start": period["start_date"],
            "period_end": period["end_date"],
        }
    return apply_template(leaf_id=spec["leaf_id"], rows=[row], user=user, factor=factor)


def record_contractual_factor(*, contractual, grid):
    from emissions.models import ContractualScope2Factor

    row = ContractualScope2Factor(emission_factor=contractual, grid_factor=grid)
    row.save()
    return row


def record_assurance(*, reporting_period, fields: dict):
    from emissions.models import AssuranceEngagement

    row = AssuranceEngagement.objects.create(
        reporting_period=reporting_period,
        assurer_name=str(fields.get("assurer_name") or "").strip(),
        engagement_type=str(fields.get("engagement_type") or "").strip().lower(),
        standard=str(fields.get("standard") or "").strip(),
        opinion_date=fields.get("opinion_date") or None,
        statement_id=str(fields.get("statement_id") or "").strip(),
    )
    return assurance_status(
        {
            "assurer_name": row.assurer_name,
            "engagement_type": row.engagement_type,
            "standard": row.standard,
            "opinion_date": row.opinion_date,
            "statement_id": row.statement_id,
        },
        reporting_period.end_date,
    )
