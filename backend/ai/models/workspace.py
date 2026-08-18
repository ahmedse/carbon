"""AI Workspace models — persistent conversations and messages.

AI CONTRACT §10: Carbon owns conversation state; providers are stateless.
Multi-turn conversations are persisted here and carried to every AI call
as ConversationContext.

These models predate Phase 2 and live alongside the 49 vendored engine tables.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Per-user monthly token budget default. Overridable via settings
# ``AI_DEFAULT_MONTHLY_TOKEN_LIMIT`` (see config/settings.py).
DEFAULT_MONTHLY_TOKEN_LIMIT = getattr(
    settings, "AI_DEFAULT_MONTHLY_TOKEN_LIMIT", 1_000_000
)


class AIConversation(models.Model):
    """A multi-turn AI conversation persisted across sessions.

    Each conversation has a type (chat, dq_validate, etc.) and tracks
    its state through a finite state machine:
        pending → working → needs_input → working → completed
                       ↘                          ↗
                         failed ─────────────────┘
    """

    # Core types are fixed; domain apps may declare additional task types via
    # ``DomainAIOperations.supported_task_types`` (see
    # ai.domain_protocol.supported_conversation_types). The full set is the
    # union of both — this list documents the built-in core only.
    CONVERSATION_TYPES = [
        ("chat", "Chat"),
        ("dq_validate", "DQ Validate"),
        ("dq_suggest", "DQ Suggest"),
        ("nl_query", "NL Query"),
        ("anomaly", "Anomaly"),
        ("investigate", "Investigate"),
        ("nl_rule_test", "NL Rule Test"),
        ("report_draft", "Report Draft"),
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
    last_summarized_message_id = models.UUIDField(
        null=True,
        blank=True,
        default=None,
        help_text="Latest AIMessage id included when the rolling summary was last generated.",
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Denormalized sort/group key from the latest AIMessage.",
    )
    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="When the user last opened/resumed this conversation "
                  "(drives the >24h resume catch-up summary).",
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
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="replies",
        help_text="User turn this reply answers (thread structure for delete-descendants).",
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft-delete flag. Deleted messages are excluded from context "
                  "assembly but rendered dimmed in the thread.",
    )
    context_signature = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Opaque hash of the context window (message-id vector + model "
                  "+ profile) at generation time. Never stores message text.",
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


class AIArtifact(models.Model):
    """A durable artifact promoted from an AI conversation."""

    ARTIFACT_TYPES = [
        ("report", "Report"),
        ("rule_set", "Rule Set"),
        ("query", "Query"),
        ("analysis", "Analysis"),
    ]

    VISIBILITY_CHOICES = [
        ("private", "Private"),
        ("shared", "Shared"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    message = models.ForeignKey(
        AIMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="artifacts",
    )
    title = models.CharField(max_length=255)
    artifact_type = models.CharField(max_length=30, choices=ARTIFACT_TYPES)
    content_json = models.JSONField(default=dict, blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="private")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ai_artifacts",
    )

    class Meta:
        app_label = "ai"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "visibility", "-created_at"], name="ai_art_conv_vis_idx"),
            models.Index(fields=["created_by", "visibility"], name="ai_art_creator_vis_idx"),
            models.Index(fields=["artifact_type", "visibility"], name="ai_art_type_vis_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.artifact_type})"


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
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Set once at completion; the aggregation window key (period).",
    )
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

    # ── Phase 21-A: usage is a first-class generation attribute ──────────
    # Written once at completion; never recomputed from prompt text later.
    model_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Stable ModelCatalog.model_id slug (usage attribution).",
    )
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("0.0"),
        help_text="USD cost computed from ModelCatalog rates (never ad hoc).",
    )

    class Meta:
        app_label = "ai"
        indexes = [
            models.Index(
                fields=["conversation", "status", "completed_at"],
                name="ai_gen_conv_status_done_idx",
            ),
        ]

    def __str__(self):
        return f"{self.conversation_id} [{self.status}]"


class AIUserProfile(models.Model):
    """Per-user AI settings — quota budget + reset rule (Phase 21-A).

    A durable 1:1 extension of the auth user.  Phase 15 introduced profile
    *injection* (``_user_profile_message``) but never a durable model; this
    closes that gap and is the target Phase 22-A extends with preferences.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_profile",
    )
    monthly_token_limit = models.BigIntegerField(
        default=DEFAULT_MONTHLY_TOKEN_LIMIT,
        help_text="Monthly token budget (soft warning at 80%, hard stop at 100%).",
    )
    quota_reset_day = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Day of month (1-28) the monthly token quota resets.",
    )

    # ── Phase 22-A: per-user preferences ──────────────────────────────────
    # RESOLUTION ORDER (low → high), applied at turn time in
    # CarbonIntelligence (ai/intelligence.py):
    #
    #     system default → domain manifest → user profile → per-message override
    #
    # The user profile NEVER overrides a per-message override, and the domain
    # manifest NEVER overrides the profile.  Per-message wins because the
    # frontend model picker is a deliberate per-turn choice; the profile is a
    # durable default; the manifest is a per-domain recommendation; the
    # settings are the platform floor.  Future workers: keep this order in the
    # resolution helper — swapping profile and per-message would be a
    # correctness bug.
    default_model_id = models.ForeignKey(
        "ai.ModelCatalog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=(
            "Durable per-user default model (Phase 20-A catalog FK). "
            "Resolved AFTER the domain manifest default and BEFORE any "
            "per-message override."
        ),
    )
    temperature = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
        help_text="Default chat sampling temperature (0.0-2.0).",
    )
    auto_title = models.BooleanField(
        default=True,
        help_text="Auto-title conversations from the first user message.",
    )
    memory_enabled = models.BooleanField(
        default=True,
        help_text="Inject the user's long-term memory tier (T4) into turns.",
    )
    usage_alert_threshold = models.PositiveSmallIntegerField(
        default=int(getattr(settings, "AI_QUOTA_SOFT_WARNING_PCT", 80)),
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Soft-warning percent of the monthly token limit (1-100).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ai"
        verbose_name = "AI User Profile"
        verbose_name_plural = "AI User Profiles"

    def __str__(self):
        return f"{self.user_id} (limit={self.monthly_token_limit})"

    def quota_reset_at(self, now=None) -> "datetime":
        """Return the next reset datetime (day ``quota_reset_day`` of month).

        If the reset day has already passed this month, returns next month.
        Day is clamped to 28 to stay valid in every month.
        """
        from django.utils import timezone

        now = now or timezone.now()
        day = max(1, min(int(self.quota_reset_day), 28))
        year, month = now.year, now.month
        try:
            reset = now.replace(
                year=year, month=month, day=day, hour=0, minute=0,
                second=0, microsecond=0,
            )
        except ValueError:  # pragma: no cover - day clamped to <=28
            reset = now.replace(
                year=year, month=month, day=28, hour=0, minute=0,
                second=0, microsecond=0,
            )
        if reset <= now:
            # Next month's reset day.
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
            reset = reset.replace(year=year, month=month, day=day)
        return reset

    def quota_window_start(self, now=None) -> "datetime":
        """Return the start of the current billing window (most recent reset)."""
        from django.utils import timezone

        now = now or timezone.now()
        day = max(1, min(int(self.quota_reset_day), 28))
        try:
            candidate = now.replace(
                day=day, hour=0, minute=0, second=0, microsecond=0,
            )
        except ValueError:  # pragma: no cover - day clamped to <=28
            candidate = now.replace(
                day=28, hour=0, minute=0, second=0, microsecond=0,
            )
        if candidate > now:
            # This month's reset is still ahead → window started last month.
            if now.month == 1:
                candidate = candidate.replace(year=now.year - 1, month=12)
            else:
                candidate = candidate.replace(month=now.month - 1)
        return candidate
