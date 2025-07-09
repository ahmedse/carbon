# File: accounts/admin.py
# Django admin registration for accounts app models.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import Tenant, User, ScopedRole, RoleAssignmentAuditLog

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at']
    search_fields = ['name']

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ['id', 'username', 'email', 'tenant', 'is_staff', 'is_active']
    list_filter = ['tenant', 'is_staff', 'is_active']
    search_fields = ['username', 'email']
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Tenant Info", {"fields": ("tenant",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Tenant Info", {"fields": ("tenant",)}),
    )


# @admin.register(User)
# class UserAdmin(DjangoUserAdmin):
#     list_display = ['id', 'username', 'email', 'tenant', 'is_staff', 'is_active']
#     list_filter = ['tenant', 'is_staff', 'is_active']
#     search_fields = ['username', 'email']
#     fieldsets = DjangoUserAdmin.fieldsets + (
#         ("Tenant Info", {"fields": ("tenant",)}),
#     )

@admin.register(ScopedRole)
class ScopedRoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'group', 'tenant', 'project', 'module', 'is_active', 'created_at']
    list_filter = ['tenant', 'group', 'is_active']
    search_fields = ['user__username', 'group__name']

@admin.register(RoleAssignmentAuditLog)
class RoleAssignmentAuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'group', 'tenant', 'project', 'module', 'action', 'timestamp']
    list_filter = ['tenant', 'group', 'action']
    search_fields = ['user__username', 'group__name']