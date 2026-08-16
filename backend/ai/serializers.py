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
    workspace_context = serializers.JSONField(required=False, default=None)


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=False)


class EditMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=False)


class ConversationListSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["pending", "working", "needs_input", "completed", "failed"],
        required=False,
    )
    limit = serializers.IntegerField(required=False, default=50, max_value=200, min_value=1)
    q = serializers.CharField(required=False)
    is_archived = serializers.BooleanField(required=False)
    is_pinned = serializers.BooleanField(required=False)
    conversation_type = serializers.ChoiceField(
        choices=["chat", "dq_validate", "dq_suggest", "nl_query", "anomaly"],
        required=False,
    )
    cursor = serializers.CharField(required=False)


class ConversationUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    is_pinned = serializers.BooleanField(required=False)
    is_archived = serializers.BooleanField(required=False)
    visibility = serializers.ChoiceField(
        choices=["private", "shared"],
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field is required.")
        return attrs


class MessageListSerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, default=50, max_value=200, min_value=1)
    before = serializers.CharField(required=False)
    after = serializers.CharField(required=False)


class MessageFeedbackSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=["accepted", "rejected", "corrected", "ignored"],
    )
    correction_text = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs.get("outcome") == "corrected" and not attrs.get("correction_text", "").strip():
            raise serializers.ValidationError(
                {"correction_text": "A correction is required when outcome is 'corrected'."}
            )
        return attrs
