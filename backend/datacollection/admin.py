from django.contrib import admin
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
    ContextAssignment
)

@admin.register(ReadingItemDefinition)
class ReadingItemDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'data_type', 'category', 'required', 'editable', 'context', 'module')

@admin.register(ReadingTemplate)
class ReadingTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'status', 'created_at', 'updated_at', 'context', 'module')

@admin.register(ReadingTemplateField)
class ReadingTemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('template', 'field', 'order')

@admin.register(ReadingEntry)
class ReadingEntryAdmin(admin.ModelAdmin):
    list_display = ('template', 'template_version', 'item', 'context', 'submitted_by', 'submitted_at', 'status')

@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = ('reading_entry', 'reading_item', 'file', 'file_type', 'uploaded_at', 'context')

@admin.register(ContextAssignment)
class ContextAssignmentAdmin(admin.ModelAdmin):
    list_display = ('context', 'user', 'role')