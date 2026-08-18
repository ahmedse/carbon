from django.contrib import admin

from .models import (
    DataContract, DataContractViolation, Dataset, DatasetAccessPolicy,
    DatasetVersion,
)


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'module', 'status', 'classification', 'updated_at')
    list_filter = ('status', 'classification', 'module')
    search_fields = ('name', 'slug', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'version_number', 'status', 'health_score',
                    'row_count', 'created_at')
    list_filter = ('status',)
    search_fields = ('dataset__name',)
    readonly_fields = ('id', 'created_at')


@admin.register(DataContract)
class DataContractAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'min_health_score', 'freshness_hours', 'is_active')
    list_filter = ('is_active',)


@admin.register(DataContractViolation)
class DataContractViolationAdmin(admin.ModelAdmin):
    list_display = ('contract', 'dataset_version', 'violation_type', 'detected_at')
    list_filter = ('violation_type',)


@admin.register(DatasetAccessPolicy)
class DatasetAccessPolicyAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'user', 'group', 'can_view', 'can_ingest', 'can_approve')
    list_filter = ('can_view', 'can_ingest', 'can_approve')
