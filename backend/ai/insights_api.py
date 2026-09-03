"""
AI Proactive Insights read-layer API (Pulse 0.2 Phase A3).

GET   /carbon-api/ai/insights/stream/         — SSE stream of scoped ``insight.new`` frames
GET   /carbon-api/ai/insights/                — paginated list of scoped insights
POST  /carbon-api/ai/insights/{pk}/disposition/ — user-driven read/acted_on/dismissed

Proactive insights are instance-level (never tied to a single host user), so
they persist as ``visibility="shared"`` and are narrowed by the caller's org
subtree at this read boundary (CBAC, via ``scope_ai_queryset`` / the pure
``_frame_visible`` filter). Frames are OUTCOME-shaped (RULE_23): no engine
jargon (trigger_id, condition_json, delivery_channel, channel names, etc.)
ever crosses the HTTP surface.

This is a Django read layer — importing ``accounts`` scoping helpers here is
the established, allowed pattern (RULE_20 / I1).
"""

import asyncio
import json
import queue
import threading

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.engine.core.event_bus import events_channel, subscribe
from ai.pii_guard import PIIGuard

# SSE heartbeat interval (seconds). Keeps proxies/nginx from closing the
# stream while idle, and bounds the time the generator blocks on an empty
# queue so a dead Redis connection never spins.
_HEARTBEAT_SECONDS = 15.0

# Valid user-driven dispositions (RULE_21: user action only, POST endpoint).
DISPOSITIONS = frozenset({"read", "acted_on", "dismissed"})

_STOP = object()


class _IgnoreAcceptNegotiation(BaseContentNegotiation):
    """Always select the first renderer, ignoring the client's ``Accept``.

    SSE views return a raw ``StreamingHttpResponse`` (not a DRF ``Response``),
    so the negotiated renderer is never used. This only stops DRF from raising
    ``NotAcceptable`` (406) when a browser sends the standard SSE header
    ``Accept: text/event-stream`` that no default renderer matches.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


def _parse_json(value, default):
    """Parse a JSON-text column, tolerating already-decoded / None values."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def _serialize_insight(insight) -> dict:
    """Serialize a ``KgProactiveInsight`` row to the OUTCOME shape (RULE_23)."""
    return {
        "id": str(insight.id),
        "title": insight.title,
        "narrative": PIIGuard.redact(insight.narrative or ""),
        "severity": insight.severity,
        "insight_type": insight.insight_type,
        "recommended_actions": _parse_json(insight.recommended_actions_json, []),
        "context": _parse_json(insight.context_json, {}),
        "disposition": insight.disposition,
        "created_at": insight.created_at.isoformat(),
    }


def _frame_visible(user, frame: dict) -> bool:
    """Pure CBAC filter over an OUTCOME-shaped bus frame (dict, not a row).

    Mirrors ``accounts.ai_scoping.scope_ai_queryset`` semantics: superuser /
    global admin sees all; otherwise ``visibility`` in (global, shared) or
    ``private`` + ``host_user_id`` == caller id; then org-subtree narrowing
    (rows with ``org_unit_id`` in the allowed set, or ``None`` when the user
    holds no org roles).
    """
    from accounts.constants import ADMIN_ROLES
    from accounts.rbac_utils import get_allowed_org_unit_ids, user_is_global_admin

    if frame.get("app_identifier") != "carbon":
        return False
    if user.is_superuser or user_is_global_admin(user):
        return True

    visibility = frame.get("visibility")
    host_user_id = frame.get("host_user_id")
    uid = str(user.id)
    visible = visibility in ("global", "shared") or (
        visibility == "private" and host_user_id == uid
    )
    if not visible:
        return False

    org_unit_id = frame.get("org_unit_id")
    allowed = get_allowed_org_unit_ids(user, ADMIN_ROLES)
    if allowed:
        return org_unit_id is None or org_unit_id in allowed
    return org_unit_id is None


def _insight_stream_frames(user):
    """Synchronous generator bridging the async bus subscribe to an SSE stream.

    A background thread runs ``asyncio.run`` over the async ``subscribe``
    generator and pushes matching ``insight.new`` frames onto a thread-safe
    queue. This (sync) generator drains the queue, emitting ``data: {json}``
    frames for frames the caller may see and a ``: ping`` comment heartbeat
    while idle (so a dead Redis connection never spins and proxies stay open).
    """
    q: "queue.Queue[object]" = queue.Queue()

    async def _consume() -> None:
        async for frame in subscribe(events_channel()):
            if frame.get("event_type") != "insight.new":
                continue
            payload = frame.get("payload") or {}
            if _frame_visible(user, payload):
                payload = dict(payload)
                payload["narrative"] = PIIGuard.redact(payload.get("narrative") or "")
                q.put(payload)

    def _run() -> None:
        try:
            asyncio.run(_consume())
        finally:
            q.put(_STOP)

    thread = threading.Thread(target=_run, name="ai-insights-sse", daemon=True)
    thread.start()

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
        q.put(_STOP)


class InsightsStreamView(APIView):
    """GET /stream/ — Server-Sent Events stream of scoped ``insight.new`` frames."""

    permission_classes = [IsAuthenticated]
    # This view returns a raw ``StreamingHttpResponse`` (not a DRF ``Response``),
    # so DRF's renderer is never used. Default content negotiation would 406 on
    # the standard ``Accept: text/event-stream`` header a browser sends for SSE
    # (no registered renderer matches that media type). Ignore the client's
    # Accept header so the stream is served regardless.
    content_negotiation_class = _IgnoreAcceptNegotiation

    def get(self, request):
        response = StreamingHttpResponse(
            _insight_stream_frames(request.user),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class InsightsListView(APIView):
    """GET / — paginated list of CBAC-scoped proactive insights (OUTCOME shape)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounts.ai_scoping import scope_ai_queryset
        from ai.models import KgProactiveInsight

        qs = scope_ai_queryset(KgProactiveInsight.objects.all(), request.user)
        qs = qs.order_by("-created_at")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginator.max_page_size = 100
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            data = [_serialize_insight(row) for row in page]
            return paginator.get_paginated_response(data)
        return Response([_serialize_insight(row) for row in qs])


class InsightDispositionView(APIView):
    """POST /{pk}/disposition/ — user-driven disposition (RULE_21: user action only)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from accounts.ai_scoping import scope_ai_queryset
        from ai.models import KgProactiveInsight

        disposition = request.data.get("disposition")
        if disposition not in DISPOSITIONS:
            return Response(
                {
                    "detail": (
                        f"Invalid disposition: {disposition!r}. "
                        f"Expected one of {sorted(DISPOSITIONS)}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = request.data.get("reason")

        qs = scope_ai_queryset(KgProactiveInsight.objects.all(), request.user)
        try:
            insight = qs.get(id=pk)
        except KgProactiveInsight.DoesNotExist:
            return Response(
                {"detail": "Insight not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        update_fields = ["disposition"]
        insight.disposition = disposition
        if reason and disposition == "dismissed":
            insight.dismissed_reason = reason
            update_fields.append("dismissed_reason")
        insight.save(update_fields=update_fields)

        return Response(_serialize_insight(insight))
