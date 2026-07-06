# File: accounts/admin.py
# Django admin registration for accounts app models.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, ScopedRole, RoleAssignmentAuditLog

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