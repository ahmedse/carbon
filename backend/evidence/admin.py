# File: backend/evidence/admin.py
from django.contrib import admin
from .models import Evidence


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_row', 'original_filename', 'file_size', 'uploaded_by', 'uploaded_at', 'is_deleted')
    list_filter = ('is_deleted', 'uploaded_at', 'uploaded_by')
    search_fields = ('original_filename', 'data_row__id')
    readonly_fields = ('file_size', 'mime_type', 'uploaded_at', 'deleted_at', 'deleted_by')
    
    fieldsets = (
        ('File Information', {
            'fields': ('data_row', 'file', 'original_filename', 'file_size', 'mime_type')
        }),
        ('Upload Metadata', {
            'fields': ('uploaded_by', 'uploaded_at')
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Automatically set uploaded_by on creation."""
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
