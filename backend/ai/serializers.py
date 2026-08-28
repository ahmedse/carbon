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
    # trim_whitespace ensures " " is treated as blank. Blank is ALLOWED here —
    # an empty/whitespace message is normalized to a greeting downstream in
    # Intelligence.send_message (never a 400; the assistant responds helpfully).
    content = serializers.CharField(required=True, allow_blank=True, trim_whitespace=True)
    model = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


class EditMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=False)
    # Phase 19-A — when false, only the stored text is edited (no regenerate).
    regenerate = serializers.BooleanField(required=False, default=True)


class RetryMessageSerializer(serializers.Serializer):
    # Optional model override (Phase 18 reuse) for the retry/regenerate path.
    model = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)


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


class ToolExecutionActionSerializer(serializers.Serializer):
    """Body for confirming/declining a staged tool execution (Sprint fly-to-rule).

    ``body`` is optional and only meaningful on confirm: when present it
    REPLACES the staged host POST body before execution, so a user can modify
    the proposed rule (e.g. tweak params / severity in the JSON editor) and
    confirm the edited version in one atomic call.
    """

    execution_id = serializers.CharField(required=True, allow_blank=False)
    body = serializers.JSONField(required=False, allow_null=True)


class CheckpointCreateSerializer(serializers.Serializer):
    """Body for POST ``conversations/{id}/checkpoint/`` (Sprint W1-B).

    ``name`` is required and unique per conversation — re-saving the same
    name overwrites the existing checkpoint (idempotent snapshot).
    """

    name = serializers.CharField(max_length=120, allow_blank=False)
    note = serializers.CharField(
        required=False, allow_blank=True, default="",
    )


class CheckpointActionSerializer(serializers.Serializer):
    """Body for POST ``conversations/{id}/restore/`` and ``.../fork/``.

    ``checkpoint_id`` selects which named snapshot to restore or fork from.
    """

    checkpoint_id = serializers.UUIDField(required=True)


class AgentActionStreamSerializer(serializers.Serializer):
    """Body for streaming an agent/tool action run (Sprint W1-A).

    ``{action_type: "tool"|"agent", tool?, agent?, args, verbosity}`` —
    ``tool`` is required for ``action_type="tool"``, ``agent`` for
    ``action_type="agent"``.  ``verbosity`` selects the clustered frame set:
    ``concise`` (headers only) vs ``full`` (adds ``tool_arg`` + redacted
    ``tool_result`` bodies).
    """

    action_type = serializers.ChoiceField(choices=["tool", "agent"])
    tool = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None,
    )
    agent = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None,
    )
    args = serializers.JSONField(required=False, default=dict)
    verbosity = serializers.ChoiceField(
        choices=["concise", "full"], required=False, default="concise",
    )

    def validate(self, attrs):
        action_type = attrs.get("action_type")
        if action_type == "tool" and not attrs.get("tool"):
            raise serializers.ValidationError(
                {"tool": "tool is required for action_type='tool'."}
            )
        if action_type == "agent" and not attrs.get("agent"):
            raise serializers.ValidationError(
                {"agent": "agent is required for action_type='agent'."}
            )
        return attrs


class UserProfileSerializer(serializers.Serializer):
    """GET/PATCH body for ``/ai/profile/`` (Phase 22-A).

    GET returns the stored preferences plus resolved effective defaults so the
    UI can render inherited values; PATCH accepts only the writable preference
    fields and upserts the profile row.
    """

    # ── Writable preferences (PATCH) ─────────────────────────────────────
    # Stable ModelCatalog ``model_id`` slug; null/"" clears the preference.
    default_model_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, default=None,
    )
    temperature = serializers.FloatField(
        required=False, min_value=0.0, max_value=2.0,
    )
    auto_title = serializers.BooleanField(required=False)
    memory_enabled = serializers.BooleanField(required=False)
    usage_alert_threshold = serializers.IntegerField(
        required=False, min_value=1, max_value=100,
    )

    # ── Resolved / read-only (GET) ───────────────────────────────────────
    resolved_model_id = serializers.CharField(read_only=True, allow_null=True)
    monthly_token_limit = serializers.IntegerField(read_only=True)
    quota_reset_day = serializers.IntegerField(read_only=True)

    def validate_default_model_id(self, value):
        """Map the catalog slug to a ModelCatalog row (or None to clear)."""
        if not value:
            return None
        from ai.models import ModelCatalog

        model = ModelCatalog.objects.filter(model_id=value).first()
        if model is None:
            raise serializers.ValidationError(
                f"Unknown model '{value}' — not in the model catalog."
            )
        return model
