"""
Delivery — routes proactive insights to appropriate channels based on severity,
persists them as KgProactiveInsight records, and pushes to WebSocket subscribers.

Channel routing:
  - critical → immediate WebSocket push + notification + banner
  - warning  → WebSocket push + notification panel
  - info     → digest urgency for notifications; still published on the bus
               so list/SSE subscribers see it (PEC-3A)

OUTCOME contract (RULE_23): every persisted insight and bus frame carries
honest ``confidence`` / ``confidence_label`` plus outcome-shaped ``provenance``.
Engine jargon (trigger_id, delivery_channel, SQL, condition JSON) never crosses
the HTTP/SSE surface.
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

# Severity → prior confidence. Conserved downward when measured evidence is thin
# (uncertainty-provenance: never amplify certainty).
_SEVERITY_CONFIDENCE = {
    "critical": 0.95,
    "warning": 0.80,
    "info": 0.60,
}

# Raw context keys that stay internal (never on the public OUTCOME surface).
_INTERNAL_CONTEXT_KEYS = frozenset(
    {
        "trigger_summary",
        "recent_history",
        "system_context",
        "related_alerts",
        "condition",
        "condition_json",
        "sql",
        "data_sources",
        "trigger_id",
        "delivery_channel",
    }
)


def _confidence_label(score: float) -> str:
    """Map 0.0–1.0 → ``high|medium|low|uncertain`` (mirrors Faculty 7 ladder)."""
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    if score >= 0.35:
        return "low"
    return "uncertain"


def _resolve_app_identifier(instance_id: str, insight_data: dict) -> str:
    """Brand-aware app partition for CBAC (list + SSE must agree)."""
    explicit = insight_data.get("app_identifier")
    if explicit:
        return str(explicit)
    try:
        from ai.instance_registry import default_app_for_instance

        return default_app_for_instance(instance_id)
    except Exception:
        return instance_id or "carbon"


def build_outcome_fields(insight_data: dict) -> dict:
    """Derive honest confidence + outcome-shaped provenance from insight_data.

    Returns keys suitable for both persistence (inside ``context_json``) and the
    public API/SSE payload: ``confidence``, ``confidence_label``, ``provenance``,
    and a sanitized ``context`` (no engine jargon).
    """
    severity = (insight_data.get("severity") or "info").lower()
    raw_context = insight_data.get("context") or {}
    if not isinstance(raw_context, dict):
        raw_context = {}

    base = float(_SEVERITY_CONFIDENCE.get(severity, 0.60))
    measured = raw_context.get("measured_data")
    has_measured = bool(measured)
    # No live reading → degrade (honest uncertainty); never invent high confidence.
    if not has_measured:
        base = min(base, 0.55)
    if "confidence" in insight_data and insight_data["confidence"] is not None:
        try:
            base = min(base, float(insight_data["confidence"]))
        except (TypeError, ValueError):
            pass
    confidence = round(max(0.0, min(1.0, base)), 2)
    label = _confidence_label(confidence)

    sources: list[dict] = []
    if has_measured:
        sources.append(
            {
                "label": "Live reading",
                "detail": _summarize_measured(measured),
            }
        )
    related = raw_context.get("related_alerts") or []
    if isinstance(related, list) and related:
        sources.append(
            {
                "label": "Recent alerts",
                "detail": f"{len(related)} related alert(s) in the last day",
            }
        )
    for key in ("notification_count", "episode_count", "proactive_alert_count"):
        if key in raw_context and raw_context[key]:
            sources.append(
                {
                    "label": key.replace("_", " ").title(),
                    "detail": str(raw_context[key]),
                }
            )
    if insight_data.get("insight_type") == "daily_briefing" and not sources:
        sources.append(
            {
                "label": "Daily summary",
                "detail": "Aggregated from recent activity",
            }
        )
    if not sources:
        sources.append(
            {
                "label": "Scheduled check",
                "detail": "No supporting readings attached — treat as provisional",
            }
        )

    provenance = {
        "sources": sources,
        "basis": (
            "Based on live readings and recent alerts"
            if has_measured
            else "Best available — supporting readings were thin"
        ),
    }

    public_context = {
        k: v
        for k, v in raw_context.items()
        if k not in _INTERNAL_CONTEXT_KEYS
        and k
        not in (
            "confidence",
            "confidence_label",
            "provenance",
            "measured_data",  # mirrored as outcome-shaped ``measured``
        )
    }
    if has_measured and "measured" not in public_context:
        public_context["measured"] = measured
    if "related_alert_count" not in public_context and isinstance(related, list):
        public_context["related_alert_count"] = len(related)

    # Persist epistemic fields inside context so the Django JSON column carries
    # them without a schema migration; the read layer lifts them to top-level.
    public_context["confidence"] = confidence
    public_context["confidence_label"] = label
    public_context["provenance"] = provenance

    return {
        "confidence": confidence,
        "confidence_label": label,
        "provenance": provenance,
        "context": public_context,
    }


def _summarize_measured(measured) -> str:
    if isinstance(measured, dict):
        parts = []
        for key in ("value", "metric", "name", "unit", "threshold"):
            if key in measured and measured[key] is not None:
                parts.append(f"{key}={measured[key]}")
        if parts:
            return ", ".join(parts[:6])
        return ", ".join(f"{k}={v}" for k, v in list(measured.items())[:4])
    return str(measured)[:200]


def extract_outcome_fields(context) -> dict:
    """Lift confidence / provenance from a stored context blob (dict or JSON)."""
    ctx = context
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except (json.JSONDecodeError, TypeError):
            ctx = {}
    if not isinstance(ctx, dict):
        ctx = {}

    confidence = ctx.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    label = ctx.get("confidence_label") or (
        _confidence_label(confidence) if confidence is not None else "uncertain"
    )
    provenance = ctx.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {
            "sources": [
                {
                    "label": "Scheduled check",
                    "detail": "No supporting readings attached — treat as provisional",
                }
            ],
            "basis": "Best available — supporting readings were thin",
        }
        if confidence is None:
            confidence = 0.55
            label = _confidence_label(confidence)

    public_context = {
        k: v
        for k, v in ctx.items()
        if k
        not in (
            "confidence",
            "confidence_label",
            "provenance",
            "measured_data",
            *_INTERNAL_CONTEXT_KEYS,
        )
    }
    if "measured" not in public_context and ctx.get("measured_data"):
        public_context["measured"] = ctx["measured_data"]
    return {
        "confidence": confidence if confidence is not None else 0.55,
        "confidence_label": label,
        "provenance": provenance,
        "context": public_context,
    }


async def deliver_insight(
    db,
    instance_id: str,
    insight_data: dict,
    trigger_id: str | None = None,
    group_id: str | None = None,
    executor=None,
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
      - confidence: float (optional; conserved downward, never amplified)
      - app_identifier: str (optional; defaults via brand map)

    Returns the insight ID.
    """
    settings = get_settings()
    severity = insight_data.get("severity", "info")
    channel = _route_channel(severity)
    expiry_hours = settings.KG_PROACTIVE_EXPIRY_HOURS if severity == "info" else None
    outcome = build_outcome_fields(insight_data)
    app_identifier = _resolve_app_identifier(instance_id, insight_data)

    insight = KgProactiveInsight(
        instance_id=instance_id,
        # Instance-level insight (not user-private) → visible to authenticated
        # platform users. The Django store copies this onto the persisted row so
        # the read boundary (scope_ai_queryset) admits it (Phase A3).
        visibility="shared",
        app_identifier=app_identifier,
        trigger_id=trigger_id,
        insight_type=insight_data.get("insight_type", "threshold_alert"),
        severity=severity,
        title=insight_data.get("title", "Proactive Insight"),
        narrative=insight_data.get("narrative", ""),
        context_json=json.dumps(outcome["context"]),
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

    # Deliver based on channel. Delivery is a host effect, so when an executor
    # with the boundary seam is supplied the push/notify work is routed through
    # the fail-closed command boundary (PDP decision row per delivery).
    await _deliver(db, instance_id, insight, insight_data, severity, channel, executor)

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
    executor=None,
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
            executor=executor,
        )
        ids.append(insight_id)
    return ids


async def _deliver(
    db,
    instance_id: str,
    insight: KgProactiveInsight,
    insight_data: dict,
    severity: str,
    channel: str,
    executor=None,
) -> None:
    """Run the delivery host effect for one insight.

    Delivery is a host effect. When ``executor`` exposes the
    ``execute_delivery_via_boundary`` seam, the push/notify work is wrapped in a
    command-boundary ``Command`` so the PDP records a decision row per delivery.
    When an executor is supplied without that seam, delivery fails closed
    (nothing is sent). When no executor is supplied, the legacy direct path is
    preserved.
    """

    async def _deliver_effect(command=None):
        # Always publish the OUTCOME frame to the event bus so list/SSE
        # subscribers see every severity (including digest/info). Channel only
        # gates notification urgency, not bus visibility (PEC-3A).
        await _push_websocket(db, instance_id, insight)
        if severity in ("warning", "critical"):
            await _create_notification(db, instance_id, insight_data, severity)
        return {
            "insight_id": insight.id,
            "channel": channel,
            "severity": severity,
        }

    if executor is None:
        await _deliver_effect()
        return

    boundary_method = getattr(executor, "execute_delivery_via_boundary", None)
    if not callable(boundary_method):
        logger.warning(
            "Delivery boundary seam unavailable for %s — blocking delivery "
            "(fail-closed)",
            instance_id,
        )
        return

    outcome = await boundary_method(
        effect=_deliver_effect,
        instance_id=instance_id,
        host_user_id=getattr(executor, "host_user_id", None),
        delivery_type=channel,
    )

    status = outcome.get("status") if isinstance(outcome, dict) else None
    if status not in ("executed", "confirmed"):
        reason = (
            (outcome.get("error") or outcome.get("reason") or status)
            if isinstance(outcome, dict)
            else status
        )
        logger.warning(
            "Delivery for %s refused/failed by boundary: %s",
            instance_id,
            reason,
        )


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
    outcome = extract_outcome_fields(
        _parse_json_field(insight.context_json, {})
    )
    app_identifier = getattr(insight, "app_identifier", None)
    if not app_identifier:
        app_identifier = _resolve_app_identifier(instance_id, {})
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
            "context": outcome["context"],
            "confidence": outcome["confidence"],
            "confidence_label": outcome["confidence_label"],
            "provenance": outcome["provenance"],
            "disposition": insight.disposition,
            "created_at": (
                insight.created_at.isoformat()
                if insight.created_at
                else utcnow().isoformat()
            ),
            # CBAC scoping fields — instance-level insight, visible to
            # authenticated users (org narrowing at the read boundary).
            "visibility": getattr(insight, "visibility", None) or "shared",
            "org_unit_id": getattr(insight, "org_unit_id", None),
            "host_user_id": getattr(insight, "host_user_id", None),
            "app_identifier": app_identifier,
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
