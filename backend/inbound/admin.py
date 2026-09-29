from django.contrib import admin

from .models import InboundBatch, InboundTemplate


@admin.register(InboundBatch)
class InboundBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'target_key', 'status', 'original_filename', 'row_count', 'updated_at')
    list_filter = ('kind', 'status')


@admin.register(InboundTemplate)
class InboundTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'target_key', 'kind')
