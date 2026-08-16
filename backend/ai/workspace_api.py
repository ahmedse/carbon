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

from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.intelligence import (
    CarbonIntelligence,
    NotAssistantMessageError,
    NotUserMessageError,
)
from ai.serializers import (
    ConversationListSerializer,
    ConversationUpdateSerializer,
    CreateConversationSerializer,
    EditMessageSerializer,
    MessageFeedbackSerializer,
    MessageListSerializer,
    SendMessageSerializer,
)


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

    @action(detail=True, methods=["get", "post"], url_path="messages")
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

    @action(detail=True, methods=["post"], url_path="messages/(?P<message_id>[^/.]+)/feedback")
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

    @action(detail=True, methods=["post"], url_path="messages/stream")
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
                ):
                    yield f"data: {json.dumps(frame)}\n\n"
            except ValueError as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream",
        )

    @action(detail=True, methods=["post"], url_path="stop")
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

    @action(detail=True, methods=["post"], url_path="summary")
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

    @action(detail=True, methods=["get"], url_path="export")
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
