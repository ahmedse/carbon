"""integrations/turnkey/admin.py — admin registration for the TurnKey Bridge.

The TurnKey API key is only ever shown in ciphertext form (encrypted at rest);
a read-only field shows whether a key is configured.
"""
from django.contrib import admin

from .models import DriftAlert, PredictionRecord, TurnKeyConfig, TurnKeyModelLink


@admin.register(TurnKeyConfig)
class TurnKeyConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url', 'has_api_key', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'base_url')
    readonly_fields = ('api_key_encrypted', 'created_at', 'created_by')

    def has_api_key(self, obj) -> bool:
        return bool(obj.api_key_encrypted)
    has_api_key.boolean = True
    has_api_key.short_description = 'API key configured'


@admin.register(TurnKeyModelLink)
class TurnKeyModelLinkAdmin(admin.ModelAdmin):
    list_display = (
        'turnkey_model_name', 'dataset_version', 'purpose', 'status',
        'turnkey_config', 'created_at',
    )
    list_filter = ('status', 'purpose')
    search_fields = ('turnkey_model_name', 'turnkey_model_id')
    readonly_fields = ('id', 'created_at', 'linked_by')


@admin.register(PredictionRecord)
class PredictionRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'model_link', 'input_data_row', 'input_hash',
                    'feedback_submitted_at', 'created_at')
    list_filter = ('created_at',)
    readonly_fields = ('id', 'created_at')
    search_fields = ('input_hash',)


@admin.register(DriftAlert)
class DriftAlertAdmin(admin.ModelAdmin):
    list_display = ('turnkey_alert_id', 'model_link', 'metric', 'value',
                    'threshold', 'severity', 'dq_job_triggered', 'received_at')
    list_filter = ('severity', 'dq_job_triggered')
    search_fields = ('turnkey_alert_id', 'metric')
    readonly_fields = ('received_at',)
