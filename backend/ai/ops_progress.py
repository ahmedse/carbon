"""
AI Operations Progress read-layer API + publisher (Pulse 0.2 Wave D1).

GET   /carbon-api/ai/operations/stream/  — SSE stream of scoped ``op.progress``
                                            frames for the caller's own ops.

Long operations (DQ runs, imports, reports) publish progress frames onto the
existing A2 event bus (``ai.engine.core.event_bus``) as they run. This module
provides the OUTCOME-shaped frame builder + a thin sync publisher for the
synchronous Django services that run those ops, plus the A3-style SSE bridge
that streams the frames back to the initiating user.

Scoping is simpler than proactive insights: operation progress is **private** —
only the user who started the operation sees its frames (a superuser / global
admin sees all, for support). Frames are OUTCOME-shaped (RULE_23): the
``message`` is a narrated human sentence ("Reading your file…"), never engine
jargon (job_type internals, pulse task ids, channel names, handler names).

This is a Django read layer — importing ``accounts`` scoping helpers here is
the established, allowed pattern (RULE_20 / I1). The bus itself is transient
fire-and-forget transport (RULE_6): nothing is persisted here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ai.engine.core.event_bus import build_event_frame, events_channel, publish, subscribe

logger = logging.getLogger("pulse.ops.progress")

# SSE heartbeat interval (seconds). Mirrors ``ai/insights_api.py`` so an idle
# stream neither spins on an empty queue nor gets closed by a proxy.
_HEARTBEAT_SECONDS = 15.0

# The event type on the A2 bus (mirrors ``insight.new``).
EVENT_TYPE = "op.progress"

# Supported operation categories (human-facing, RULE_23 — no engine jargon).
OP_TYPES = frozenset({"dq_run", "import", "report"})

# Terminal states the frontend treats as "this op is over".
TERMINAL_STATUSES = frozenset({"done", "failed", "canceled"})

# How often the presence-driven ticker asks registered apps to advance their
# in-flight operations while a client is streaming (seconds). Mirrors the
# old 5s frontend poll, but now it lives server-side and only runs while
# someone is actually watching the stream.
_REFRESH_SECONDS = 5.0

# Registered operation refreshers. An app with asynchronous long operations
# (e.g. ``dq`` polling Pulse for in-flight jobs) registers a ``callable(user)``
# here at app startup; the SSE stream invokes them on a cadence so progress
# frames are produced *and* streamed from a single, presence-driven loop.
# Keep this generic — the stream layer must never import app-specific runners.
_REFRESHERS: "list" = []

_STOP = object()


def register_progress_refresher(fn) -> None:
    """Register a ``callable(user)`` that advances in-flight ops for a user.

    Called from an app's ``AppConfig.ready()``. The function must be cheap,
    best-effort, and never raise — a misbehaving refresher must not break the
    stream. It is invoked while a user is connected to the operations stream.
    """
    if fn not in _REFRESHERS:
        _REFRESHERS.append(fn)


def _refresh_for_user(user) -> None:
    """Run every registered refresher for ``user`` (best-effort, never raises)."""
    for fn in _REFRESHERS:
        try:
            fn(user)
        except Exception as exc:  # noqa: BLE001 — refreshers are best-effort
            logger.debug("op.progress refresher %r failed: %s", fn, exc)


class _IgnoreAcceptNegotiation(BaseContentNegotiation):
    """Always select the first renderer, ignoring the client's ``Accept``.

    SSE views return a raw ``StreamingHttpResponse`` (not a DRF ``Response``),
    so the negotiated renderer is never used. This only stops DRF from raising
    ``NotAcceptable`` (406) on the standard SSE header
    ``Accept: text/event-stream`` that no default renderer matches.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


def build_op_progress_payload(
    op_type: str,
    op_id,
    status: str,
    message: str,
    *,
    percent: int | None = None,
    host_user_id=None,
    org_unit_id=None,
) -> dict:
    """Build the OUTCOME-shaped ``op.progress`` payload (RULE_23).

    ``op_id`` is the stable identifier of the operation (e.g. the ``DQJob`` or
    ``ImportJob`` pk). ``status`` is one of ``queued | running | done | failed
    | canceled``. ``message`` is a narrated human sentence. ``percent`` is an
    optional 0–100 integer.
    """
    return {
        "app_identifier": "carbon",
        "op_type": op_type,
        "op_id": str(op_id),
        "status": status,
        "message": message,
        "percent": int(percent) if percent is not None else None,
        "host_user_id": str(host_user_id) if host_user_id is not None else None,
        "org_unit_id": org_unit_id,
        "visibility": "private",
        "created_at": timezone.now().isoformat(),
    }


async def publish_op_progress(
    op_type: str,
    op_id,
    status: str,
    message: str,
    *,
    percent: int | None = None,
    host_user_id=None,
    org_unit_id=None,
) -> None:
    """Publish an ``op.progress`` frame to the A2 bus (async). Never raises."""
    payload = build_op_progress_payload(
        op_type,
        op_id,
        status,
        message,
        percent=percent,
        host_user_id=host_user_id,
        org_unit_id=org_unit_id,
    )
    frame = build_event_frame(EVENT_TYPE, _instance_id(), payload)
    await publish(events_channel(), frame)


def publish_op_progress_sync(
    op_type: str,
    op_id,
    status: str,
    message: str,
    *,
    percent: int | None = None,
    host_user_id=None,
    org_unit_id=None,
) -> None:
    """Fire-and-forget publisher for synchronous Django callers.

    The DQ/import/report services are synchronous, so awaiting the async bus
    would either block the request or raise inside a running loop. A daemon
    thread runs the async publish in its own event loop, so the caller returns
    immediately and the frame still lands on the bus. Progress publishing is
    best-effort (RULE_6): a down Redis is logged and dropped, never raised.
    """

    def _run() -> None:
        try:
            asyncio.run(
                publish_op_progress(
                    op_type,
                    op_id,
                    status,
                    message,
                    percent=percent,
                    host_user_id=host_user_id,
                    org_unit_id=org_unit_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 — fire-and-forget must not raise
            logger.debug("op.progress publish dropped (%s #%s): %s", op_type, op_id, exc)

    threading.Thread(target=_run, name="op-progress-publish", daemon=True).start()


def _instance_id() -> str:
    """Return this instance's id for the frame envelope (lazy, no engine import)."""
    from ai.engine.core.config import get_settings

    return get_settings().PULSE_INSTANCE_ID


def _op_frame_visible(user, frame: dict) -> bool:
    """Pure CBAC filter over an OUTCOME-shaped ``op.progress`` payload.

    Operation progress is private to the initiating user; superuser / global
    admin sees all frames (support). No org-subtree narrowing — a user's own
    operation progress is not org-scoped.
    """
    from accounts.rbac_utils import user_is_global_admin

    if frame.get("app_identifier") != "carbon":
        return False
    if user.is_superuser or user_is_global_admin(user):
        return True
    return str(frame.get("host_user_id")) == str(user.id)


def _op_stream_frames(user):
    """Synchronous generator bridging the async bus subscribe to an SSE stream.

    Mirrors ``ai/insights_api.py::_insight_stream_frames``: a background thread
    runs ``asyncio.run`` over the async ``subscribe`` generator and pushes the
    caller's matching ``op.progress`` frames onto a thread-safe queue; this
    (sync) generator drains the queue, emitting ``data: {json}`` frames and a
    ``: ping`` heartbeat while idle.

    Additionally, a second daemon thread runs the registered refreshers on a
    cadence (presence-driven progress): while this user is streaming, their
    in-flight operations are advanced server-side, producing the very frames
    this generator emits. The refresher thread is stopped cleanly on close;
    the bus-subscribe thread is daemon (same as ``insights_api.py``) and relies
    on process teardown.
    """
    q: "queue.Queue[object]" = queue.Queue()
    stop_refresh = threading.Event()

    async def _consume() -> None:
        async for frame in subscribe(events_channel()):
            if frame.get("event_type") != EVENT_TYPE:
                continue
            payload = frame.get("payload") or {}
            if _op_frame_visible(user, payload):
                q.put(payload)

    def _run() -> None:
        try:
            asyncio.run(_consume())
        finally:
            q.put(_STOP)

    def _refresh_loop() -> None:
        while not stop_refresh.wait(_REFRESH_SECONDS):
            _refresh_for_user(user)

    thread = threading.Thread(target=_run, name="ai-ops-progress-sse", daemon=True)
    thread.start()
    refresh_thread = threading.Thread(
        target=_refresh_loop, name="ai-ops-progress-refresh", daemon=True
    )
    refresh_thread.start()

    try:
        while True:
            try:
                item = q.get(timeout=_HEARTBEAT_SECONDS)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            if item is _STOP:
                break
            yield f"data: {json.dumps(item)}\n\n"
    finally:
        stop_refresh.set()
        q.put(_STOP)


class OperationsStreamView(APIView):
    """GET /stream/ — SSE stream of the caller's own ``op.progress`` frames."""

    permission_classes = [IsAuthenticated]
    content_negotiation_class = _IgnoreAcceptNegotiation

    def get(self, request):
        response = StreamingHttpResponse(
            _op_stream_frames(request.user),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
