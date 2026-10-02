"""Coverage targets — layer 1 of the two-layer Coverage model (locked 2 Oct 2026).

Coverage has TWO layers:
  * TARGETS  — a period-scoped KPI goal (percent or absolute) with a quality
    floor, a due date, and an owner. Progress is DERIVED from real rows.
  * STREAMS  — the declared universe (InventorySource + InventorySourceStatus)
    the targets are measured over. Coverage is the only reporter of
    Missing / Entered / Excluded.

A target owns TASKS; a task is done only on host evidence. Nothing here writes
a kilogram, opens a period, or promotes a CoverageGoal.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

# ── Scope helpers ──────────────────────────────────────────────────────────


def parse_scopes(scope: Any) -> set[int]:
    """'1+2' -> {1, 2}. Anything unparseable yields an empty set (no universe)."""
    parts = str(scope or "").replace(" ", "").split("+")
    scopes: set[int] = set()
    for part in parts:
        if part in {"1", "2", "3"}:
            scopes.add(int(part))
    return scopes


def target_sources(target):
    """Active InventorySource rows in the target's org unit × scope × category."""
    from emissions.models import InventorySource

    scopes = parse_scopes(target.scope)
    if not scopes:
        return InventorySource.objects.none()
    qs = InventorySource.objects.filter(
        is_active=True, org_unit_id=target.org_unit_id, scope__in=scopes
    )
    if target.scope3_category is not None:
        qs = qs.filter(scope3_category=target.scope3_category)
    return qs.order_by("scope", "scope3_category", "source_name", "id")


# ── Per-stream state (mirrors campus_intake._stream_for, period-parameterised) ──


def source_state(source, period) -> dict[str, Any]:
    """One stream's Missing / Entered / Excluded / Awaiting-factor on ONE period.

    Kilograms come only from Calculations on that same period (CR-COV-01). A
    missing stream is not 0 kg.
    """
    from dataschema.models import DataRow
    from emissions.models import Calculation, InventorySourceStatus

    status = (
        InventorySourceStatus.objects.filter(source=source, reporting_period=period)
        .order_by("id")
        .first()
    )
    if status is not None and status.status == "excluded" and status.exclusion_reason:
        notes = (status.notes or "").strip()
        if status.exclusion_reason == "other" and not notes:
            return {"status": "missing", "reason": "exclusion_notes", "inventory_kg": None}
        return {"status": "excluded", "reason": status.exclusion_reason, "inventory_kg": None}

    linked_ids = list(status.linked_tables.values_list("id", flat=True)) if status is not None else []
    if linked_ids:
        calcs = Calculation.objects.filter(
            reporting_period=period,
            is_stale=False,
            superseded_by__isnull=True,
            data_row__is_archived=False,
            data_row__data_table_id__in=linked_ids,
        )
        if calcs.exists():
            total = sum((calc.co2e_kg for calc in calcs), Decimal("0"))
            return {"status": "entered", "reason": None, "inventory_kg": format(total, "f")}

    start = period.start_date.isoformat()
    end = period.end_date.isoformat()
    live = DataRow.objects.filter(
        is_archived=False,
        values__source_name=source.source_name,
        values__period_start=start,
        values__period_end=end,
        data_table__module__org_unit_id=source.org_unit_id,
    )
    if live.exists():
        reasons = {(row.values or {}).get("reason") or "" for row in live}
        if "awaiting_factor" in reasons:
            return {"status": "awaiting_factor", "reason": "awaiting_factor", "inventory_kg": None}
        return {"status": "entered", "reason": None, "inventory_kg": None}
    return {"status": "missing", "reason": None, "inventory_kg": None}


# ── Target progress (derived from real rows only) ──────────────────────────

_COUNT_KEYS = ("required", "entered", "excluded", "awaiting_factor", "missing")


def target_progress(target) -> dict[str, Any]:
    """Counts + a measured ratio for a target. Never a claimed coverage percent.

    ``measured_pct`` counts entered + excluded streams over required streams on
    the target's period. It is labelled ``measured_not_claimed`` and the payload
    never says coverage_complete. ``measured_kg`` is populated only from real
    Calculations on that period; an absolute goal reports it, else null.
    """
    counts = {key: 0 for key in _COUNT_KEYS}
    streams: list[dict[str, Any]] = []
    measured_kg = Decimal("0")
    has_kg = False
    for source in target_sources(target):
        state = source_state(source, target.reporting_period)
        counts["required"] += 1
        counts[state["status"]] = counts.get(state["status"], 0) + 1
        streams.append({
            "inventory_source_id": source.id,
            "source_name": source.source_name,
            "scope": source.scope,
            "scope3_category": source.scope3_category,
            "status": state["status"],
            "reason": state["reason"],
            "inventory_kg": state["inventory_kg"],
        })
        if state["inventory_kg"] is not None:
            measured_kg += Decimal(state["inventory_kg"])
            has_kg = True

    settled = counts["entered"] + counts["excluded"]
    measured_pct = None
    if counts["required"]:
        measured_pct = format(
            Decimal(settled) * Decimal("100") / Decimal(counts["required"]), ".2f"
        )

    if counts["required"] == 0:
        state = "empty"
    elif target.goal_kind == "percent":
        state = "met" if Decimal(measured_pct or "0") >= target.goal_value else "short"
    else:
        state = "met" if has_kg and measured_kg >= target.goal_value else "short"

    return {
        "counts": counts,
        "measured_pct": measured_pct,
        "measured_kg": format(measured_kg, "f") if has_kg else None,
        "state": state,
        "basis": "streams_with_a_real_row_on_the_target_period",
        "claim": "measured_not_claimed",
        "coverage_complete": False,
        "streams": streams,
    }


# ── Task evidence (host objects, never a hand-set done) ────────────────────

_PROBE_FIELDS = (
    "task_type", "status", "data_table", "stream_source", "factor", "through_month", "target",
)


def probe_task(instance, attrs: dict):
    """A transient CoverageTask with the intended writes applied (for evidence)."""
    from emissions.models import CoverageTask

    task = CoverageTask()
    for field in _PROBE_FIELDS:
        if field in attrs:
            setattr(task, field, attrs[field])
        elif instance is not None:
            setattr(task, field, getattr(instance, field))
    return task


def _rows_reach(task) -> bool:
    """True when a real DataRow on the bound table(s) has a month in range."""
    from dataschema.models import DataRow
    from emissions.models import InventorySourceStatus

    period = task.target.reporting_period if task.target_id else None
    if period is None or task.through_month is None:
        return False
    table_ids: list[int] = []
    if task.data_table_id:
        table_ids.append(task.data_table_id)
    if task.stream_source_id:
        status = (
            InventorySourceStatus.objects.filter(
                source_id=task.stream_source_id, reporting_period=period
            )
            .order_by("id")
            .first()
        )
        if status is not None:
            table_ids += list(status.linked_tables.values_list("id", flat=True))
    if not table_ids:
        return False
    start = period.start_date.isoformat()
    through = task.through_month.isoformat()
    rows = DataRow.objects.filter(is_archived=False, data_table_id__in=table_ids).only("values")
    for row in rows:
        month = str((row.values or {}).get("month") or "")[:10]
        if month and start <= month <= through:
            return True
    return False


def task_evidence(task) -> dict[str, Any]:
    """Host evidence for a task type. ``met`` is the only gate for done."""
    codes: list[str] = []
    met = False

    if task.task_type == "bind_data_product":
        table = task.data_table if task.data_table_id else None
        if table is not None and not getattr(table, "is_archived", False):
            met = True
        else:
            codes.append("data_table_unbound")
    elif task.task_type == "complete_rows":
        if task.stream_source_id is None and task.data_table_id is None:
            codes.append("stream_required")
        elif task.through_month is None:
            codes.append("through_month_required")
        elif _rows_reach(task):
            met = True
        else:
            codes.append("rows_not_complete")
    elif task.task_type == "fill_gap":
        if task.stream_source_id is None:
            codes.append("stream_required")
        elif task.target_id is None:
            codes.append("target_required")
        else:
            state = source_state(task.stream_source, task.target.reporting_period)
            if state["status"] in ("entered", "excluded"):
                met = True
            else:
                codes.append("gap_still_missing")
    elif task.task_type == "secure_factor":
        factor = task.factor if task.factor_id else None
        if factor is not None and getattr(factor, "is_active", False):
            met = True
        else:
            codes.append("factor_inactive")
    else:  # other — no host binding; the status itself is the record
        met = task.status == "done"

    return {"met": bool(met), "codes": codes, "claim": "host_evidence_only"}
