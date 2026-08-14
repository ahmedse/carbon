"""
Trigger Evaluator — reads host DB data, evaluates trigger conditions,
and determines which triggers should fire.

Supports three categories:
  - threshold: value crosses a boundary
  - trend: rolling stat deviates from baseline
  - correlation: two+ signals move together
"""
import json
import logging
import statistics
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow
from typing import Optional

from ai.engine.core.config import get_settings
from ai.engine.knowledge_graph.models import KgProactiveTrigger

logger = logging.getLogger("pulse.proactive.trigger_evaluator")


class TriggerResult:
    """Result of evaluating a single trigger."""

    __slots__ = ("trigger_id", "fired", "severity", "trigger_name", "category",
                 "measured_value", "threshold_value", "detail", "data_snapshot")

    def __init__(
        self,
        trigger_id: str,
        fired: bool,
        severity: str,
        trigger_name: str,
        category: str,
        measured_value=None,
        threshold_value=None,
        detail: str = "",
        data_snapshot: dict | None = None,
    ):
        self.trigger_id = trigger_id
        self.fired = fired
        self.severity = severity
        self.trigger_name = trigger_name
        self.category = category
        self.measured_value = measured_value
        self.threshold_value = threshold_value
        self.detail = detail
        self.data_snapshot = data_snapshot or {}


async def evaluate_triggers(
    db,
    instance_id: str,
    host_db_url: str,
) -> list[TriggerResult]:
    """
    Evaluate all enabled triggers for an instance against live host data.
    Returns list of TriggerResults (both fired and non-fired for audit).
    """
    settings = get_settings()
    if not settings.KG_PROACTIVE_ENABLED:
        return []

    # Fetch enabled triggers
    triggers = await db.select(
        KgProactiveTrigger,
        ("instance_id", instance_id),
        ("enabled", True),
    )

    if not triggers:
        return []

    now = utcnow()
    results: list[TriggerResult] = []

    for trigger in triggers:
        # Check cooldown
        if trigger.last_fired_at:
            cooldown_until = trigger.last_fired_at + timedelta(seconds=trigger.cooldown_seconds)
            if now < cooldown_until:
                continue

        try:
            condition = json.loads(trigger.condition_json)
            data_sources = json.loads(trigger.data_sources_json)

            if trigger.category == "threshold":
                tr = await _evaluate_threshold(trigger, condition, data_sources, host_db_url)
            elif trigger.category == "trend":
                tr = await _evaluate_trend(trigger, condition, data_sources, host_db_url)
            elif trigger.category == "correlation":
                tr = await _evaluate_correlation(trigger, condition, data_sources, host_db_url)
            else:
                continue

            results.append(tr)
        except Exception as e:
            logger.warning(f"Error evaluating trigger '{trigger.name}': {e}")
            results.append(TriggerResult(
                trigger_id=trigger.id,
                fired=False,
                severity=trigger.severity,
                trigger_name=trigger.name,
                category=trigger.category,
                detail=f"Evaluation error: {e}",
            ))

    return results


# ── Threshold evaluation ──────────────────────────────────────────────────────

async def _evaluate_threshold(
    trigger: KgProactiveTrigger,
    condition: dict,
    data_sources: list,
    host_db_url: str,
) -> TriggerResult:
    """
    Evaluate a threshold trigger.

    Condition format:
    {
      "column": "winding_temperature",
      "table": "transformer_readings",
      "operator": ">",        // >, <, >=, <=, ==, !=
      "value": 105.0,
      "where": "asset_id = 'T-3'",  // optional filter
      "aggregation": "latest"   // latest | avg | max | min | count
    }
    """
    table = condition.get("table", "")
    column = condition.get("column", "")
    operator = condition.get("operator", ">")
    threshold = condition.get("value")
    where_clause = condition.get("where", "")
    aggregation = condition.get("aggregation", "latest")

    if not table or not column or threshold is None:
        return TriggerResult(
            trigger_id=trigger.id, fired=False, severity=trigger.severity,
            trigger_name=trigger.name, category="threshold",
            detail="Incomplete condition: missing table, column, or value",
        )

    # Validate operator
    valid_ops = {">", "<", ">=", "<=", "==", "!="}
    if operator not in valid_ops:
        return TriggerResult(
            trigger_id=trigger.id, fired=False, severity=trigger.severity,
            trigger_name=trigger.name, category="threshold",
            detail=f"Invalid operator: {operator}",
        )

    measured = await _query_aggregation(host_db_url, table, column, aggregation, where_clause)
    if measured is None:
        return TriggerResult(
            trigger_id=trigger.id, fired=False, severity=trigger.severity,
            trigger_name=trigger.name, category="threshold",
            detail="No data returned from host query",
        )

    fired = _compare(measured, operator, threshold)

    return TriggerResult(
        trigger_id=trigger.id,
        fired=fired,
        severity=trigger.severity,
        trigger_name=trigger.name,
        category="threshold",
        measured_value=measured,
        threshold_value=threshold,
        detail=f"{column} {aggregation}={measured} {operator} {threshold} → {'FIRED' if fired else 'ok'}",
        data_snapshot={"table": table, "column": column, "measured": measured, "threshold": threshold},
    )


# ── Trend evaluation ─────────────────────────────────────────────────────────

async def _evaluate_trend(
    trigger: KgProactiveTrigger,
    condition: dict,
    data_sources: list,
    host_db_url: str,
) -> TriggerResult:
    """
    Evaluate a trend trigger — detects deviation from rolling baseline.

    Condition format:
    {
      "column": "efficiency",
      "table": "unit_metrics",
      "time_column": "recorded_at",
      "baseline_days": 30,
      "recent_days": 3,
      "deviation_pct": 5.0,      // fire if recent avg deviates > this %
      "direction": "decrease"    // decrease | increase | any
    }
    """
    table = condition.get("table", "")
    column = condition.get("column", "")
    time_column = condition.get("time_column", "created_at")
    baseline_days = condition.get("baseline_days", 30)
    recent_days = condition.get("recent_days", 3)
    deviation_pct = condition.get("deviation_pct", 5.0)
    direction = condition.get("direction", "any")

    if not table or not column:
        return TriggerResult(
            trigger_id=trigger.id, fired=False, severity=trigger.severity,
            trigger_name=trigger.name, category="trend",
            detail="Incomplete condition: missing table or column",
        )

    baseline_avg = await _query_time_avg(
        host_db_url, table, column, time_column, baseline_days
    )
    recent_avg = await _query_time_avg(
        host_db_url, table, column, time_column, recent_days
    )

    if baseline_avg is None or recent_avg is None or baseline_avg == 0:
        return TriggerResult(
            trigger_id=trigger.id, fired=False, severity=trigger.severity,
            trigger_name=trigger.name, category="trend",
            detail="Insufficient data for trend analysis",
        )

    pct_change = ((recent_avg - baseline_avg) / abs(baseline_avg)) * 100
    fired = False

    if direction == "decrease" and pct_change < -deviation_pct:
        fired = True
    elif direction == "increase" and pct_change > deviation_pct:
        fired = True
    elif direction == "any" and abs(pct_change) > deviation_pct:
        fired = True

    return TriggerResult(
        trigger_id=trigger.id,
        fired=fired,
        severity=trigger.severity,
        trigger_name=trigger.name,
        category="trend",
        measured_value=round(pct_change, 2),
        threshold_value=deviation_pct,
        detail=f"{column} trend: baseline_avg={baseline_avg:.2f}, recent_avg={recent_avg:.2f}, "
               f"change={pct_change:+.2f}% (threshold ±{deviation_pct}%) → {'FIRED' if fired else 'ok'}",
        data_snapshot={
            "table": table, "column": column,
            "baseline_avg": baseline_avg, "recent_avg": recent_avg,
            "pct_change": round(pct_change, 2),
        },
    )


# ── Correlation evaluation ────────────────────────────────────────────────────

async def _evaluate_correlation(
    trigger: KgProactiveTrigger,
    condition: dict,
    data_sources: list,
    host_db_url: str,
) -> TriggerResult:
    """
    Evaluate a correlation trigger — two+ signals moving together.

    Condition format:
    {
      "signals": [
        {"table": "load_readings", "column": "load_mw", "direction": "increase"},
        {"table": "gen_readings", "column": "generation_mw", "direction": "decrease"}
      ],
      "recent_hours": 6,
      "time_column": "recorded_at",
      "min_signals": 2    // how many must agree to fire
    }
    """
    signals = condition.get("signals", [])
    recent_hours = condition.get("recent_hours", 6)
    time_column = condition.get("time_column", "recorded_at")
    min_signals = condition.get("min_signals", len(signals))

    if len(signals) < 2:
        return TriggerResult(
            trigger_id=trigger.id, fired=False, severity=trigger.severity,
            trigger_name=trigger.name, category="correlation",
            detail="Correlation requires at least 2 signals",
        )

    matching = 0
    signal_details = []

    for sig in signals:
        table = sig.get("table", "")
        column = sig.get("column", "")
        expected_dir = sig.get("direction", "any")

        if not table or not column:
            continue

        # Compare recent vs slightly-older window
        recent_avg = await _query_time_avg(host_db_url, table, column, time_column, 0, recent_hours)
        older_avg = await _query_time_avg(host_db_url, table, column, time_column, recent_hours, recent_hours)

        if recent_avg is None or older_avg is None or older_avg == 0:
            signal_details.append(f"{table}.{column}: insufficient data")
            continue

        actual_change = ((recent_avg - older_avg) / abs(older_avg)) * 100
        actual_dir = "increase" if actual_change > 1 else ("decrease" if actual_change < -1 else "flat")

        match = (expected_dir == "any") or (expected_dir == actual_dir)
        if match:
            matching += 1

        signal_details.append(
            f"{table}.{column}: {actual_dir} ({actual_change:+.1f}%) "
            f"{'✓' if match else '✗'}"
        )

    fired = matching >= min_signals

    return TriggerResult(
        trigger_id=trigger.id,
        fired=fired,
        severity=trigger.severity,
        trigger_name=trigger.name,
        category="correlation",
        measured_value=matching,
        threshold_value=min_signals,
        detail=f"Correlation: {matching}/{len(signals)} signals matched "
               f"(need {min_signals}). {'; '.join(signal_details)}",
        data_snapshot={"matching": matching, "signals": signal_details},
    )


# ── Host DB query helpers ─────────────────────────────────────────────────────

async def _query_aggregation(
    host_db_url: str,
    table: str,
    column: str,
    aggregation: str,
    where_clause: str = "",
) -> Optional[float]:
    """Query host DB for an aggregated value. Runs in thread pool (sync psycopg2)."""
    import asyncio
    import psycopg2

    agg_map = {
        "latest": f"(SELECT {_qi(column)} FROM {_qi(table)} %WHERE% ORDER BY 1 DESC LIMIT 1)",
        "avg": f"SELECT AVG({_qi(column)}) FROM {_qi(table)} %WHERE%",
        "max": f"SELECT MAX({_qi(column)}) FROM {_qi(table)} %WHERE%",
        "min": f"SELECT MIN({_qi(column)}) FROM {_qi(table)} %WHERE%",
        "count": f"SELECT COUNT(*) FROM {_qi(table)} %WHERE%",
    }

    template = agg_map.get(aggregation)
    if not template:
        return None

    where_sql = f"WHERE {where_clause}" if where_clause else ""
    # For "latest", the subquery needs a different structure
    if aggregation == "latest":
        sql = f"SELECT {_qi(column)} FROM {_qi(table)} {where_sql} ORDER BY 1 DESC LIMIT 1"
    else:
        sql = template.replace("%WHERE%", where_sql)

    def _run():
        try:
            conn = psycopg2.connect(host_db_url)
            conn.set_session(readonly=True, autocommit=True)
            cur = conn.cursor()
            cur.execute(f"SET statement_timeout = '5000'")
            cur.execute(sql)
            row = cur.fetchone()
            cur.close()
            conn.close()
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            logger.debug(f"Host query failed: {e}")
            return None

    return await asyncio.get_event_loop().run_in_executor(None, _run)


async def _query_time_avg(
    host_db_url: str,
    table: str,
    column: str,
    time_column: str,
    days_ago_start: int,
    days_window: int | None = None,
) -> Optional[float]:
    """
    Query host DB for average value in a time window.
    If days_window is None, uses days_ago_start as "last N days from now".
    If days_window is set, uses days_ago_start..days_ago_start+days_window window ago.
    """
    import asyncio
    import psycopg2

    if days_window is None:
        # Last N days from now
        sql = (
            f"SELECT AVG({_qi(column)}) FROM {_qi(table)} "
            f"WHERE {_qi(time_column)} >= NOW() - INTERVAL '{days_ago_start} days'"
        )
    else:
        # Window: from (days_ago_start + days_window) to days_ago_start ago
        if days_ago_start == 0:
            sql = (
                f"SELECT AVG({_qi(column)}) FROM {_qi(table)} "
                f"WHERE {_qi(time_column)} >= NOW() - INTERVAL '{days_window} hours'"
            )
        else:
            sql = (
                f"SELECT AVG({_qi(column)}) FROM {_qi(table)} "
                f"WHERE {_qi(time_column)} >= NOW() - INTERVAL '{days_ago_start + days_window} hours' "
                f"AND {_qi(time_column)} < NOW() - INTERVAL '{days_ago_start} hours'"
            )

    def _run():
        try:
            conn = psycopg2.connect(host_db_url)
            conn.set_session(readonly=True, autocommit=True)
            cur = conn.cursor()
            cur.execute(f"SET statement_timeout = '10000'")
            cur.execute(sql)
            row = cur.fetchone()
            cur.close()
            conn.close()
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            logger.debug(f"Host time query failed: {e}")
            return None

    return await asyncio.get_event_loop().run_in_executor(None, _run)


# ── SQL safety ────────────────────────────────────────────────────────────────

def _qi(identifier: str) -> str:
    """Quote a SQL identifier to prevent injection. Only allows alphanumeric + underscore."""
    clean = "".join(c for c in identifier if c.isalnum() or c == "_")
    return f'"{clean}"'


def _compare(measured: float, operator: str, threshold: float) -> bool:
    """Safe comparison of measured value against threshold."""
    ops = {
        ">": measured > threshold,
        "<": measured < threshold,
        ">=": measured >= threshold,
        "<=": measured <= threshold,
        "==": abs(measured - threshold) < 1e-9,
        "!=": abs(measured - threshold) >= 1e-9,
    }
    return ops.get(operator, False)
