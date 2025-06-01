# File: dataschema/admin.py

from django.contrib import admin
from .models import DataTable, DataField, DataRow, SchemaChangeLog

class DataFieldInline(admin.TabularInline):
    model = DataField
    fk_name = "data_table"
    extra = 0
    fields = ('label', 'name', 'type', 'order', 'required', 'is_active', 'is_archived', 'version')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

class DataRowInline(admin.TabularInline):
    model = DataRow
    extra = 0
    fields = ('id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_archived', 'version')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'version')
    show_change_link = True

@admin.register(DataTable)
class DataTableAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'module', 'version', 'is_archived', 'created_at', 'created_by')
    search_fields = ('title', 'module__name')
    list_filter = ('module', 'is_archived')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'version')
    inlines = [DataFieldInline, DataRowInline]
    ordering = ('-created_at',)

@admin.register(DataField)
class DataFieldAdmin(admin.ModelAdmin):
    list_display = ('id', 'label', 'name', 'type', 'data_table', 'order', 'is_active', 'is_archived', 'version')
    list_filter = ('type', 'is_active', 'is_archived', 'data_table')
    search_fields = ('label', 'name', 'data_table__title')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'version')
    ordering = ('data_table', 'order', 'id')

@admin.register(DataRow)
class DataRowAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_table', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_archived', 'version')
    list_filter = ('data_table', 'is_archived')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'version')
    search_fields = ('data_table__title',)
    ordering = ('-created_at',)

@admin.register(SchemaChangeLog)
class SchemaChangeLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'action', 'data_table', 'data_field', 'user', 'timestamp', 'notes')
    list_filter = ('action', 'data_table', 'data_field', 'user')
    search_fields = ('data_table__title', 'data_field__label', 'user__username', 'notes')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)