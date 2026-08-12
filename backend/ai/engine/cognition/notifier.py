"""
Notification system — create, store, and push notifications to connected clients.

Supports two subscriber channels:
  - Widget subscribers (chat WS) — receive notifications only
  - Studio subscribers (admin WS) — receive notifications + cognition events + dashboard updates
"""
import json
import logging
from datetime import datetime

from ai.engine.core.clock import utcnow
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.models import Notification, generate_uuid

logger = logging.getLogger("pulse.cognition.notifier")

# Connected WebSocket clients for notification push
# Key: instance_id, Value: set of WebSocket connections
_subscribers: dict[str, set] = {}

# Studio WebSocket clients — receive richer event stream
_studio_subscribers: dict[str, set] = {}


def subscribe(instance_id: str, websocket):
    """Register a WebSocket client for notification push."""
    if instance_id not in _subscribers:
        _subscribers[instance_id] = set()
    _subscribers[instance_id].add(websocket)
    logger.debug(f"Subscriber added for instance {instance_id}")


def unsubscribe(instance_id: str, websocket):
    """Remove a WebSocket client from notification push."""
    if instance_id in _subscribers:
        _subscribers[instance_id].discard(websocket)
        if not _subscribers[instance_id]:
            del _subscribers[instance_id]


def subscribe_studio(instance_id: str, websocket):
    """Register a Studio WebSocket client for the full event stream."""
    if instance_id not in _studio_subscribers:
        _studio_subscribers[instance_id] = set()
    _studio_subscribers[instance_id].add(websocket)
    logger.debug(f"Studio subscriber added for instance {instance_id}")


def unsubscribe_studio(instance_id: str, websocket):
    """Remove a Studio WebSocket client."""
    if instance_id in _studio_subscribers:
        _studio_subscribers[instance_id].discard(websocket)
        if not _studio_subscribers[instance_id]:
            del _studio_subscribers[instance_id]


async def create_notification(
    db: AsyncSession,
    instance_id: str,
    severity: str,
    title: str,
    body: str | None = None,
) -> Notification:
    """
    Create and store a notification, then push to connected clients.
    Severity: 'info', 'warning', 'critical'
    """
    notification = Notification(
        id=generate_uuid(),
        instance_id=instance_id,
        severity=severity,
        title=title,
        body=body,
        host_user_id=None,       # Instance-wide notification (not user-private)
        visibility="shared",     # Visible to all users of this instance
    )
    db.add(notification)
    await db.commit()

    logger.info(f"[{severity.upper()}] {title}")

    # Push to connected WebSocket clients
    await push_to_subscribers(instance_id, notification)

    return notification


async def push_to_subscribers(instance_id: str, notification: Notification):
    """Broadcast a notification to all connected WebSocket clients for this instance."""
    subscribers = _subscribers.get(instance_id, set())
    if not subscribers:
        return

    payload = {
        "type": "notification",
        "notification": {
            "id": notification.id,
            "severity": notification.severity,
            "title": notification.title,
            "body": notification.body,
            "created_at": notification.created_at.isoformat()
            if notification.created_at
            else utcnow().isoformat(),
        },
    }

    dead = set()
    for ws in subscribers:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)

    # Clean up dead connections
    for ws in dead:
        subscribers.discard(ws)

    # Also push to Studio subscribers
    await _broadcast_studio(instance_id, payload)


async def _broadcast_studio(instance_id: str, payload: dict):
    """Broadcast any event to Studio WebSocket subscribers."""
    subscribers = _studio_subscribers.get(instance_id, set())
    if not subscribers:
        return

    dead = set()
    for ws in subscribers:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)

    for ws in dead:
        subscribers.discard(ws)


async def broadcast_cognition_event(
    instance_id: str,
    event: str,
    task_name: str,
    data: dict | None = None,
):
    """
    Push a cognition event to Studio subscribers.
    Events: task_started, task_completed, task_failed
    """
    payload = {
        "type": "cognition_event",
        "event": event,
        "task": task_name,
        "timestamp": utcnow().isoformat(),
        **(data or {}),
    }
    await _broadcast_studio(instance_id, payload)


# ═══════════════════════════════════════════════════════════════════════════════
# P1.4 — AG-UI run event stream (TASK-BE-01-4)
# ═══════════════════════════════════════════════════════════════════════════════

RUN_EVENT_TYPES: frozenset[str] = frozenset({
    "run.started",
    "run.step.started",
    "run.step.completed",
    "run.step.failed",
    "run.step.skipped",
    "run.paused",
    "run.resumed",
    "run.completed",
    "run.failed",
    "run.cancelled",
    "tool.started",
    "tool.completed",
    "tool.failed",
})


async def broadcast_run_event(instance_id: str, event_type: str, payload: dict):
    """Push an AG-UI vocabulary run lifecycle event to Studio subscribers.

    Args:
        instance_id: Pulse instance to scope the broadcast
        event_type: One of RUN_EVENT_TYPES (e.g. "run.started", "run.paused")
        payload: Event-specific data dict (run_id, step_index, error, etc.)
    """
    if event_type not in RUN_EVENT_TYPES:
        logger.warning(f"Unknown run event type: {event_type}")
        return
    msg = {
        "type": "run_event",
        "event": event_type,
        "timestamp": utcnow().isoformat(),
        "payload": payload,
    }
    await _broadcast_studio(instance_id, msg)
