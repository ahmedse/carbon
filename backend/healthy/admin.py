from django.contrib import admin

from .models import ERPSnapshot, LoadoutSheet, RepHealthCard


@admin.register(ERPSnapshot)
class ERPSnapshotAdmin(admin.ModelAdmin):
    list_display = ('source_view', 'status', 'row_count', 'started_at', 'completed_at')
    list_filter = ('status', 'source_view')
    search_fields = ('source_view',)
    readonly_fields = ('id', 'started_at')


@admin.register(LoadoutSheet)
class LoadoutSheetAdmin(admin.ModelAdmin):
    list_display = ('week_start', 'rep_code', 'rep_name', 'generated_at')
    list_filter = ('week_start',)
    search_fields = ('rep_code', 'rep_name')
    readonly_fields = ('id', 'generated_at')


@admin.register(RepHealthCard)
class RepHealthCardAdmin(admin.ModelAdmin):
    list_display = ('week_start', 'rep_code', 'churn_probability', 'generated_at')
    list_filter = ('week_start',)
    search_fields = ('rep_code',)
    readonly_fields = ('id', 'generated_at')
