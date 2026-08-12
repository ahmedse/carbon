"""
Context Assembler — when a trigger fires, assembles rich context around it
by executing context queries, pulling recent history, and synthesizing a narrative.

This is what makes proactive insights different from raw alarms — narrative context.
"""
import json
import logging
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow

from openai import AsyncOpenAI
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import Notification, SystemSnapshot
from ai.engine.knowledge_graph.models import KgProactiveTrigger

logger = logging.getLogger("pulse.proactive.context_assembler")


async def assemble_context(
    db: AsyncSession,
    trigger: dict,
    trigger_result,
    instance_id: str,
    host_db_url: str,
) -> dict:
    """
    Assemble full context around a fired trigger.

    Returns:
    {
        "trigger_summary": str,
        "measured_data": dict,
        "recent_history": list[dict],
        "related_alerts": list[dict],
        "system_context": dict,
        "narrative": str,
        "recommended_actions": list[str],
    }
    """
    context = {
        "trigger_summary": trigger_result.detail,
        "measured_data": trigger_result.data_snapshot,
        "recent_history": [],
        "related_alerts": [],
        "system_context": {},
        "narrative": "",
        "recommended_actions": trigger.get("recommended_actions", []),
    }

    # 1) Execute the trigger's attached context queries (if any)
    context_queries = trigger.get("context_queries", [])
    if context_queries:
        query_results = await _execute_context_queries(context_queries, host_db_url)
        context["recent_history"] = query_results

    # 2) Pull related notifications from the last 24h
    context["related_alerts"] = await _get_related_alerts(db, instance_id)

    # 3) Get the latest system snapshot for ambient conditions
    context["system_context"] = await _get_system_context(db, instance_id)

    # 4) Synthesize a narrative using LLM
    context["narrative"] = await _synthesize_narrative(
        trigger, trigger_result, context, instance_id
    )

    return context


async def _execute_context_queries(
    queries: list[dict],
    host_db_url: str,
) -> list[dict]:
    """Execute attached context queries against the host DB."""
    import asyncio
    import psycopg2

    results = []
    for query_spec in queries[:5]:  # cap at 5 context queries
        sql = query_spec.get("sql", "")
        label = query_spec.get("label", query_spec.get("intent", "context query"))

        if not sql or not sql.strip().upper().startswith("SELECT"):
            continue

        def _run(q=sql):
            try:
                conn = psycopg2.connect(host_db_url)
                conn.set_session(readonly=True, autocommit=True)
                cur = conn.cursor()
                cur.execute("SET statement_timeout = '5000'")
                cur.execute(q)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchmany(50)
                cur.close()
                conn.close()
                return {
                    "label": label,
                    "columns": columns,
                    "rows": [list(r) for r in rows],
                    "row_count": len(rows),
                }
            except Exception as e:
                logger.debug(f"Context query failed: {e}")
                return {"label": label, "error": str(e)}

        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        results.append(result)

    return results


async def _get_related_alerts(db: AsyncSession, instance_id: str) -> list[dict]:
    """Pull recent notifications (last 24h) that might be related."""
    cutoff = utcnow() - timedelta(hours=24)
    stmt = (
        select(Notification)
        .where(
            Notification.instance_id == instance_id,
            Notification.created_at >= cutoff,
        )
        .order_by(Notification.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    return [
        {
            "title": n.title,
            "severity": n.severity,
            "body": n.body,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in result.scalars().all()
    ]


async def _get_system_context(db: AsyncSession, instance_id: str) -> dict:
    """Get the latest system snapshot for ambient context."""
    stmt = (
        select(SystemSnapshot)
        .where(SystemSnapshot.instance_id == instance_id)
        .order_by(SystemSnapshot.taken_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return {}

    try:
        data = json.loads(snapshot.snapshot_data or "{}")
    except json.JSONDecodeError:
        data = {}

    return {
        "snapshot_summary": snapshot.summary or "",
        "snapshot_data": data,
        "taken_at": snapshot.taken_at.isoformat() if snapshot.taken_at else None,
    }


_NARRATIVE_PROMPT = """You are an operational intelligence analyst for {system_name}.
A proactive monitoring trigger has fired. Your job is to write a brief, contextual narrative
that helps an engineer understand what's happening, why it matters, and what to do.

Trigger: {trigger_name} ({category}, severity: {severity})
Description: {trigger_description}
Measurement: {detail}

{context_section}

Write a 2-4 paragraph narrative that:
1. States what was detected, with specific values and timing
2. Provides relevant context (ambient conditions, related events, recent history)
3. Compares to any past occurrences if data is available
4. Suggests concrete next steps

Be direct, specific, and operational. Use actual numbers. No filler."""


async def _synthesize_narrative(
    trigger: dict,
    trigger_result,
    context: dict,
    instance_id: str,
) -> str:
    """Use LLM via route_chat to synthesize a contextual narrative around the trigger event."""
    # Build context section
    context_parts = []

    if context.get("recent_history"):
        for item in context["recent_history"]:
            if "error" in item:
                continue
            label = item.get("label", "data")
            rows = item.get("rows", [])
            cols = item.get("columns", [])
            if rows:
                context_parts.append(
                    f"Context query '{label}': {len(rows)} rows. "
                    f"Columns: {', '.join(cols)}. "
                    f"First row: {rows[0]}"
                )

    if context.get("related_alerts"):
        alerts_text = "; ".join(
            f"[{a['severity']}] {a['title']}"
            for a in context["related_alerts"][:5]
        )
        context_parts.append(f"Recent alerts: {alerts_text}")

    if context.get("system_context", {}).get("snapshot_summary"):
        context_parts.append(f"System state: {context['system_context']['snapshot_summary']}")

    context_section = "\n".join(context_parts) if context_parts else "No additional context available."

    prompt = _NARRATIVE_PROMPT.format(
        system_name="the host system",
        trigger_name=trigger.get("name", "Unknown"),
        category=trigger.get("category", ""),
        severity=trigger.get("severity", "info"),
        trigger_description=trigger.get("description", ""),
        detail=trigger_result.detail,
        context_section=context_section,
    )

    try:
        from ai.engine.llm.router import route_chat
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"trigger-narrative-{trigger.get('id', 'unknown')}",
            messages=[
                {"role": "system", "content": "You are a concise operational intelligence analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return (result.get("content") or "").strip()
    except Exception as e:
        logger.warning(f"Narrative synthesis failed: {e}")
        # Fallback: return the raw detail
        return (
            f"Trigger '{trigger.get('name', '')}' fired: {trigger_result.detail}. "
            f"Severity: {trigger.get('severity', 'info')}."
        )
