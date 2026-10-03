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


# An absolute goal is an EMISSIONS-VALUE target, not a coverage KPI: its unit
# must be a CO2e mass unit. ``kgCO2e`` is canonical; these map a goal unit to
# the kilograms in one unit.
_CO2E_UNIT_FACTORS = {
    "kgco2e": (Decimal("1"), "kgCO2e"),
    "kgco2eq": (Decimal("1"), "kgCO2e"),
    "tco2e": (Decimal("1000"), "tCO2e"),
    "tco2eq": (Decimal("1000"), "tCO2e"),
    "tonneco2e": (Decimal("1000"), "tCO2e"),
    "tonnesco2e": (Decimal("1000"), "tCO2e"),
}


def normalize_unit(unit: Any) -> str:
    """Case/space/₂-insensitive unit key used for the CO2e mass lookup."""
    return str(unit or "").strip().lower().replace("₂", "2").replace(" ", "")


def co2e_unit_factor(unit: Any) -> Decimal | None:
    """Kilograms in one ``unit`` for a CO2e mass unit, else None."""
    entry = _CO2E_UNIT_FACTORS.get(normalize_unit(unit))
    return entry[0] if entry else None


def canonical_co2e_unit(unit: Any) -> str | None:
    """Canonical label ('kgCO2e' / 'tCO2e') for a CO2e mass unit, else None."""
    entry = _CO2E_UNIT_FACTORS.get(normalize_unit(unit))
    return entry[1] if entry else None


def _pct(numerator: int, denominator: int) -> str | None:
    """Two-decimal percent, or None when there is no denominator."""
    if not denominator:
        return None
    return format(Decimal(numerator) * Decimal("100") / Decimal(denominator), ".2f")


# ── Target boundary (org unit × descendants × scope × category) ─────────────


def target_sources(target):
    """Active InventorySource rows in the target's boundary × scope × category.

    The boundary is the target's org unit **and all of its descendants**: a
    whole-campus target must see the streams declared on its child units, not
    only the ones bound directly on the campus. ``include_self=True`` keeps a
    source bound on the target's own unit in scope.
    """
    from emissions.models import InventorySource

    scopes = parse_scopes(target.scope)
    if not scopes:
        return InventorySource.objects.none()
    org_unit = target.org_unit
    if org_unit is not None:
        org_ids = org_unit.get_descendant_ids(include_self=True)
    else:  # pragma: no cover — org_unit is a non-null FK
        org_ids = {target.org_unit_id}
    qs = InventorySource.objects.filter(
        is_active=True, org_unit_id__in=org_ids, scope__in=scopes
    )
    if target.scope3_category is not None:
        qs = qs.filter(scope3_category=target.scope3_category)
    return qs.select_related("org_unit").order_by(
        "scope", "scope3_category", "source_name", "id"
    )


# ── Per-stream state (mirrors campus_intake._stream_for, period-parameterised) ──


def source_state(source, period) -> dict[str, Any]:
    """One stream's Missing / Entered / Excluded / Awaiting-factor / In-progress on ONE period.

    Kilograms come only from Calculations on that same period (CR-COV-01). A
    missing stream is not 0 kg.

    ``entered`` is the locked L-COVERED definition: the linked table is
    populated AND a Calculation exists on that same period. A raw DataRow that
    has not produced a Calculation yet is ``in_progress`` — it is NOT entered,
    so it never borrows the contract's 'covered' prestige.

    ``tier`` is the stream's declared PCAF quality tier
    (``InventorySourceStatus.data_quality_tier``) when one exists, else None.
    ``covered`` is True only for the Calculation-backed path.
    """
    from dataschema.models import DataRow
    from emissions.models import Calculation, InventorySourceStatus

    status = (
        InventorySourceStatus.objects.filter(source=source, reporting_period=period)
        .order_by("id")
        .first()
    )
    tier = status.data_quality_tier if status is not None else None

    if status is not None and status.status == "excluded" and status.exclusion_reason:
        notes = (status.notes or "").strip()
        if status.exclusion_reason == "other" and not notes:
            return {
                "status": "missing", "reason": "exclusion_notes",
                "inventory_kg": None, "tier": tier, "covered": False,
            }
        return {
            "status": "excluded", "reason": status.exclusion_reason,
            "inventory_kg": None, "tier": tier, "covered": False,
        }

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
            return {
                "status": "entered", "reason": None,
                "inventory_kg": format(total, "f"), "tier": tier, "covered": True,
            }

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
            return {
                "status": "awaiting_factor", "reason": "awaiting_factor",
                "inventory_kg": None, "tier": tier, "covered": False,
            }
        # A raw row exists but no Calculation on this period yet: NOT entered.
        return {
            "status": "in_progress", "reason": None,
            "inventory_kg": None, "tier": tier, "covered": False,
        }
    return {
        "status": "missing", "reason": None,
        "inventory_kg": None, "tier": tier, "covered": False,
    }


# ── Target progress (derived from real rows only) ──────────────────────────

_COUNT_KEYS = (
    "required", "entered", "excluded", "awaiting_factor", "missing",
    "in_progress", "measured", "settled", "settled_at_target",
    "below_floor", "tier_unknown",
)

# ── Gaps → next actions (derived from the live stream states) ───────────────
# A gap is a REAL, currently-open reason a stream is not measured at target.
# Each entry names the existing COUNTER(S) that respond when the real row lands
# (the causal link, never a fabricated percent) and a stable verb id the UI
# localizes. Nothing here is user-facing copy, and nothing is hardcoded per
# target: the affected streams are collected from the live stream states below.
_GAP_MOVES: dict[str, tuple[str, ...]] = {
    "no_declared_sources": (),
    "missing": ("entered", "measured"),
    "in_progress": ("entered", "measured"),
    "awaiting_factor": ("entered", "measured"),
    "below_floor": ("settled_at_target",),
    "tier_unknown": ("settled_at_target", "tier_unknown"),
}
_GAP_VERBS: dict[str, str] = {
    "no_declared_sources": "declare_sources",
    "missing": "enter_stream",
    "in_progress": "complete_entry",
    "awaiting_factor": "secure_factor",
    "below_floor": "improve_quality",
    "tier_unknown": "declare_tier",
}
_GAP_ORDER = (
    "no_declared_sources", "missing", "in_progress",
    "awaiting_factor", "below_floor", "tier_unknown",
)


def _next_action(code: str, streams: list[dict[str, Any]]) -> dict[str, Any]:
    """One gap named with its affected streams, its verb and the counters it moves."""
    return {
        "code": code,
        "count": len(streams),
        "verb": _GAP_VERBS[code],
        "moves": list(_GAP_MOVES[code]),
        "streams": streams,
    }


def target_progress(target) -> dict[str, Any]:
    """Counts + honest, separated ratios for a target. Never a claimed coverage percent.

    The percent named ``measured_pct`` counts only streams that are settled
    WITH a real kilogram — a stream is *measured* only when its linked table is
    populated AND a Calculation exists on the target's period (the locked
    L-COVERED definition). A formally excluded stream has no kilogram and is
    reported separately (``excluded_pct``); exclusions can never make a target
    look met.

    ``settled_at_target`` is the subset of measured streams whose actual PCAF
    quality tier is at or above the target's ``min_quality_tier`` floor (a
    lower tier number is better quality). Below-floor streams are NOT dropped:
    they are counted in ``below_floor`` and flagged on the stream.

    An ``absolute`` goal is an EMISSIONS-VALUE target, not a coverage KPI. Its
    unit is restricted to a CO2e mass unit (kgCO2e / tCO2e); the payload reports
    ``metric='absolute_emissions'`` and the measured value in the goal's unit.
    """
    counts = {key: 0 for key in _COUNT_KEYS}
    streams: list[dict[str, Any]] = []
    gap_streams: dict[str, list[dict[str, Any]]] = {}
    measured_kg = Decimal("0")
    measured_kg_at_target = Decimal("0")
    has_kg = False
    floor = target.min_quality_tier

    for source in target_sources(target):
        state = source_state(source, target.reporting_period)
        status = state["status"]
        tier = state.get("tier")
        counts["required"] += 1
        counts[status] = counts.get(status, 0) + 1

        has_real_kg = state["inventory_kg"] is not None
        if floor is None:
            meets_floor = True
        elif tier is None:
            meets_floor = False
        else:
            meets_floor = tier <= floor
        at_target = status == "entered" and meets_floor
        below_floor = status == "entered" and has_real_kg and not meets_floor
        tier_unknown = (
            status == "entered" and floor is not None and tier is None
        )

        if status == "entered":
            counts["measured"] += 1
        if at_target:
            counts["settled_at_target"] += 1
        if below_floor:
            counts["below_floor"] += 1
        if tier_unknown:
            counts["tier_unknown"] += 1

        if has_real_kg:
            value = Decimal(state["inventory_kg"])
            measured_kg += value
            has_kg = True
            if at_target:
                measured_kg_at_target += value

        streams.append({
            "inventory_source_id": source.id,
            "source_name": source.source_name,
            "org_unit_id": source.org_unit_id,
            "org_unit_name": source.org_unit.name if source.org_unit_id else None,
            "scope": source.scope,
            "scope3_category": source.scope3_category,
            "status": status,
            "reason": state["reason"],
            "inventory_kg": state["inventory_kg"],
            "quality_tier": tier,
            "meets_quality_floor": meets_floor,
            "below_floor": below_floor,
            "counts_toward_target": at_target,
            "covered": state.get("covered", False),
        })

        # A stream may be both below-floor and tier-unknown; count it once, in
        # the more specific gap, so the next action names the right fix.
        if status in ("missing", "in_progress", "awaiting_factor"):
            gap_streams.setdefault(status, []).append({
                "inventory_source_id": source.id,
                "source_name": source.source_name,
                "org_unit_id": source.org_unit_id,
                "scope": source.scope,
            })
        elif tier_unknown:
            gap_streams.setdefault("tier_unknown", []).append({
                "inventory_source_id": source.id,
                "source_name": source.source_name,
                "org_unit_id": source.org_unit_id,
                "scope": source.scope,
            })
        elif below_floor:
            gap_streams.setdefault("below_floor", []).append({
                "inventory_source_id": source.id,
                "source_name": source.source_name,
                "org_unit_id": source.org_unit_id,
                "scope": source.scope,
            })

    # Raw settled = measured WITH kg + formally excluded (no kg). It is never
    # the ratio a target is judged met on.
    counts["settled"] = counts["measured"] + counts["excluded"]

    measured_pct = _pct(counts["measured"], counts["required"])
    excluded_pct = _pct(counts["excluded"], counts["required"])
    settled_pct = _pct(counts["settled"], counts["required"])
    settled_at_target_pct = _pct(counts["settled_at_target"], counts["required"])

    findings: list[dict[str, Any]] = []
    if counts["required"] == 0:
        findings.append({
            "code": "no_declared_sources",
            "detail": (
                "No declared sources under this boundary "
                f"(org unit {target.org_unit_id} and its descendants) "
                f"for scope {target.scope}."
            ),
        })

    metric = "absolute_emissions" if target.goal_kind == "absolute" else "coverage_percent"
    goal_concept = "emissions_value" if target.goal_kind == "absolute" else "coverage_kpi"

    # Measured value expressed in the goal's unit, for an absolute emissions goal.
    measured_value = None
    measured_unit = None
    unit_factor = None
    if target.goal_kind == "absolute":
        unit_factor = co2e_unit_factor(target.goal_unit)
        if unit_factor is not None:
            measured_unit = canonical_co2e_unit(target.goal_unit)
            # Missing is not 0: report a value only from real kilograms.
            measured_value = format(measured_kg / unit_factor, "f") if has_kg else None
        else:
            findings.append({
                "code": "goal_unit_not_co2e",
                "detail": (
                    f"Absolute goal unit {target.goal_unit!r} is not a CO2e mass unit "
                    "(kgCO2e / tCO2e); the measured kilograms are not comparable to it."
                ),
            })

    if counts["required"] == 0:
        state = "empty"
    elif target.goal_kind == "percent":
        state = "met" if Decimal(settled_at_target_pct or "0") >= target.goal_value else "short"
    elif unit_factor is None:
        state = "invalid_unit"
    else:
        state = "met" if has_kg and measured_kg >= target.goal_value * unit_factor else "short"

    # Next actions are the live gap set, not a stored plan. An empty universe
    # yields the explicit declare-sources action; otherwise each action names
    # the real gap, its affected streams, its verb and the counters it moves.
    if counts["required"] == 0:
        next_actions = [_next_action("no_declared_sources", [])]
    else:
        next_actions = [
            _next_action(code, gap_streams[code])
            for code in _GAP_ORDER
            if gap_streams.get(code)
        ]

    return {
        "counts": counts,
        "next_actions": next_actions,
        "measured_pct": measured_pct,
        "excluded_pct": excluded_pct,
        "settled_pct": settled_pct,
        "settled_at_target_pct": settled_at_target_pct,
        "measured_kg": format(measured_kg, "f") if has_kg else None,
        "measured_kg_at_target": format(measured_kg_at_target, "f") if has_kg else None,
        "measured_value": measured_value,
        "measured_unit": measured_unit,
        "metric": metric,
        "goal_concept": goal_concept,
        "goal_kind": target.goal_kind,
        "goal_value": format(target.goal_value, "f"),
        "goal_unit": target.goal_unit or "",
        "min_quality_tier": floor,
        "quality_floor_applied": floor is not None,
        "state": state,
        "findings": findings,
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


# ── Task → gap binding (what a task declares it closes) ─────────────────────

# A task DECLARES which completeness gap it addresses, from its real type. The
# gap codes line up with the target-level ``next_actions`` codes so the UI can
# join a task to the live gap it is meant to move.
_TASK_GAP = {
    "fill_gap": "missing",
    "complete_rows": "in_progress",
    "bind_data_product": "missing",
    "secure_factor": "awaiting_factor",
}


def task_gap_code(task) -> str | None:
    """The completeness gap a task declares; None for an unbounded 'other' task."""
    return _TASK_GAP.get(task.task_type)


def _task_gap_changed(task) -> bool:
    """True only when the task's declared completeness gap is really closed.

    This is stricter than ``task_evidence``: binding a table, activating a
    factor or reaching a month is the evidence, but the gap is only *changed*
    when the real stream/row it targets actually moves.
    """
    period = task.target.reporting_period if task.target_id else None
    if task.task_type == "fill_gap":
        if task.stream_source_id is None or period is None:
            return False
        state = source_state(task.stream_source, period)
        return state["status"] in ("entered", "excluded")
    if task.task_type == "complete_rows":
        if task.stream_source_id is not None and period is not None:
            state = source_state(task.stream_source, period)
            return state["status"] in ("entered", "in_progress", "excluded")
        return _rows_reach(task)
    if task.task_type == "bind_data_product":
        table = task.data_table if task.data_table_id else None
        if table is None or getattr(table, "is_archived", False):
            return False
        # Binding a table is the EVIDENCE, not the gap change: it only moves the
        # declared completeness gap when a real stream it names is no longer
        # ``missing``. Without a stream the gap is unverifiable, so it stays open.
        if task.stream_source_id is None or period is None:
            return False
        return source_state(task.stream_source, period)["status"] != "missing"
    if task.task_type == "secure_factor":
        factor = task.factor if task.factor_id else None
        if factor is None or not getattr(factor, "is_active", False):
            return False
        # An active factor is EVIDENCE; the declared gap changes only when the
        # stream that was waiting on it is no longer ``awaiting_factor``.
        if task.stream_source_id is None or period is None:
            return False
        return source_state(task.stream_source, period)["status"] != "awaiting_factor"
    return False


def task_closure(task) -> dict[str, Any]:
    """Honest closure state for a task: evidence met AND the gap actually changed.

    * ``awaiting_evidence`` — the host evidence gate is not met (cannot be done).
    * ``closed`` — evidence met and the declared gap really changed.
    * ``open`` — evidence met but the declared gap did not change: the classic
      "marked done, nothing moved" case that never counts as causal progress.
    """
    evidence = task_evidence(task)
    gap = task_gap_code(task)
    met = bool(evidence["met"])
    if gap is None:
        changed = met
        state = "closed" if met else "awaiting_evidence"
    elif not met:
        changed = False
        state = "awaiting_evidence"
    else:
        changed = _task_gap_changed(task)
        state = "closed" if changed else "open"
    return {
        "state": state,
        "gap": gap,
        "gap_changed": bool(changed),
        "evidence_met": met,
        "moves": list(_GAP_MOVES.get(gap, ())),
        "codes": evidence["codes"],
        "claim": "host_evidence_only",
    }
