"""
AI Workspace models — persistent conversations and messages.

AI CONTRACT §10: Carbon owns conversation state; providers are stateless.
Multi-turn conversations are persisted here and carried to every AI call
as ConversationContext.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
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

    class Meta:
        ordering = ["created_at"]
        verbose_name = "AI Message"
        verbose_name_plural = "AI Messages"

    def __str__(self):
        return f"{self.role} @ {self.created_at:%Y-%m-%d %H:%M}"
