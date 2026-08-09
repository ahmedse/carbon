# File: accounts/admin.py
# Django admin registration for accounts app models.

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.conf import settings
from django.urls import path
from django.shortcuts import redirect
from .models import (
    User, ScopedRole, RoleAssignmentAuditLog, PlatformAppConfig,
    EmailConfig, PasswordPolicy, BackupConfig, BackupRecord,
    LogConfig, APIConfig,
)

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ['id', 'username', 'email', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_active']
    search_fields = ['username', 'email']


@admin.register(ScopedRole)
class ScopedRoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'group', 'org_unit', 'module', 'is_active', 'created_at']
    list_filter = ['group', 'is_active']
    search_fields = ['user__username', 'group__name']

@admin.register(RoleAssignmentAuditLog)
class RoleAssignmentAuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'group', 'org_unit', 'module', 'action', 'timestamp']
    list_filter = ['group', 'action']
    search_fields = ['user__username', 'group__name']


@admin.register(PlatformAppConfig)
class PlatformAppConfigAdmin(admin.ModelAdmin):
    list_display = ['app_id', 'is_enabled', 'display_order', 'updated_at', 'updated_by']
    list_filter = ['is_enabled']
    search_fields = ['app_id']
    list_editable = ['is_enabled', 'display_order']
    ordering = ['display_order', 'app_id']


@admin.register(EmailConfig)
class EmailConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'backend_label', 'host', 'from_email', 'enabled', 'updated_at']
    list_filter = ['enabled']

    def backend_label(self, obj):
        return dict(EmailConfig.BACKEND_CHOICES).get(obj.backend, obj.backend)
    backend_label.short_description = 'Backend'

    def has_add_permission(self, request):
        """Singleton — only one EmailConfig allowed."""
        return not EmailConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False  # Never delete the singleton


@admin.register(PasswordPolicy)
class PasswordPolicyAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'min_length', 'require_uppercase', 'require_lowercase',
        'require_special', 'max_age_days', 'lockout_after_n', 'updated_at',
    ]
    list_editable = [
        'min_length', 'require_uppercase', 'require_lowercase',
        'require_special', 'max_age_days', 'lockout_after_n',
    ]

    def has_add_permission(self, request):
        return not PasswordPolicy.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ── Phase 1.2: Backup Admin ───────────────────────────────────────────────────

@admin.register(BackupConfig)
class BackupConfigAdmin(admin.ModelAdmin):
    list_display = ['frequency', 'retention_days', 's3_bucket', 'enabled', 'last_backup_at']
    list_display_links = ['last_backup_at']
    list_editable = ['frequency', 'retention_days', 'enabled']
    fieldsets = (
        (None, {'fields': ('frequency', 'retention_days', 'enabled')}),
        ('S3 Offsite Storage', {'fields': ('s3_bucket', 's3_path'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('last_backup_at', 'last_backup_size_bytes')}),
    )

    def has_add_permission(self, request):
        return not BackupConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def run_backup_now(self, request):
        """Admin action: trigger a backup immediately."""
        if settings.DJANGO_ENV == 'production':
            settings_label = getattr(settings, 'DJANGO_ENV_LABEL', settings.DJANGO_ENV)
            self.message_user(
                request,
                f'Dangerous action blocked in {settings_label} environment. '
                f'Use staging or run via SSH: manage.py run_backup',
                level=messages.ERROR,
            )
            return redirect('..')
        from django.core.management import call_command
        try:
            call_command('run_backup')
            self.message_user(request, 'Backup initiated successfully.', level=messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f'Backup failed: {exc}', level=messages.ERROR)
        return redirect('..')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('run-backup/', self.admin_site.admin_view(self.run_backup_now), name='accounts-backupconfig-run'),
        ]
        return custom_urls + urls

    change_form_template = 'admin/accounts/backupconfig/change_form.html'


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display = ['filename', 'status', 'size_display', 'location', 'started_at', 'completed_at']
    list_filter = ['status']
    search_fields = ['filename', 'location']
    date_hierarchy = 'started_at'
    readonly_fields = ['filename', 'size_bytes', 'status', 'location', 'error_message', 'started_at', 'completed_at']

    def size_display(self, obj):
        if obj.size_bytes >= 1_048_576:
            return f'{obj.size_bytes / 1_048_576:.1f} MB'
        if obj.size_bytes >= 1024:
            return f'{obj.size_bytes / 1024:.1f} KB'
        return f'{obj.size_bytes} B'
    size_display.short_description = 'Size'
    size_display.admin_order_field = 'size_bytes'

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return settings.DJANGO_ENV != 'production'


# ── Phase 1.3: Log Config Admin ───────────────────────────────────────────────

@admin.register(LogConfig)
class LogConfigAdmin(admin.ModelAdmin):
    list_display = ['default_level', 'db_log_level', 'retention_days', 'json_format', 'updated_at']
    list_display_links = ['updated_at']
    list_editable = ['default_level', 'db_log_level', 'retention_days']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        return not LogConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ── Phase 1.4: API Config Admin ───────────────────────────────────────────────

@admin.register(APIConfig)
class APIConfigAdmin(admin.ModelAdmin):
    list_display = ['page_size', 'max_page_size', 'enable_pagination', 'updated_at']
    list_display_links = ['updated_at']
    list_editable = ['page_size', 'max_page_size', 'enable_pagination']

    def has_add_permission(self, request):
        return not APIConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False