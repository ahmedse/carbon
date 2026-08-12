"""
AI Workspace REST API — conversation CRUD + messaging.

POST   /carbon-api/ai/workspace/conversations/
GET    /carbon-api/ai/workspace/conversations/
GET    /carbon-api/ai/workspace/conversations/{id}/
POST   /carbon-api/ai/workspace/conversations/{id}/messages/
"""

import sys, os

# Ensure repo root is on path so that `backend.ai.*` imports resolve.
# Django's manage.py only adds backend/; pytest adds the repo root for tests.
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.intelligence import CarbonIntelligence
from ai.serializers import (
    ConversationListSerializer,
    CreateConversationSerializer,
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

        Query params: status, limit (default 50).
        """
        serializer = ConversationListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        conversations = self.intelligence.list_conversations(
            user=request.user,
            status=serializer.validated_data.get("status"),
            limit=serializer.validated_data.get("limit", 50),
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

    @action(detail=True, methods=["post"], url_path="messages")
    def send_message(self, request, pk=None):
        """Send a message and get AI response."""
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
