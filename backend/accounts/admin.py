# File: accounts/admin.py
# Purpose: Admin configuration for User, Role, Context, and RoleAssignment models.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Context, RoleAssignment

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for the User model.
    """
    pass

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin interface for managing roles.
    """
    list_display = ('name', 'description')

@admin.register(Context)
class ContextAdmin(admin.ModelAdmin):
    """
    Admin interface for managing contexts.
    """
    list_display = ('type', 'project', 'cycle', 'module')
    list_filter = ('type', 'project', 'cycle', 'module')

@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    """
    Admin interface for managing role assignments.
    """
    list_display = ('user', 'role', 'context')
    list_filter = ('role', 'context__type', 'context__project', 'context__cycle', 'context__module')