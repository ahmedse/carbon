"""Django admin registration for AI Workspace models."""

from django.contrib import admin

from .models import AIConversation, AIMessage


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
