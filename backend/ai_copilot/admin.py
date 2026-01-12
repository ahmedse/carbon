"""
Django Admin Configuration for AI Copilot
"""

from django.contrib import admin
from .models import ConversationMessage, ProactiveInsight, UserAIPreference


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'created_at', 'project']
    list_filter = ['role', 'created_at', 'project']
    search_fields = ['user__email', 'content', 'project__name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Message Info', {
            'fields': ('user', 'project', 'role', 'content')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProactiveInsight)
class ProactiveInsightAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'urgency', 'acknowledged', 'created_at']
    list_filter = ['urgency', 'acknowledged', 'created_at']
    search_fields = ['title', 'description', 'user__email', 'project__name']
    readonly_fields = ['created_at', 'acknowledged_at']
    actions = ['mark_acknowledged']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Insight Details', {
            'fields': ('user', 'project', 'urgency', 'title', 'description')
        }),
        ('Actions', {
            'fields': ('actions',)
        }),
        ('Status', {
            'fields': ('acknowledged', 'acknowledged_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def mark_acknowledged(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(acknowledged=True, acknowledged_at=timezone.now())
        self.message_user(request, f"{updated} insight(s) marked as acknowledged.")
    mark_acknowledged.short_description = "Mark selected insights as acknowledged"


@admin.register(UserAIPreference)
class UserAIPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'updated_at']
    search_fields = ['user__email']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Preferences', {
            'fields': ('preferences',)
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
