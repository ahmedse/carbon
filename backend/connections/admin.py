# connections/admin.py
from django.contrib import admin
from .models import DataSource, ConsumingConnection


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'status', 'owner', 'last_tested_at', 'updated_at']
    list_filter = ['source_type', 'status', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'source_type', 'description')}),
        ('Configuration', {'fields': ('connection_config', 'status')}),
        ('Metadata', {'fields': ('domain', 'owner')}),
        ('Testing', {'fields': ('last_tested_at', 'last_test_status')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(ConsumingConnection)
class ConsumingConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'system_type', 'is_active', 'owner', 'last_used_at', 'updated_at']
    list_filter = ['system_type', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'api_key_hash', 'api_key_salt', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'system_type', 'description')}),
        ('Configuration', {'fields': ('scopes', 'is_active')}),
        ('API Key', {'fields': ('api_key_hash', 'api_key_salt'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('owner', 'last_used_at')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
