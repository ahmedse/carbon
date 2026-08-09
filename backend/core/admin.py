# File: core/admin.py
# Django admin registration for core app models.

from django.contrib import admin
from .models import Module, Feedback, RequestLog


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'scope', 'org_unit']
    search_fields = ['name']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'rating', 'submitted_at']
    search_fields = ['name', 'email', 'message']
    list_filter = ['rating', 'submitted_at']


# ── Phase 1.3: Request Log Viewer ─────────────────────────────────────────────

@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'level', 'method', 'path_truncated', 'status_code',
        'duration_ms', 'user', 'slow_request',
    ]
    list_filter = [
        'level', 'status_code', 'method', 'slow_request',
    ]
    search_fields = ['correlation_id', 'path', 'user']
    date_hierarchy = 'timestamp'
    readonly_fields = [
        'correlation_id', 'level', 'method', 'path', 'user', 'user_id',
        'status_code', 'duration_ms', 'remote_addr', 'slow_request', 'timestamp',
    ]
    actions = ['purge_old_logs']

    def path_truncated(self, obj):
        return obj.path[:80] + ('…' if len(obj.path) > 80 else '')
    path_truncated.short_description = 'Path'
    path_truncated.admin_order_field = 'path'

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        from django.conf import settings
        return settings.DJANGO_ENV != 'production'

    @admin.action(description='Purge logs older than retention period')
    def purge_old_logs(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        try:
            from accounts.models import LogConfig
            cfg = LogConfig.load()
            cutoff = timezone.now() - timedelta(days=cfg.retention_days)
        except Exception:
            cutoff = timezone.now() - timedelta(days=90)
        count, _ = self.model.objects.filter(timestamp__lt=cutoff).delete()
        self.message_user(request, f'Purged {count} log entries older than {cutoff:%Y-%m-%d}.')