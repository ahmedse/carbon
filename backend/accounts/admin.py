from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Context, RoleAssignment

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    pass

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Context)
class ContextAdmin(admin.ModelAdmin):
    list_display = ('type', 'project', 'cycle', 'module')
    list_filter = ('type', 'project', 'cycle', 'module')

@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'context')
    list_filter = ('role', 'context__type', 'context__project', 'context__cycle', 'context__module')