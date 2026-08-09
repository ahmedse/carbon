# File: accounts/admin.py
# Django admin registration for accounts app models.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import (
    User, ScopedRole, RoleAssignmentAuditLog, PlatformAppConfig,
    EmailConfig, PasswordPolicy,
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