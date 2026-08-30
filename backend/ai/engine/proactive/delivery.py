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
from datetime import timedelta

from ai.engine.core.clock import utcnow

from ai.engine.core.config import get_settings
from ai.engine.core.event_bus import build_event_frame, events_channel, publish
from ai.engine.cognition.notifier import create_notification, push_to_subscribers
from ai.engine.core.models import Notification, generate_uuid
from ai.engine.knowledge_graph.models import KgProactiveInsight

logger = logging.getLogger("pulse.proactive.delivery")


async def deliver_insight(
    db,
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
        # Instance-level insight (not user-private) → visible to authenticated
        # carbon users. The Django store copies this onto the persisted row so
        # the read boundary (scope_ai_queryset) admits it (Phase A3).
        visibility="shared",
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
    db,
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


async def expire_stale_insights(db, instance_id: str) -> int:
    """
    Mark expired info-level insights as 'expired'.
    Called periodically by the cognition loop.
    Returns count of expired insights.
    """
    now = utcnow()
    expired = await db.select(
        KgProactiveInsight,
        ("instance_id", instance_id),
        ("disposition", "pending"),
        ("expires_at__isnull", False),
        ("expires_at__lte", now),
    )

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

def _parse_json_field(value, default):
    """Parse a JSON-text column, tolerating already-decoded / None values."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def _build_insight_frame(instance_id: str, insight: KgProactiveInsight) -> dict:
    """Build the OUTCOME-shaped ``insight.new`` bus frame (RULE_23).

    Carries only OUTCOME fields plus the CBAC scoping fields the SSE endpoint
    needs to filter — never engine internals (trigger_id, delivery_channel,
    channel names, instance_id, etc.).
    """
    return build_event_frame(
        "insight.new",
        instance_id,
        {
            "id": insight.id,
            "title": insight.title,
            "narrative": insight.narrative,
            "severity": insight.severity,
            "insight_type": insight.insight_type,
            "recommended_actions": _parse_json_field(
                insight.recommended_actions_json, []
            ),
            "context": _parse_json_field(insight.context_json, {}),
            "disposition": insight.disposition,
            "created_at": (
                insight.created_at.isoformat()
                if insight.created_at
                else utcnow().isoformat()
            ),
            # CBAC scoping fields — instance-level insight, visible to
            # authenticated carbon users (org narrowing at the read boundary).
            "visibility": getattr(insight, "visibility", None) or "shared",
            "org_unit_id": getattr(insight, "org_unit_id", None),
            "host_user_id": getattr(insight, "host_user_id", None),
            "app_identifier": getattr(insight, "app_identifier", None) or "carbon",
        },
    )


async def _push_websocket(db, instance_id: str, insight: KgProactiveInsight):
    """Push insight to connected WebSocket clients and the Redis event bus.

    The Redis publish (Phase A3) happens first so cross-process SSE
    subscribers receive the insight even when there are no in-process WS
    subscribers; the in-process fan-out below is preserved unchanged.
    """
    from ai.engine.cognition.notifier import _subscribers

    await publish(events_channel(), _build_insight_frame(instance_id, insight))

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
    db,
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
