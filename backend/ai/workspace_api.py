"""
AI Workspace REST API — conversation CRUD + messaging.

POST   /carbon-api/ai/workspace/conversations/
GET    /carbon-api/ai/workspace/conversations/
GET    /carbon-api/ai/workspace/conversations/{id}/
POST   /carbon-api/ai/workspace/conversations/{id}/messages/
"""

import json
import sys, os

# Ensure repo root is on path so that `backend.ai.*` imports resolve.
# Django's manage.py only adds backend/; pytest adds the repo root for tests.
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.intelligence import (
    CarbonIntelligence,
    NotAssistantMessageError,
    NotUserMessageError,
)
from ai.usage_service import QuotaExceededError
from ai.serializers import (
    AgentActionStreamSerializer,
    ArtifactCreateSerializer,
    ArtifactSerializer,
    ArtifactUpdateSerializer,
    CheckpointActionSerializer,
    CheckpointCreateSerializer,
    ConversationListSerializer,
    ConversationUpdateSerializer,
    CreateConversationSerializer,
    EditMessageSerializer,
    MessageFeedbackSerializer,
    MessageListSerializer,
    RetryMessageSerializer,
    SendMessageSerializer,
    ToolExecutionActionSerializer,
    UserProfileSerializer,
)
from accounts.capabilities import has_capability

import logging

logger = logging.getLogger("carbon.ai.workspace_api")


class WorkspaceConversationViewSet(viewsets.GenericViewSet):
    """AI Workspace conversation API.

    All endpoints require authentication and are scoped to the
    requesting user's own conversations.
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._intelligence: CarbonIntelligence | None = None

    @property
    def intelligence(self) -> CarbonIntelligence:
        if self._intelligence is None:
            self._intelligence = CarbonIntelligence()
        return self._intelligence

    def list(self, request):
        """List conversations for the current user.

        Query params: status, limit (default 50), q, is_archived, is_pinned,
        conversation_type, cursor.
        """
        serializer = ConversationListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        conversations = self.intelligence.list_conversations(
            user=request.user,
            status=serializer.validated_data.get("status"),
            limit=serializer.validated_data.get("limit", 50),
            query=serializer.validated_data.get("q"),
            is_archived=serializer.validated_data.get("is_archived"),
            is_pinned=serializer.validated_data.get("is_pinned"),
            conversation_type=serializer.validated_data.get("conversation_type"),
        )
        return Response(conversations)

    def create(self, request):
        """Create a new conversation."""
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation = self.intelligence.create_conversation(
            user=request.user,
            conversation_type=serializer.validated_data["conversation_type"],
            title=serializer.validated_data.get("title", ""),
            app_identifier=serializer.validated_data.get("app_identifier"),
            task_payload=serializer.validated_data.get("task_payload"),
            workspace_context=serializer.validated_data.get("workspace_context"),
        )
        return Response(conversation, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        """Get a single conversation with all its messages."""
        try:
            conversation = self.intelligence.get_conversation(
                user=request.user,
                conversation_id=pk,
            )
            return Response(conversation)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    def partial_update(self, request, pk=None):
        """Partially update a conversation (title/is_pinned/is_archived/visibility)."""
        serializer = ConversationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            conversation = self.intelligence.update_conversation(
                user=request.user,
                conversation_id=pk,
                **serializer.validated_data,
            )
            return Response(conversation)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    def destroy(self, request, pk=None):
        """Hard-delete a conversation (owner-only)."""
        try:
            result = self.intelligence.delete_conversation(
                user=request.user,
                conversation_id=pk,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get", "post"], url_path="messages", url_name="send-message")
    def send_message(self, request, pk=None):
        """GET: paginate messages. POST: send a message and get AI response.

        Both share ``conversations/{id}/messages/`` (list vs. create). DRF cannot
        register two ``@action`` methods on the same ``url_path`` without one
        shadowing the other, so the two operations are dispatched by HTTP method
        here.
        """
        if request.method == "GET":
            return self.list_messages(request, pk)

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = self.intelligence.send_message(
                user=request.user,
                conversation_id=pk,
                content=serializer.validated_data["content"],
                model=serializer.validated_data.get("model") or None,
            )
            return Response(result)
        except QuotaExceededError as e:
            return Response(
                {"error": str(e), "error_code": "quota", "quota": e.quota},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    def list_messages(self, request, pk=None):
        """List a conversation's messages with cursor pagination."""
        serializer = MessageListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        try:
            result = self.intelligence.list_messages(
                user=request.user,
                conversation_id=pk,
                limit=serializer.validated_data.get("limit", 50),
                before=serializer.validated_data.get("before"),
                after=serializer.validated_data.get("after"),
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback", url_name="message-feedback")
    def message_feedback(self, request, pk=None, message_id=None):
        """Record user feedback (accept/reject/correct/ignore) on an AI message."""
        serializer = MessageFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            message = self.intelligence.record_feedback(
                user=request.user,
                conversation_id=pk,
                message_id=message_id,
                outcome=serializer.validated_data["outcome"],
                correction_text=serializer.validated_data.get("correction_text", ""),
            )
            return Response(message)
        except NotAssistantMessageError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="messages/stream", url_name="send-message-stream")
    def send_message_stream(self, request, pk=None):
        """Stream a chat answer as Server-Sent Events.

        Frames are ``data: <json>\n\n``.  Terminal frames are
        ``{"type": "done", "conversation": {...}}`` on success or
        ``{"type": "error", "error": message}`` on failure.
        """
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def event_stream():
            try:
                for frame in self.intelligence.send_message_stream(
                    user=request.user,
                    conversation_id=pk,
                    content=serializer.validated_data["content"],
                    model=serializer.validated_data.get("model") or None,
                ):
                    yield f"data: {json.dumps(frame)}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    @action(detail=True, methods=["post"], url_path="actions/stream", url_name="run-action-stream")
    def run_action_stream(self, request, pk=None):
        """Stream an agent/tool action run as Server-Sent Events (Sprint W1-A).

        Body: ``{action_type: "tool"|"agent", tool?, agent?, args, verbosity}``.

        Frames are ``data: <json>\n\n``:
          {"type": "turn_start"|"tool_start"|"tool_arg"|"tool_result"|"tool_end"|"turn_end", ...}
          {"type": "done", "conversation": {...}}
          {"type": "stopped", "conversation": {...}}
          {"type": "error", "error": message}

        Host-mutating tools are staged (never auto-run, RULE_21): the
        ``tool_end`` frame carries ``status:"needs_confirmation"`` +
        ``execution_id`` for the confirm/decline endpoints.
        """
        serializer = AgentActionStreamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def event_stream():
            try:
                for frame in self.intelligence.run_agent_action_stream(
                    user=request.user,
                    conversation_id=pk,
                    action_type=serializer.validated_data["action_type"],
                    tool=serializer.validated_data.get("tool") or None,
                    agent=serializer.validated_data.get("agent") or None,
                    args=serializer.validated_data.get("args") or {},
                    verbosity=serializer.validated_data.get("verbosity", "concise"),
                ):
                    yield f"data: {json.dumps(frame)}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-generation")
    def stop_generation(self, request, pk=None):
        """Request cancellation of a running generation (idempotent)."""
        try:
            result = self.intelligence.stop_generation(
                user=request.user,
                conversation_id=pk,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="messages/(?P<message_id>[^/.]+)/regenerate",
        url_name="regenerate-message",
    )
    def regenerate_message(self, request, pk=None, message_id=None):
        """Regenerate an assistant reply (non-streaming)."""
        try:
            conversation = self.intelligence.regenerate_message(
                user=request.user,
                conversation_id=pk,
                message_id=message_id,
            )
            return Response(conversation)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["patch", "delete"],
        # `(?!stream/)` keeps the literal `messages/stream/` SSE route from
        # being shadowed by this parameterized route: DRF registers extra
        # actions alphabetically, so `edit_message` would otherwise match
        # "stream" as a message_id and reject POST with 405.  PATCH + DELETE
        # share this route to avoid two identical-regex routes (the first would
        # swallow the other's method with a 405).
        url_path="messages/(?P<message_id>(?!stream/)[^/.]+)",
        url_name="edit-message",
    )
    def edit_message(self, request, pk=None, message_id=None):
        """PATCH: edit a user message (optional ``regenerate``).

        DELETE: soft-delete a message (and its descendants for a user turn).
        """
        if request.method == "DELETE":
            try:
                conversation = self.intelligence.delete_message(
                    user=request.user,
                    conversation_id=pk,
                    message_id=message_id,
                )
                return Response(conversation)
            except ValueError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = EditMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            conversation = self.intelligence.edit_message(
                user=request.user,
                conversation_id=pk,
                message_id=message_id,
                content=serializer.validated_data["content"],
                regenerate=serializer.validated_data.get("regenerate", True),
            )
            return Response(conversation)
        except NotUserMessageError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="messages/(?P<user_message_id>[^/.]+)/retry",
        url_name="retry-message",
    )
    def retry_message(self, request, pk=None, user_message_id=None):
        """Retry a user turn (regenerate) as Server-Sent Events.

        Aborts any in-flight generation, re-runs the pipeline for that turn
        using its context snapshot, and streams a fresh assistant reply.
        """
        serializer = RetryMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def event_stream():
            try:
                for frame in self.intelligence.retry_message_stream(
                    user=request.user,
                    conversation_id=pk,
                    user_message_id=user_message_id,
                    model=serializer.validated_data.get("model") or None,
                ):
                    yield f"data: {json.dumps(frame)}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    @action(detail=True, methods=["post"], url_path="summary", url_name="summarize")
    def summarize(self, request, pk=None):
        """Generate (or force-refresh) a conversation's rolling summary."""
        force = bool(request.data.get("force", False))

        try:
            conversation = self.intelligence.summarize_conversation(
                user=request.user,
                conversation_id=pk,
                force=force,
            )
            return Response(conversation)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="tool-executions/confirm",
        url_name="confirm-tool-execution",
    )
    def confirm_tool_execution(self, request, pk=None):
        """Confirm a staged tool execution (e.g. create_dq_rule proposal).

        Executes the staged mutation in-process as the requesting user and
        appends a grounded assistant message carrying the navigate action —
        so the UI can "fly" to the created entity.  Only executions staged
        inside this conversation and owned by the requesting user can be
        confirmed (defense-in-depth: the executor re-checks ownership too).
        """
        from asgiref.sync import async_to_sync

        from ai.engine_runtime import _carbon_instance_config
        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor
        from ai.serializers import ToolExecutionActionSerializer

        serializer = ToolExecutionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        execution_id = serializer.validated_data["execution_id"]
        modified_body = serializer.validated_data.get("body")

        conversation = self.intelligence._get_accessible_conversation(request.user, pk)
        if conversation is None:
            return Response(
                {"error": f"Conversation {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from ai.models import ToolExecution as ToolExecutionModel

        try:
            execution = ToolExecutionModel.objects.get(
                id=execution_id, conversation_id=str(conversation.id)
            )
        except ToolExecutionModel.DoesNotExist:
            return Response(
                {"error": "Execution not found in this conversation."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_pk = str(request.user.pk)
        if execution.host_user_id and execution.host_user_id != user_pk:
            return Response(
                {"error": "This execution belongs to another user."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if execution.status != "pending_confirmation":
            return Response(
                {"error": f"Execution is not pending confirmation (status: {execution.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optional "modify before confirm": the user edited the proposed rule in
        # the JSON editor — replace the staged POST body so confirm_execution
        # (which re-reads the row fresh from the DB) executes the edited body.
        # Atomic: either the edited rule is created or nothing happens.
        if modified_body is not None:
            if not isinstance(modified_body, dict):
                return Response(
                    {"error": "Modified rule body must be a JSON object."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            input_params = (
                json.loads(execution.input_params) if execution.input_params else {}
            )
            input_params["body"] = modified_body
            execution.input_params = json.dumps(input_params)
            execution.save(update_fields=["input_params"])

        instance_config = _carbon_instance_config(user_pk)
        factory = get_session_factory("carbon")

        def _run():
            async def _confirm():
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config=instance_config,
                        user_token=f"inproc:carbon:{user_pk}",
                        host_user_id=user_pk,
                    )
                    return await executor.confirm_execution(
                        execution_id, expected_host_user_id=user_pk
                    )

            return async_to_sync(_confirm)()

        try:
            result = _run()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            logger.warning("Tool execution confirm failed: %s", exc, exc_info=True)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Persist the confirmed outcome as a grounded assistant message so the
        # confirmation survives reloads.  Memory writes (learn_fact/forget_fact)
        # produce a truthful message with no navigate action — they are not DQ
        # rules.  Runs in the sync view context (no event loop), so direct ORM
        # writes are safe here.
        data = (result or {}).get("data") or result or {}
        kind = (result or {}).get("kind")
        operation = (result or {}).get("operation")

        if kind == "memory":
            if operation == "forget":
                self.intelligence._save_assistant_message(
                    conversation,
                    "✅ Forgot that fact.",
                    metadata={},
                    status="completed",
                )
            else:
                fact_text = data.get("fact") or ""
                self.intelligence._save_assistant_message(
                    conversation,
                    f"✅ Remembered: {fact_text}",
                    metadata={},
                    status="completed",
                )
            return Response(
                {
                    "status": "confirmed",
                    "kind": "memory",
                    "operation": operation,
                    "memory_id": data.get("id") or "",
                    "action": None,
                }
            )

        rule_id = data.get("id") or ""
        rule_name = data.get("name") or "rule"
        if rule_id:
            self.intelligence._save_assistant_message(
                conversation,
                f"✅ DQ rule '{rule_name}' created.",
                metadata={
                    "action": {
                        "type": "navigate",
                        "route": f"/dq/rules/{rule_id}",
                        "label": "View rule",
                        "summary": (
                            f"Rule '{rule_name}' created — opened its detail page."
                        ),
                    }
                },
                status="completed",
            )
        return Response(
            {
                "status": "confirmed",
                "rule_id": rule_id,
                "rule_name": rule_name,
                "action": (
                    {
                        "type": "navigate",
                        "route": f"/dq/rules/{rule_id}",
                        "label": "View rule",
                        "summary": f"Rule '{rule_name}' created.",
                    }
                    if rule_id
                    else None
                ),
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="tool-executions/decline",
        url_name="decline-tool-execution",
    )
    def decline_tool_execution(self, request, pk=None):
        """Decline a staged tool execution — nothing is written."""
        from asgiref.sync import async_to_sync

        from ai.engine_runtime import _carbon_instance_config
        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor
        from ai.serializers import ToolExecutionActionSerializer

        serializer = ToolExecutionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        execution_id = serializer.validated_data["execution_id"]

        conversation = self.intelligence._get_accessible_conversation(request.user, pk)
        if conversation is None:
            return Response(
                {"error": f"Conversation {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from ai.models import ToolExecution as ToolExecutionModel

        try:
            execution = ToolExecutionModel.objects.get(
                id=execution_id, conversation_id=str(conversation.id)
            )
        except ToolExecutionModel.DoesNotExist:
            return Response(
                {"error": "Execution not found in this conversation."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_pk = str(request.user.pk)
        if execution.host_user_id and execution.host_user_id != user_pk:
            return Response(
                {"error": "This execution belongs to another user."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if execution.status != "pending_confirmation":
            return Response(
                {"error": f"Execution is not pending confirmation (status: {execution.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        factory = get_session_factory("carbon")

        def _run():
            async def _decline():
                async with factory() as db:
                    executor = CarbonHostExecutor(
                        db=db,
                        instance_config=_carbon_instance_config(user_pk),
                        user_token=f"inproc:carbon:{user_pk}",
                        host_user_id=user_pk,
                    )
                    await executor.decline_execution(
                        execution_id, expected_host_user_id=user_pk
                    )

            return async_to_sync(_decline)()

        try:
            _run()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            logger.warning("Tool execution decline failed: %s", exc, exc_info=True)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sync context (no event loop) — safe for direct ORM writes.
        self.intelligence._save_assistant_message(
            conversation,
            "❌ Declined — nothing was created.",
            metadata={},
            status="completed",
        )
        return Response({"status": "declined"})

    @action(detail=True, methods=["get"], url_path="export", url_name="export")
    def export(self, request, pk=None):
        """Export a conversation as JSON or Markdown (?fmt=json|markdown).

        The param is ``fmt`` (not ``format``) because DRF reserves ``format``
        for URL_FORMAT_OVERRIDE content negotiation, which 404s on unknown
        renderer formats (QA F2).
        """
        fmt = request.query_params.get("fmt", "json")
        if fmt not in ("json", "markdown"):
            return Response(
                {"error": f"Unsupported export format: {fmt}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.intelligence.export_conversation(
                user=request.user,
                conversation_id=pk,
                fmt=fmt,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"], url_path="suggestions", url_name="suggestions")
    def suggestions(self, request, pk=None):
        """List pending proactive suggestions scoped to the user.

        The ``pk`` is only used to verify access to the active thread; the
        result set is the user's workspace-level suggestion rail.
        """
        limit = request.query_params.get("limit", 10)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))

        try:
            suggestions = self.intelligence.list_proactive_suggestions(
                user=request.user,
                conversation_id=pk,
                limit=limit,
            )
            return Response({"suggestions": suggestions})
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="resume", url_name="resume")
    def resume(self, request, pk=None):
        """Mark a conversation as resumed and return a catch-up summary."""
        try:
            result = self.intelligence.resume_conversation(
                user=request.user,
                conversation_id=pk,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/accept", url_name="suggestion-accept")
    def accept_suggestion(self, request, pk=None, suggestion_id=None):
        """Accept a proactive suggestion."""
        try:
            result = self.intelligence.acknowledge_proactive_suggestion(
                user=request.user,
                conversation_id=pk,
                suggestion_id=suggestion_id,
                disposition="acknowledged",
            )
            return Response(result)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="suggestions/(?P<suggestion_id>[^/.]+)/dismiss", url_name="suggestion-dismiss")
    def dismiss_suggestion(self, request, pk=None, suggestion_id=None):
        """Dismiss a proactive suggestion (optionally with a reason)."""
        try:
            result = self.intelligence.acknowledge_proactive_suggestion(
                user=request.user,
                conversation_id=pk,
                suggestion_id=suggestion_id,
                disposition="dismissed",
                reason=request.data.get("reason") if request.data else None,
            )
            return Response(result)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="suggestions", url_name="workspace-suggestions")
    def workspace_suggestions(self, request):
        """List pending proactive suggestions workspace-wide (no conversation pk)."""
        limit = request.query_params.get("limit", 10)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))
        suggestions = self.intelligence.list_proactive_suggestions(
            user=request.user,
            limit=limit,
        )
        return Response({"suggestions": suggestions})

    # ── Sprint 20 W1-B — context lifecycle (checkpoint/restore/fork/clear) ─
    @action(detail=True, methods=["post"], url_path="checkpoint", url_name="checkpoint-conversation")
    def checkpoint(self, request, pk=None):
        """Save a named snapshot of the conversation's working context.

        Idempotent: re-saving the same ``name`` overwrites the existing
        checkpoint.  Mutating console action → ``ai:manage_console``.
        """
        if not has_capability(request.user, "ai:manage_console"):
            raise PermissionDenied(
                "Saving a checkpoint requires ai:manage_console."
            )

        serializer = CheckpointCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            checkpoint = self.intelligence.checkpoint_conversation(
                user=request.user,
                conversation_id=pk,
                name=serializer.validated_data["name"],
                note=serializer.validated_data.get("note", ""),
            )
            return Response(checkpoint)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"], url_path="checkpoints", url_name="checkpoints")
    def checkpoints(self, request, pk=None):
        """List the conversation's named checkpoints, newest first (picker).

        Read-only console action → ``ai:view_console``.
        """
        if not has_capability(request.user, "ai:view_console"):
            raise PermissionDenied(
                "Listing checkpoints requires ai:view_console."
            )

        try:
            checkpoints = self.intelligence.list_checkpoints(
                user=request.user,
                conversation_id=pk,
            )
            return Response({"checkpoints": checkpoints})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="restore", url_name="restore-conversation")
    def restore(self, request, pk=None):
        """Re-seed the conversation's working context from a checkpoint.

        Does NOT overwrite the durable message log.  Mutating console action
        → ``ai:manage_console``.
        """
        if not has_capability(request.user, "ai:manage_console"):
            raise PermissionDenied(
                "Restoring a checkpoint requires ai:manage_console."
            )

        serializer = CheckpointActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            conversation = self.intelligence.restore_conversation(
                user=request.user,
                conversation_id=pk,
                checkpoint_id=serializer.validated_data["checkpoint_id"],
            )
            return Response(conversation)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="fork", url_name="fork-conversation")
    def fork(self, request, pk=None):
        """Clone the conversation into a NEW row seeded from a checkpoint.

        Returns the new conversation id — never aliases the source row.
        Mutating console action → ``ai:manage_console``.
        """
        if not has_capability(request.user, "ai:manage_console"):
            raise PermissionDenied(
                "Forking a conversation requires ai:manage_console."
            )

        serializer = CheckpointActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            conversation = self.intelligence.fork_conversation(
                user=request.user,
                conversation_id=pk,
                checkpoint_id=serializer.validated_data["checkpoint_id"],
            )
            return Response(
                conversation, status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="clear-context", url_name="clear-context")
    def clear_context(self, request, pk=None):
        """Reset the conversation's working context (summary + snapshot).

        Never deletes the conversation row, the message log, or learned
        facts.  Mutating console action → ``ai:manage_console``.
        """
        if not has_capability(request.user, "ai:manage_console"):
            raise PermissionDenied(
                "Clearing context requires ai:manage_console."
            )

        try:
            conversation = self.intelligence.clear_context(
                user=request.user,
                conversation_id=pk,
            )
            return Response(conversation)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)


class WorkspaceArtifactViewSet(viewsets.GenericViewSet):
    """AI Workspace artifact API."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._intelligence: CarbonIntelligence | None = None

    @property
    def intelligence(self) -> CarbonIntelligence:
        if self._intelligence is None:
            self._intelligence = CarbonIntelligence()
        return self._intelligence

    def list(self, request):
        return Response(self.intelligence.list_artifacts(user=request.user))

    def create(self, request):
        serializer = ArtifactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            artifact = self.intelligence.create_artifact(
                user=request.user,
                **serializer.validated_data,
            )
            return Response(artifact, status=status.HTTP_201_CREATED)
        except PermissionDenied as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    def retrieve(self, request, pk=None):
        try:
            return Response(self.intelligence.get_artifact(request.user, pk))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, pk=None):
        serializer = ArtifactUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            artifact = self.intelligence.update_artifact(
                request.user,
                pk,
                **serializer.validated_data,
            )
            return Response(artifact)
        except PermissionDenied as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, pk=None):
        try:
            return Response(self.intelligence.delete_artifact(request.user, pk))
        except PermissionDenied as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get", "post"], url_path="messages", url_name="send-message")
    def send_message(self, request, pk=None):
        """GET: paginate messages. POST: send a message and get AI response.

        Both share ``conversations/{id}/messages/`` (list vs. create). DRF cannot
        register two ``@action`` methods on the same ``url_path`` without one
        shadowing the other, so the two operations are dispatched by HTTP method
        here.
        """
        if request.method == "GET":
            return self.list_messages(request, pk)

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = self.intelligence.send_message(
                user=request.user,
                conversation_id=pk,
                content=serializer.validated_data["content"],
                model=serializer.validated_data.get("model") or None,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    def list_messages(self, request, pk=None):
        """List a conversation's messages with cursor pagination."""
        serializer = MessageListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        try:
            result = self.intelligence.list_messages(
                user=request.user,
                conversation_id=pk,
                limit=serializer.validated_data.get("limit", 50),
                before=serializer.validated_data.get("before"),
                after=serializer.validated_data.get("after"),
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback", url_name="message-feedback")
    def message_feedback(self, request, pk=None, message_id=None):
        """Record user feedback (accept/reject/correct/ignore) on an AI message."""
        serializer = MessageFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            message = self.intelligence.record_feedback(
                user=request.user,
                conversation_id=pk,
                message_id=message_id,
                outcome=serializer.validated_data["outcome"],
                correction_text=serializer.validated_data.get("correction_text", ""),
            )
            return Response(message)
        except NotAssistantMessageError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="messages/stream", url_name="send-message-stream")
    def send_message_stream(self, request, pk=None):
        """Stream a chat answer as Server-Sent Events.

        Frames are ``data: <json>\n\n``.  Terminal frames are
        ``{"type": "done", "conversation": {...}}`` on success or
        ``{"type": "error", "error": message}`` on failure.
        """
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def event_stream():
            try:
                for frame in self.intelligence.send_message_stream(
                    user=request.user,
                    conversation_id=pk,
                    content=serializer.validated_data["content"],
                    model=serializer.validated_data.get("model") or None,
                ):
                    yield f"data: {json.dumps(frame)}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    @action(detail=True, methods=["post"], url_path="stop", url_name="stop-generation")
    def stop_generation(self, request, pk=None):
        """Request cancellation of a running generation (idempotent)."""
        try:
            result = self.intelligence.stop_generation(
                user=request.user,
                conversation_id=pk,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="messages/(?P<message_id>[^/.]+)/regenerate",
        url_name="regenerate-message",
    )
    def regenerate_message(self, request, pk=None, message_id=None):
        """Regenerate an assistant reply (non-streaming)."""
        try:
            conversation = self.intelligence.regenerate_message(
                user=request.user,
                conversation_id=pk,
                message_id=message_id,
            )
            return Response(conversation)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        detail=True,
        methods=["patch"],
        # `(?!stream/)` keeps the literal `messages/stream/` SSE route from
        # being shadowed by this parameterized route: DRF registers extra
        # actions alphabetically, so `edit_message` would otherwise match
        # "stream" as a message_id and reject POST with 405.
        url_path="messages/(?P<message_id>(?!stream/)[^/.]+)",
        url_name="edit-message",
    )
    def edit_message(self, request, pk=None, message_id=None):
        """Edit a user message's content and regenerate the reply."""
        serializer = EditMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            conversation = self.intelligence.edit_message(
                user=request.user,
                conversation_id=pk,
                message_id=message_id,
                content=serializer.validated_data["content"],
            )
            return Response(conversation)
        except NotUserMessageError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="summary", url_name="summarize")
    def summarize(self, request, pk=None):
        """Generate (or force-refresh) a conversation's rolling summary."""
        force = bool(request.data.get("force", False))

        try:
            conversation = self.intelligence.summarize_conversation(
                user=request.user,
                conversation_id=pk,
                force=force,
            )
            return Response(conversation)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"], url_path="export", url_name="export")
    def export(self, request, pk=None):
        """Export a conversation as JSON or Markdown (?fmt=json|markdown).

        The param is ``fmt`` (not ``format``) because DRF reserves ``format``
        for URL_FORMAT_OVERRIDE content negotiation, which 404s on unknown
        renderer formats (QA F2).
        """
        fmt = request.query_params.get("fmt", "json")
        if fmt not in ("json", "markdown"):
            return Response(
                {"error": f"Unsupported export format: {fmt}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.intelligence.export_conversation(
                user=request.user,
                conversation_id=pk,
                fmt=fmt,
            )
            return Response(result)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )


class UserProfileView(views.APIView):
    """GET/PATCH ``/carbon-api/ai/profile/`` — Phase 22-A user AI preferences.

    GET returns the stored preferences PLUS the resolved effective defaults
    (user profile → domain manifest → system default) so the UI can render
    inherited values.  PATCH upserts the profile row (get_or_create) with the
    validated preference fields.

    Resolution order note (kept in code for future workers):

        system default → domain manifest → user profile → per-message override

    The profile NEVER overrides a per-message override.  Domain manifests are
    per-conversation (resolved at turn time in CarbonIntelligence); the global
    GET resolves profile → system default and reports the manifest tier
    implicitly (a domain default only applies inside that domain's
    conversations).
    """

    permission_classes = [IsAuthenticated]

    _DEFAULT_TEMPERATURE = 0.3
    _DEFAULT_ALERT_THRESHOLD = int(
        getattr(settings, "AI_QUOTA_SOFT_WARNING_PCT", 80)
    )

    @staticmethod
    def _system_default_model() -> str | None:
        """Lowest-tier fallback: the platform default chat model."""
        from ai.engine.llm.router import get_model_for_task

        return get_model_for_task("chat")

    @classmethod
    def _profile_payload(cls, profile, user) -> dict:
        """Stored preferences + resolved effective defaults (UI render shape)."""
        resolved_model = None
        if profile is not None and profile.default_model_id_id is not None:
            resolved_model = profile.default_model_id.model_id
        if not resolved_model:
            resolved_model = cls._system_default_model()
        if profile is None:
            return {
                "default_model_id": None,
                "temperature": cls._DEFAULT_TEMPERATURE,
                "auto_title": True,
                "memory_enabled": True,
                "usage_alert_threshold": cls._DEFAULT_ALERT_THRESHOLD,
                "monthly_token_limit": int(
                    getattr(settings, "AI_DEFAULT_MONTHLY_TOKEN_LIMIT", 1_000_000)
                ),
                "quota_reset_day": 1,
                "resolved_model_id": resolved_model,
            }
        return {
            "default_model_id": (
                profile.default_model_id.model_id
                if profile.default_model_id_id is not None else None
            ),
            "temperature": profile.temperature,
            "auto_title": profile.auto_title,
            "memory_enabled": profile.memory_enabled,
            "usage_alert_threshold": profile.usage_alert_threshold,
            "monthly_token_limit": profile.monthly_token_limit,
            "quota_reset_day": profile.quota_reset_day,
            "resolved_model_id": resolved_model,
        }

    def get(self, request):
        """Return stored preferences + resolved effective defaults."""
        from ai.models import AIUserProfile

        profile = (
            AIUserProfile.objects.select_related("default_model_id")
            .filter(user=request.user)
            .first()
        )
        return Response(self._profile_payload(profile, request.user))

    def patch(self, request):
        """Upsert the profile with validated preference fields (PATCH)."""
        from ai.models import AIUserProfile

        serializer = UserProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = AIUserProfile.objects.get_or_create(user=request.user)
        for field in (
            "default_model_id",
            "temperature",
            "auto_title",
            "memory_enabled",
            "usage_alert_threshold",
        ):
            if field in serializer.validated_data:
                setattr(profile, field, serializer.validated_data[field])
        profile.save()
        return Response(self._profile_payload(profile, request.user))
