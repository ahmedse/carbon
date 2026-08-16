"""AI Workspace models — persistent conversations and messages.

AI CONTRACT §10: Carbon owns conversation state; providers are stateless.
Multi-turn conversations are persisted here and carried to every AI call
as ConversationContext.

These models predate Phase 2 and live alongside the 49 vendored engine tables.
"""

import uuid

from django.conf import settings
from django.db import models


class AIConversation(models.Model):
    """A multi-turn AI conversation persisted across sessions.

    Each conversation has a type (chat, dq_validate, etc.) and tracks
    its state through a finite state machine:
        pending → working → needs_input → working → completed
                       ↘                          ↗
                         failed ─────────────────┘
    """

    CONVERSATION_TYPES = [
        ("chat", "Chat"),
        ("dq_validate", "DQ Validate"),
        ("dq_suggest", "DQ Suggest"),
        ("nl_query", "NL Query"),
        ("anomaly", "Anomaly"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("working", "Working"),
        ("needs_input", "Needs Input"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    app_identifier = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Domain app scope (e.g. 'emissions'). None = platform-level.",
    )
    conversation_type = models.CharField(
        max_length=30,
        choices=CONVERSATION_TYPES,
        default="chat",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    scope_json = models.JSONField(
        blank=True,
        default=dict,
        help_text="Frozen copy of user Scope at conversation creation time (audit trail).",
    )
    task_payload_json = models.JSONField(
        blank=True,
        default=dict,
        help_text="Original task payload (rule_id, table_name, rows, etc.).",
    )
    is_archived = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    summary = models.TextField(
        blank=True,
        default="",
        help_text="Rolling compaction summary of older turns (written in Sprint 15).",
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Denormalized sort/group key from the latest AIMessage.",
    )
    visibility = models.CharField(
        max_length=20,
        choices=[("private", "Private"), ("shared", "Shared")],
        default="private",
    )
    context_snapshot_json = models.JSONField(
        blank=True,
        default=dict,
        help_text="Last-assembled context budget telemetry.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["user", "is_archived", "is_pinned", "-last_message_at"],
                name="ai_conv_user_org_idx",
            ),
            models.Index(
                fields=["user", "app_identifier"],
                name="ai_conv_user_app_idx",
            ),
        ]
        verbose_name = "AI Conversation"
        verbose_name_plural = "AI Conversations"

    def __str__(self):
        return f"{self.title or self.conversation_type} ({self.status})"


class AIMessage(models.Model):
    """A single message within an AI conversation."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata_json = models.JSONField(
        blank=True,
        default=dict,
        help_text="Optional: confidence, suggestions, follow_up_questions.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    token_usage_json = models.JSONField(
        blank=True,
        default=dict,
        help_text="Per-turn usage: model, prompt/completion/total tokens, cost, latency.",
    )
    parent_message_id = models.UUIDField(
        null=True,
        blank=True,
        default=None,
        help_text="Which message this edited/regenerated/replaced.",
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("completed", "Completed"),
            ("partial", "Partial"),
            ("stopped", "Stopped"),
            ("failed", "Failed"),
        ],
        default="completed",
    )
    provider_model = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Model that answered (transparency).",
    )

    OUTCOME_CHOICES = [
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("corrected", "Corrected"),
        ("ignored", "Ignored"),
    ]

    outcome = models.CharField(
        max_length=20,
        choices=OUTCOME_CHOICES,
        blank=True,
        null=True,
        default=None,
        help_text="User judgement on this AI message (learning signal).",
    )
    correction_text = models.TextField(
        blank=True,
        default="",
        help_text="User's correction when outcome='corrected'.",
    )
    learned_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Set once this message's outcome has been consumed by the learning job.",
    )

    class Meta:
        app_label = "ai"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="ai_msg_conv_time_idx",
            ),
        ]
        verbose_name = "AI Message"
        verbose_name_plural = "AI Messages"

    def __str__(self):
        return f"{self.role} @ {self.created_at:%Y-%m-%d %H:%M}"


class AIGeneration(models.Model):
    """Durable cancellation lease for an in-process generation.

    Sprint 13 adds the model + migration only; the in-process registry and
    stop logic land in Sprint 14.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="generations",
    )
    token = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True, default=None)
    status = models.CharField(
        max_length=20,
        default="running",
        choices=[
            ("running", "Running"),
            ("cancelled", "Cancelled"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
    )

    class Meta:
        app_label = "ai"

    def __str__(self):
        return f"{self.conversation_id} [{self.status}]"
