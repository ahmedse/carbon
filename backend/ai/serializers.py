"""
AI Workspace serializers — request/response shapes for the workspace API.
"""

from rest_framework import serializers


class CreateConversationSerializer(serializers.Serializer):
    # Manifest-driven: accepted values are the core types plus every task type
    # declared by a registered domain manifest (see
    # ai.domain_protocol.supported_conversation_types). Validated dynamically
    # below so new domain apps can introduce new types with zero core changes.
    conversation_type = serializers.CharField(max_length=50, default="chat")
    title = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    app_identifier = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True,
    )
    task_payload = serializers.JSONField(required=False, default=dict)
    workspace_context = serializers.JSONField(required=False, default=None)

    def validate_conversation_type(self, value):
        from ai.domain_protocol import supported_conversation_types

        if value not in supported_conversation_types():
            raise serializers.ValidationError(
                f"Unsupported conversation type '{value}'."
            )
        return value


class ArtifactSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    conversation_id = serializers.UUIDField()
    message_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    title = serializers.CharField(max_length=255)
    artifact_type = serializers.ChoiceField(choices=["report", "rule_set", "query", "analysis"])
    content_json = serializers.JSONField()
    visibility = serializers.ChoiceField(choices=["private", "shared"], default="private")
    created_by_id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class ArtifactCreateSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    message_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    title = serializers.CharField(max_length=255)
    artifact_type = serializers.ChoiceField(choices=["report", "rule_set", "query", "analysis"])
    content_json = serializers.JSONField()
    visibility = serializers.ChoiceField(choices=["private", "shared"], required=False, default="private")


class ArtifactUpdateSerializer(serializers.Serializer):
    message_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False)
    artifact_type = serializers.ChoiceField(choices=["report", "rule_set", "query", "analysis"], required=False)
    content_json = serializers.JSONField(required=False)
    visibility = serializers.ChoiceField(choices=["private", "shared"], required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field is required.")
        return attrs


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
    # allow_null=True so an ABSENT is_pinned stays None instead of DRF's
    # default_empty_html=False (which filtered pinned conversations out of the
    # default list and ?q= search — QA F3).
    is_pinned = serializers.BooleanField(required=False, allow_null=True)
    # Manifest-driven filter; validated below against the same dynamic set as
    # CreateConversationSerializer.
    conversation_type = serializers.CharField(max_length=50, required=False)
    cursor = serializers.CharField(required=False)

    def validate_conversation_type(self, value):
        from ai.domain_protocol import supported_conversation_types

        if value not in supported_conversation_types():
            raise serializers.ValidationError(
                f"Unsupported conversation type '{value}'."
            )
        return value


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
