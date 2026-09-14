"""Human Task Inbox REST + SSE API (P3-09).

Mounted at ``{api_prefix}/ai/inbox/`` (see ``config/urls.py``) with routes
declared in ``ai.task_inbox_urls``:

    GET    /tasks/                  list pending tasks (operator/auditor)
    GET    /tasks/{id}/             retrieve one task (operator/auditor)
    POST   /tasks/{id}/approve/     designated authority approves (mints grant)
    POST   /tasks/{id}/decline/     designated authority declines (no grant)
    GET    /stream/                 SSE stream of pending-task updates

Permission model (CBAC): reads (list/retrieve/stream) require ``ai:operator``
or ``ai:auditor`` via :func:`accounts.capabilities.has_any_capability`; the
approve/decline actions are the *designated-authority* gate — the service
enforces ``has_capability(user, task.required_authority)`` per task and the
view maps the fail-closed refusals to HTTP (403/404/409).  Group/role names
are never hardcoded here.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import (
    AI_AUDITOR,
    AI_OPERATOR,
    has_any_capability,
)
from ai.models.human_task import STATUS_PENDING, HumanTask
from ai.task_inbox import (
    TaskExpired,
    TaskInbox,
    TaskNotFound,
    TaskNotPending,
    UnauthorizedApprover,
)

logger = logging.getLogger("carbon.ai.task_inbox_api")

# SSE heartbeat/poll cadence (seconds).
_STREAM_POLL_SECONDS = 2.0


# ── Capability permission classes ──────────────────────────────────────────

class InboxReadPermission(BasePermission):
    """Read access: operator or auditor (superusers pass via the ``*`` cap)."""

    message = "Reading the task inbox requires ai:operator or ai:auditor."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return has_any_capability(user, {AI_OPERATOR.key, AI_AUDITOR.key})


# ── Serializers ────────────────────────────────────────────────────────────

class HumanTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = HumanTask
        fields = [
            "id",
            "run_id",
            "step_id",
            "consequence",
            "objects_revisions_json",
            "before_json",
            "after_json",
            "evidence_json",
            "evidence_digest",
            "reversibility",
            "required_authority",
            "expires_at",
            "alternatives_json",
            "status",
            "grant_id",
            "decided_by",
            "decided_at",
            "decline_reason",
            "capability",
            "process_version",
            "capability_version",
            "object_id",
            "object_type",
            "process_instance",
            "created_at",
            "updated_at",
        ]


class DeclineSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


def _serialize_task(task: HumanTask) -> dict:
    return HumanTaskSerializer(task).data


# ── ViewSet ────────────────────────────────────────────────────────────────

class TaskInboxViewSet(viewsets.GenericViewSet):
    """Durable human-task inbox — read-gated reads, designated-authority writes."""

    permission_classes = [IsAuthenticated]
    serializer_class = HumanTaskSerializer

    action_permission_map = {
        "list": [InboxReadPermission],
        "retrieve": [InboxReadPermission],
        # approve/decline are gated per-task by the service via
        # has_capability(user, task.required_authority) — the designated
        # authority is dynamic and enforced fail-closed there.
    }

    def get_permissions(self):
        perms = [IsAuthenticated()]
        for perm_cls in self.action_permission_map.get(self.action, []):
            perms.append(perm_cls())
        return perms

    def _scoped_queryset(self, request):
        from accounts.ai_scoping import scope_ai_queryset

        return scope_ai_queryset(HumanTask.objects.all(), request.user)

    def get_object(self):
        qs = self._scoped_queryset(self.request)
        return get_object_or_404(qs, pk=self.kwargs.get("pk"))

    # ── reads ──────────────────────────────────────────────────────────

    def list(self, request):
        qs = self._scoped_queryset(request).filter(
            status=STATUS_PENDING, expires_at__gt=timezone.now()
        )
        qs = qs.order_by("created_at")
        return Response(HumanTaskSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        task = self.get_object()
        return Response(HumanTaskSerializer(task).data)

    # ── decide actions (RULE_21: explicit human action) ────────────────

    def approve(self, request, pk=None):
        task = self.get_object()
        try:
            task = TaskInbox().approve(request.user, task.id)
        except TaskNotFound:
            return self._not_found()
        except UnauthorizedApprover as exc:
            return self._refused(403, "unauthorized", str(exc))
        except TaskExpired as exc:
            return self._refused(409, "expired", str(exc))
        except TaskNotPending as exc:
            return self._refused(409, "not_pending", str(exc))
        return Response(HumanTaskSerializer(task).data)

    def decline(self, request, pk=None):
        task = self.get_object()
        serializer = DeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        try:
            task = TaskInbox().decline(request.user, task.id, reason=reason)
        except TaskNotFound:
            return self._not_found()
        except UnauthorizedApprover as exc:
            return self._refused(403, "unauthorized", str(exc))
        except TaskExpired as exc:
            return self._refused(409, "expired", str(exc))
        except TaskNotPending as exc:
            return self._refused(409, "not_pending", str(exc))
        return Response(HumanTaskSerializer(task).data)

    @staticmethod
    def _not_found():
        return Response(
            {"error": "not_found", "detail": "Task not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    @staticmethod
    def _refused(code: int, error: str, detail: str) -> Response:
        return Response(
            {"error": error, "detail": detail},
            status=code,
        )


# ── SSE stream ─────────────────────────────────────────────────────────────

class _IgnoreAcceptNegotiation(BaseContentNegotiation):
    """Always select the first renderer, ignoring the client's ``Accept``.

    SSE views return a raw ``StreamingHttpResponse`` (not a DRF ``Response``),
    so the negotiated renderer is never used.  This only stops DRF from raising
    ``NotAcceptable`` (406) on the standard ``Accept: text/event-stream``.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


def _sse_frame(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def iter_pending_frames(user) -> Iterator[str]:
    """Yield the current pending-task snapshot as ``task.pending`` SSE frames."""
    inbox = TaskInbox()
    for task in inbox.list_pending(user):
        yield _sse_frame("task.pending", _serialize_task(task))


def _inbox_stream_frames(user, poll_seconds: float = _STREAM_POLL_SECONDS):
    """Synchronous generator: snapshot, then poll for newly-seen pending tasks.

    Emits an initial snapshot of every currently-pending task, then re-polls the
    DB every ``poll_seconds`` and emits only tasks not already emitted (id
    de-duplication), plus a ``: ping`` heartbeat so proxies stay open and the
    loop never spins on a down connection.
    """
    seen: set[str] = set()

    def emit_new() -> Iterator[str]:
        for task in TaskInbox().list_pending(user):
            if task.id in seen:
                continue
            seen.add(task.id)
            yield _sse_frame("task.pending", _serialize_task(task))

    for frame in emit_new():
        yield frame
    while True:
        time.sleep(poll_seconds)
        for frame in emit_new():
            yield frame
        yield ": ping\n\n"


class TaskInboxStreamView(APIView):
    """GET /stream/ — Server-Sent Events stream of pending-task updates."""

    permission_classes = [IsAuthenticated, InboxReadPermission]
    content_negotiation_class = _IgnoreAcceptNegotiation

    def get(self, request):
        response = StreamingHttpResponse(
            _inbox_stream_frames(request.user),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
