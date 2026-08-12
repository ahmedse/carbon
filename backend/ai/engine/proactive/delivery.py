"""
Delivery — routes proactive insights to appropriate channels based on severity,
persists them as KgProactiveInsight records, and pushes to WebSocket subscribers.

Channel routing:
  - critical → immediate WebSocket push + notification + banner
  - warning  → WebSocket push + notification panel
  - info     → queued for digest / next shift briefing
"""
import json
import logging
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow

from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.cognition.notifier import create_notification, push_to_subscribers
from ai.engine.core.models import Notification, generate_uuid
from ai.engine.knowledge_graph.models import KgProactiveInsight

logger = logging.getLogger("pulse.proactive.delivery")


async def deliver_insight(
    db: AsyncSession,
    instance_id: str,
    insight_data: dict,
    trigger_id: str | None = None,
    group_id: str | None = None,
) -> str:
    """
    Persist a proactive insight and route it to the appropriate delivery channel.

    insight_data keys:
      - insight_type: str
      - severity: str
      - title: str
      - narrative: str
      - context: dict (optional)
      - recommended_actions: list[str] (optional)

    Returns the insight ID.
    """
    settings = get_settings()
    severity = insight_data.get("severity", "info")
    channel = _route_channel(severity)
    expiry_hours = settings.KG_PROACTIVE_EXPIRY_HOURS if severity == "info" else None

    insight = KgProactiveInsight(
        instance_id=instance_id,
        trigger_id=trigger_id,
        insight_type=insight_data.get("insight_type", "threshold_alert"),
        severity=severity,
        title=insight_data.get("title", "Proactive Insight"),
        narrative=insight_data.get("narrative", ""),
        context_json=json.dumps(insight_data.get("context", {})),
        recommended_actions_json=json.dumps(insight_data.get("recommended_actions", [])),
        disposition="pending",
        group_id=group_id,
        delivery_channel=channel,
        expires_at=(
            utcnow() + timedelta(hours=expiry_hours) if expiry_hours else None
        ),
    )
    db.add(insight)
    await db.commit()

    insight_id = insight.id

    # Deliver based on channel
    if channel in ("websocket", "banner"):
        await _push_websocket(db, instance_id, insight)
    if severity in ("warning", "critical"):
        await _create_notification(db, instance_id, insight_data, severity)

    logger.info(
        f"Delivered [{severity}] insight '{insight_data.get('title', '')}' "
        f"via {channel} for {instance_id}"
    )
    return insight_id


async def deliver_batch(
    db: AsyncSession,
    instance_id: str,
    insights: list[dict],
    group_id: str | None = None,
) -> list[str]:
    """Deliver multiple insights, respecting the per-evaluation cap."""
    settings = get_settings()
    cap = settings.KG_PROACTIVE_MAX_INSIGHTS_PER_EVAL
    ids = []
    for insight_data in insights[:cap]:
        insight_id = await deliver_insight(
            db, instance_id, insight_data,
            trigger_id=insight_data.get("trigger_id"),
            group_id=group_id,
        )
        ids.append(insight_id)
    return ids


async def expire_stale_insights(db: AsyncSession, instance_id: str) -> int:
    """
    Mark expired info-level insights as 'expired'.
    Called periodically by the cognition loop.
    Returns count of expired insights.
    """
    from sqlalchemy import select, update

    now = utcnow()
    stmt = (
        select(KgProactiveInsight)
        .where(
            KgProactiveInsight.instance_id == instance_id,
            KgProactiveInsight.disposition == "pending",
            KgProactiveInsight.expires_at != None,  # noqa: E711
            KgProactiveInsight.expires_at <= now,
        )
    )
    result = await db.execute(stmt)
    expired = result.scalars().all()

    for insight in expired:
        insight.disposition = "expired"

    if expired:
        await db.commit()
        logger.debug(f"Expired {len(expired)} stale insights for {instance_id}")

    return len(expired)


# ── Channel routing ───────────────────────────────────────────────────────────

def _route_channel(severity: str) -> str:
    """Map severity to delivery channel."""
    return {
        "critical": "banner",
        "warning": "websocket",
        "info": "digest",
    }.get(severity, "digest")


# ── Page relevance mapping ────────────────────────────────────────────────────

# Maps insight_type keywords to host-app page path fragments.
# When the widget is on a matching page, these insights are highlighted.
_PAGE_RELEVANCE: dict[str, list[str]] = {
    "threshold_alert":    ["/engines", "/models", "/predictions"],
    "trend_alert":        ["/engines", "/models", "/dashboard"],
    "health":             ["/engines", "/models"],
    "freshness":          ["/datasets", "/data"],
    "stale":              ["/datasets", "/data"],
    "error":              ["/jobs", "/engines"],
    "failed":             ["/jobs", "/engines"],
    "drift":              ["/models", "/engines", "/predictions"],
    "performance":        ["/models", "/engines"],
    "anomaly":            ["/dashboard", "/engines"],
    "daily_briefing":     [],  # relevant to all pages
    "pattern":            ["/dashboard"],
    "recommendation":     ["/dashboard"],
    "optimization":       ["/engines", "/models"],
}


def _get_relevant_pages(insight_type: str) -> list[str]:
    """Resolve relevant page paths for an insight based on its type."""
    it = (insight_type or "").lower()
    for keyword, pages in _PAGE_RELEVANCE.items():
        if keyword in it:
            return pages
    return []


# ── Push mechanisms ──────────────────────────────────────────────────────────

async def _push_websocket(db: AsyncSession, instance_id: str, insight: KgProactiveInsight):
    """Push insight to connected WebSocket clients."""
    from ai.engine.cognition.notifier import _subscribers

    subscribers = _subscribers.get(instance_id, set())
    if not subscribers:
        return

    payload = {
        "type": "proactive_insight",
        "insight": {
            "id": insight.id,
            "insight_type": insight.insight_type,
            "severity": insight.severity,
            "title": insight.title,
            "narrative": insight.narrative,
            "recommended_actions": json.loads(insight.recommended_actions_json),
            "relevant_pages": _get_relevant_pages(insight.insight_type),
            "created_at": insight.created_at.isoformat() if insight.created_at else utcnow().isoformat(),
        },
    }

    dead = set()
    for ws in subscribers:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)

    for ws in dead:
        subscribers.discard(ws)

    if not dead or len(subscribers) > 0:
        insight.disposition = "delivered"
        insight.delivered_at = utcnow()
        await db.commit()


async def _create_notification(
    db: AsyncSession,
    instance_id: str,
    insight_data: dict,
    severity: str,
):
    """Create a persistent notification for warning/critical insights."""
    await create_notification(
        db,
        instance_id=instance_id,
        severity=severity,
        title=f"🔔 {insight_data.get('title', 'Proactive Alert')}",
        body=insight_data.get("narrative", "")[:500],
    )
