"""Django admin registration for AI Workspace models."""

from django.contrib import admin

from .models import AcceptanceReport, AIConversation, AIMessage, LearningOutcome


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "conversation_type", "status", "title", "created_at")
    list_filter = ("conversation_type", "status")
    search_fields = ("title", "user__username")
    readonly_fields = ("id", "created_at", "updated_at", "scope_json")


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    list_filter = ("role",)
    readonly_fields = ("id", "created_at")


@admin.register(AcceptanceReport)
class AcceptanceReportAdmin(admin.ModelAdmin):
    """Read-only list view for Flight Director acceptance reports."""

    list_display = ("id", "run", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = (
        "id",
        "run",
        "status",
        "report_json",
        "metrics_json",
        "narrative",
        "created_at",
    )


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    """Read-only list view for Flight Director learning outcomes."""

    list_display = ("id", "run", "pattern", "target", "status", "created_at")
    list_filter = ("status", "target")
    readonly_fields = (
        "id",
        "run",
        "pattern",
        "target",
        "payload_json",
        "status",
        "applied_at",
        "created_at",
    )
