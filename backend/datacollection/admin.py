from django.contrib import admin
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
)

@admin.register(ReadingItemDefinition)
class ReadingItemDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'data_type', 'category', 'required', 'editable')

@admin.register(ReadingTemplate)
class ReadingTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'status', 'created_at', 'updated_at')

@admin.register(ReadingTemplateField)
class ReadingTemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('template', 'field', 'order')

@admin.register(ReadingEntry)
class ReadingEntryAdmin(admin.ModelAdmin):
    list_display = ('template', 'template_version', 'context_id', 'submitted_by', 'submitted_at', 'status')

@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = ('reading_entry', 'reading_item', 'file', 'file_type', 'uploaded_at')