# importexport/admin.py
from django.contrib import admin
from .models import ExportProject, ImportJob, ExportJob


@admin.register(ExportProject)
class ExportProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'data_table', 'format', 'schedule', 'is_active', 'owner', 'updated_at']
    list_filter = ['format', 'schedule', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'description')}),
        ('Configuration', {'fields': ('data_table', 'format', 'filters', 'schedule', 'is_active')}),
        ('Metadata', {'fields': ('owner',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'data_table', 'format', 'status', 'row_count', 'error_count', 'user', 'created_at']
    list_filter = ['status', 'format', 'created_at']
    search_fields = ['data_table__title']
    readonly_fields = [
        'id', 'status', 'row_count', 'error_count', 'log', 'started_at', 'finished_at', 'created_at'
    ]
    fieldsets = (
        ('Job Info', {'fields': ('id', 'data_table', 'source', 'user')}),
        ('File & Format', {'fields': ('file', 'format')}),
        ('Processing', {'fields': ('status', 'row_count', 'error_count', 'log')}),
        ('Timeline', {'fields': ('started_at', 'finished_at', 'created_at')}),
    )


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'data_table', 'format', 'status', 'row_count', 'user', 'created_at']
    list_filter = ['status', 'format', 'created_at']
    search_fields = ['data_table__title', 'export_project__name']
    readonly_fields = ['id', 'file', 'status', 'row_count', 'started_at', 'finished_at', 'created_at']
    fieldsets = (
        ('Job Info', {'fields': ('id', 'export_project', 'data_table', 'user')}),
        ('Export Config', {'fields': ('format', 'filters')}),
        ('Output', {'fields': ('file', 'status', 'row_count')}),
        ('Timeline', {'fields': ('started_at', 'finished_at', 'created_at')}),
    )
