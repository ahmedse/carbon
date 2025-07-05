from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Tenant, User, Role, Context, Permission, RoleAssignment

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'description')
    search_fields = ('code',)

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    # Add 'tenant' to fieldsets and add_fieldsets for editing/creating users
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Tenant Info', {'fields': ('tenant',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Tenant Info', {'fields': ('tenant',)}),
    )
    list_display = ('username', 'email', 'tenant', 'is_staff', 'is_superuser')
    list_filter = ('tenant', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    filter_horizontal = ('permissions',)
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