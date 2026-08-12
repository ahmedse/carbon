"""
AI Workspace serializers — request/response shapes for the workspace API.
"""

from rest_framework import serializers


class CreateConversationSerializer(serializers.Serializer):
    conversation_type = serializers.ChoiceField(
        choices=["chat", "dq_validate", "dq_suggest", "nl_query", "anomaly"],
        default="chat",
    )
    title = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    app_identifier = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True,
    )
    task_payload = serializers.JSONField(required=False, default=dict)


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=False)


class ConversationListSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["pending", "working", "needs_input", "completed", "failed"],
        required=False,
    )
    limit = serializers.IntegerField(required=False, default=50, max_value=200, min_value=1)
