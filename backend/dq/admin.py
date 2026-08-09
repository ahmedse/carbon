# dq/admin.py
from django.contrib import admin
from .models import TableProfile, FieldProfile, DQRule, DQResult, DQProfileConfig
from .services import profile_table


@admin.register(DQProfileConfig)
class DQProfileConfigAdmin(admin.ModelAdmin):
    """Singleton config for profiling — only one instance allowed."""
    fieldsets = (
        ('Automated Profiling', {'fields': ('auto_profile_enabled', 'sample_size')}),
        ('Freshness', {'fields': ('freshness_threshold_hours', 'volume_anomaly_pct')}),
    )


@admin.register(TableProfile)
class TableProfileAdmin(admin.ModelAdmin):
    list_display = ('data_table', 'row_count', 'completeness_pct', 'profiled_at')
    list_filter = ('profiled_at',)
    readonly_fields = [f.name for f in TableProfile._meta.fields]
    actions = ['profile_selected_tables']
    search_fields = ['data_table__name']

    @admin.action(description='Profile selected tables')
    def profile_selected_tables(self, request, queryset):
        count = 0
        for tp in queryset:
            profile_table(tp.data_table_id)
            count += 1
        self.message_user(request, f'{count} table(s) re-profiled.')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FieldProfile)
class FieldProfileAdmin(admin.ModelAdmin):
    list_display = ('data_field', 'row_count', 'null_count', 'completeness_pct',
                    'uniqueness_pct', 'profiled_at')
    list_filter = ('profiled_at',)
    search_fields = ['data_field__name']
    readonly_fields = [f.name for f in FieldProfile._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(DQRule)
class DQRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'rule_type', 'scope', 'severity', 'is_active', 'created_at')
    list_filter = ('rule_type', 'severity', 'is_active', 'scope')


@admin.register(DQResult)
class DQResultAdmin(admin.ModelAdmin):
    list_display = ('rule', 'passed', 'checked_count', 'failed_count', 'run_at')
    list_filter = ('passed', 'run_at')
    readonly_fields = ['run_at', 'passed', 'score']
