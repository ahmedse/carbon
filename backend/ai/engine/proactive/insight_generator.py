"""
Insight Generator — produces scheduled proactive insights beyond trigger-based alerts.

Insight types:
  - daily_briefing: 24h summary of notable events + look-ahead
  - anomaly_narrative: wraps anomaly detection flags in contextual explanations
  - forecast_deviation: mid-day divergence between actuals and forecast
  - performance_drift: slow-moving degradation over weeks
  - optimization_opportunity: patterns suggesting operational improvements
"""
import json
import logging
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow

from openai import AsyncOpenAI
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import Insight, Notification, SystemSnapshot, MemoryEpisodic
from ai.engine.knowledge_graph.models import KgProactiveInsight

logger = logging.getLogger("pulse.proactive.insight_generator")


async def generate_daily_briefing(
    db: AsyncSession,
    instance_id: str,
) -> dict | None:
    """
    Generate a daily briefing insight — summary of last 24h + look-ahead.
    Returns the insight dict or None if no notable events.
    """
    cutoff = utcnow() - timedelta(hours=24)

    # Gather: recent notifications, insights, snapshots
    notifs = await _recent_notifications(db, instance_id, cutoff)
    snapshots = await _recent_snapshots(db, instance_id, cutoff)
    episodes = await _recent_episodes(db, instance_id, cutoff)
    proactive_insights = await _recent_proactive_insights(db, instance_id, cutoff)

    if not notifs and not snapshots and not episodes and not proactive_insights:
        return None

    # Build context for LLM
    context_parts = []
    if notifs:
        context_parts.append(
            "Recent notifications:\n" +
            "\n".join(f"- [{n['severity']}] {n['title']}: {n.get('body', '')}" for n in notifs[:10])
        )
    if snapshots:
        for s in snapshots[:2]:
            if s.get("summary"):
                context_parts.append(f"System snapshot: {s['summary']}")
    if episodes:
        context_parts.append(
            "Recent events:\n" +
            "\n".join(f"- {e['event_type']}: {e['summary']}" for e in episodes[:10])
        )
    if proactive_insights:
        context_parts.append(
            "Proactive alerts in last 24h:\n" +
            "\n".join(f"- [{pi['severity']}] {pi['title']}" for pi in proactive_insights[:10])
        )

    context_text = "\n\n".join(context_parts)

    prompt = (
        "Generate a concise daily operations briefing for the engineering team.\n\n"
        f"Data from the last 24 hours:\n{context_text}\n\n"
        "Structure your briefing as:\n"
        "1. Key Events: What notable things happened\n"
        "2. Current Status: Any ongoing concerns\n"
        "3. Look-Ahead: What to watch for based on trends\n\n"
        "Be specific, use numbers, keep it under 300 words."
    )

    try:
        from ai.engine.llm.router import route_chat
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"daily-briefing-{instance_id}",
            messages=[
                {"role": "system", "content": "You are an operational intelligence analyst writing a shift briefing."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        narrative = (result.get("content") or "").strip()
    except Exception as e:
        logger.warning(f"Daily briefing LLM call failed: {e}")
        narrative = _statistical_briefing(notifs, episodes, proactive_insights)

    return {
        "insight_type": "daily_briefing",
        "severity": "info",
        "title": f"Daily Briefing — {utcnow().strftime('%Y-%m-%d')}",
        "narrative": narrative,
        "context": {
            "notification_count": len(notifs),
            "episode_count": len(episodes),
            "proactive_alert_count": len(proactive_insights),
        },
    }


async def detect_performance_drift(
    db: AsyncSession,
    instance_id: str,
    host_db_url: str,
    metrics_config: list[dict] | None = None,
) -> list[dict]:
    """
    Detect slow-moving performance degradation.

    metrics_config is a list of:
    {
        "table": "unit_metrics",
        "column": "heat_rate",
        "name": "Unit 2 Heat Rate",
        "lookback_days": 30,
        "threshold_pct": 2.0,
        "direction": "increase"  # increase means degradation
    }

    Returns list of insight dicts for detected drifts.
    """
    if not metrics_config:
        return []

    from ai.engine.proactive.trigger_evaluator import _query_time_avg

    insights = []
    for metric in metrics_config:
        table = metric.get("table", "")
        column = metric.get("column", "")
        name = metric.get("name", f"{table}.{column}")
        lookback = metric.get("lookback_days", 30)
        threshold_pct = metric.get("threshold_pct", 2.0)
        direction = metric.get("direction", "increase")

        baseline = await _query_time_avg(host_db_url, table, column, "created_at", lookback)
        recent = await _query_time_avg(host_db_url, table, column, "created_at", 7)

        if baseline is None or recent is None or baseline == 0:
            continue

        pct_change = ((recent - baseline) / abs(baseline)) * 100
        drifting = (
            (direction == "increase" and pct_change > threshold_pct) or
            (direction == "decrease" and pct_change < -threshold_pct)
        )

        if drifting:
            insights.append({
                "insight_type": "performance_drift",
                "severity": "warning",
                "title": f"Performance Drift: {name}",
                "narrative": (
                    f"{name} has changed {pct_change:+.1f}% over the past {lookback} days "
                    f"(baseline: {baseline:.2f}, recent 7-day avg: {recent:.2f}). "
                    f"Threshold: {threshold_pct}%."
                ),
                "context": {
                    "metric": name,
                    "baseline": baseline,
                    "recent": recent,
                    "pct_change": round(pct_change, 2),
                    "lookback_days": lookback,
                },
            })

    return insights


async def detect_forecast_deviations(
    db: AsyncSession,
    instance_id: str,
    host_db_url: str,
    deviation_config: dict | None = None,
) -> list[dict]:
    """
    Detect when actuals diverge significantly from forecasts.

    deviation_config:
    {
        "forecast_table": "demand_forecasts",
        "actual_table": "demand_actuals",
        "value_column": "value_mw",
        "time_column": "timestamp",
        "join_column": "timestamp",
        "threshold_pct": 8.0
    }
    """
    if not deviation_config:
        return []

    import asyncio
    import psycopg2

    from ai.engine.proactive.trigger_evaluator import _qi

    fc_table = deviation_config.get("forecast_table", "")
    act_table = deviation_config.get("actual_table", "")
    val_col = deviation_config.get("value_column", "value")
    time_col = deviation_config.get("time_column", "timestamp")
    threshold = deviation_config.get("threshold_pct", 8.0)

    if not fc_table or not act_table:
        return []

    sql = (
        f"SELECT "
        f"  AVG(ABS(a.{_qi(val_col)} - f.{_qi(val_col)})) / NULLIF(AVG(f.{_qi(val_col)}), 0) * 100 as deviation_pct, "
        f"  AVG(a.{_qi(val_col)}) as avg_actual, "
        f"  AVG(f.{_qi(val_col)}) as avg_forecast "
        f"FROM {_qi(act_table)} a "
        f"JOIN {_qi(fc_table)} f ON a.{_qi(time_col)} = f.{_qi(time_col)} "
        f"WHERE a.{_qi(time_col)} >= NOW() - INTERVAL '12 hours'"
    )

    def _run():
        try:
            conn = psycopg2.connect(host_db_url)
            conn.set_session(readonly=True, autocommit=True)
            cur = conn.cursor()
            cur.execute("SET statement_timeout = '10000'")
            cur.execute(sql)
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and row[0] is not None:
                return {"deviation_pct": float(row[0]), "avg_actual": float(row[1] or 0), "avg_forecast": float(row[2] or 0)}
            return None
        except Exception as e:
            logger.debug(f"Forecast deviation query failed: {e}")
            return None

    result = await asyncio.get_event_loop().run_in_executor(None, _run)
    if not result or result["deviation_pct"] < threshold:
        return []

    dev = result["deviation_pct"]
    return [{
        "insight_type": "forecast_deviation",
        "severity": "warning" if dev > threshold * 2 else "info",
        "title": f"Forecast Deviation: {dev:.1f}% off",
        "narrative": (
            f"Actuals are tracking {dev:.1f}% away from forecast over the last 12 hours. "
            f"Average actual: {result['avg_actual']:.1f}, forecast: {result['avg_forecast']:.1f}. "
            f"Threshold: {threshold}%."
        ),
        "context": result,
    }]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _recent_notifications(db: AsyncSession, instance_id: str, since: datetime) -> list[dict]:
    stmt = (
        select(Notification)
        .where(Notification.instance_id == instance_id, Notification.created_at >= since)
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return [
        {"title": n.title, "severity": n.severity, "body": n.body,
         "created_at": n.created_at.isoformat() if n.created_at else None}
        for n in result.scalars().all()
    ]


async def _recent_snapshots(db: AsyncSession, instance_id: str, since: datetime) -> list[dict]:
    stmt = (
        select(SystemSnapshot)
        .where(SystemSnapshot.instance_id == instance_id, SystemSnapshot.taken_at >= since)
        .order_by(SystemSnapshot.taken_at.desc())
        .limit(3)
    )
    result = await db.execute(stmt)
    return [
        {"summary": s.summary, "taken_at": s.taken_at.isoformat() if s.taken_at else None}
        for s in result.scalars().all()
    ]


async def _recent_episodes(db: AsyncSession, instance_id: str, since: datetime) -> list[dict]:
    stmt = (
        select(MemoryEpisodic)
        .where(
            MemoryEpisodic.instance_id == instance_id,
            MemoryEpisodic.occurred_at >= since,
            MemoryEpisodic.archived == False,  # noqa: E712
        )
        .order_by(MemoryEpisodic.occurred_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return [
        {"event_type": e.event_type, "summary": e.summary,
         "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None}
        for e in result.scalars().all()
    ]


async def _recent_proactive_insights(db: AsyncSession, instance_id: str, since: datetime) -> list[dict]:
    stmt = (
        select(KgProactiveInsight)
        .where(
            KgProactiveInsight.instance_id == instance_id,
            KgProactiveInsight.created_at >= since,
        )
        .order_by(KgProactiveInsight.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return [
        {"title": i.title, "severity": i.severity, "insight_type": i.insight_type,
         "created_at": i.created_at.isoformat() if i.created_at else None}
        for i in result.scalars().all()
    ]


def _statistical_briefing(notifs: list, episodes: list, proactive: list) -> str:
    """Fallback briefing when LLM is unavailable."""
    parts = []
    if notifs:
        critical = sum(1 for n in notifs if n.get("severity") == "critical")
        warning = sum(1 for n in notifs if n.get("severity") == "warning")
        parts.append(f"Notifications: {len(notifs)} total ({critical} critical, {warning} warning)")
    if episodes:
        parts.append(f"Events: {len(episodes)} recorded in last 24h")
    if proactive:
        parts.append(f"Proactive alerts: {len(proactive)} generated")
    return "Daily Briefing (statistical summary):\n" + "\n".join(f"- {p}" for p in parts) if parts else "No notable events in the last 24 hours."
