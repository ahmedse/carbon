from django.contrib import admin
from .models import (
    ReadingItemDefinition,
    ReadingTemplate,
    ReadingTemplateField,
    ReadingEntry,
    EvidenceFile,
    ContextAssignment
)

class TenantFilterAdminMixin:
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant'):
            if hasattr(self.model, 'project'):
                return qs.filter(project__tenant=request.user.tenant)
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Restrict project/module to current user's tenant
        if db_field.name == "project" and hasattr(request.user, 'tenant'):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                tenant=request.user.tenant
            )
        if db_field.name == "module" and hasattr(request.user, 'tenant'):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                project__tenant=request.user.tenant
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(ReadingItemDefinition)
class ReadingItemDefinitionAdmin(TenantFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        'name', 'data_type', 'category', 'required', 'editable', 'project'
    )
    list_filter = ('project', 'data_type', 'required', 'editable')
    search_fields = ('name', 'description', 'category', 'tags')

@admin.register(ReadingTemplate)
class ReadingTemplateAdmin(TenantFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        'name', 'version', 'status', 'created_at', 'updated_at', 'project', 'module'
    )
    list_filter = ('project', 'module', 'status')
    search_fields = ('name', 'description')

@admin.register(ReadingTemplateField)
class ReadingTemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('template', 'field', 'order')
    list_filter = ('template',)
    search_fields = ('template__name', 'field__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(request.user, 'tenant'):
            return qs.filter(template__project__tenant=request.user.tenant)
        return qs

@admin.register(ReadingEntry)
class ReadingEntryAdmin(TenantFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        'template', 'template_version', 'item', 'project', 'submitted_by', 'submitted_at', 'status'
    )
    list_filter = ('project', 'template', 'item', 'status')
    search_fields = ('id', 'template__name', 'item__name', 'submitted_by__username')

@admin.register(EvidenceFile)
class EvidenceFileAdmin(TenantFilterAdminMixin, admin.ModelAdmin):
    list_display = (
        'reading_entry', 'reading_item', 'file', 'file_type', 'uploaded_at', 'project'
    )
    list_filter = ('project', 'file_type')
    search_fields = ('reading_entry__id', 'reading_item__name', 'file')

@admin.register(ContextAssignment)
class ContextAssignmentAdmin(TenantFilterAdminMixin, admin.ModelAdmin):
    list_display = ('project', 'user', 'role')
    list_filter = ('project', 'role', 'user')
    search_fields = ('project__id', 'user__username')