# File: accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Tenant, User, Role, Context, RoleAssignment

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'tenant', 'is_staff', 'is_superuser')
    list_filter = ('tenant', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Context)
class ContextAdmin(admin.ModelAdmin):
    list_display = ('type', 'project', 'module')
    list_filter = ('type', 'project', 'module')

@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'context')
    list_filter = ('role', 'context__type', 'context__project', 'context__module', 'user__tenant')
    search_fields = ('user__username', 'role__name')