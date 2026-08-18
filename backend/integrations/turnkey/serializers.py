"""
integrations/turnkey/serializers.py — thin DRF serializers for the TurnKey Bridge.

Never expose the encrypted key ciphertext — configs serialize only a
``has_api_key`` boolean; the plaintext key is written via ``set_api_key()``.
"""
from rest_framework import serializers

from datahub.models import DatasetVersion
from .models import DriftAlert, PredictionRecord, TurnKeyConfig, TurnKeyModelLink


class TurnKeyConfigSerializer(serializers.ModelSerializer):
    has_api_key = serializers.SerializerMethodField()

    class Meta:
        model = TurnKeyConfig
        fields = [
            'id', 'name', 'base_url', 'has_api_key', 'is_active',
            'created_at', 'created_by',
        ]
        read_only_fields = ['id', 'has_api_key', 'created_at', 'created_by']

    def get_has_api_key(self, obj) -> bool:
        return bool(obj.api_key_encrypted)


class TurnKeyConfigCreateSerializer(serializers.ModelSerializer):
    """Write serializer — accepts the plaintext api_key and encrypts it."""
    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False,
    )

    class Meta:
        model = TurnKeyConfig
        fields = ['id', 'name', 'base_url', 'api_key', 'is_active',
                  'created_at', 'created_by']
        read_only_fields = ['id', 'created_at', 'created_by']

    def create(self, validated_data):
        api_key = validated_data.pop('api_key', '')
        config = TurnKeyConfig(**validated_data)
        config.set_api_key(api_key)
        config.save()
        return config


class TurnKeyModelLinkSerializer(serializers.ModelSerializer):
    # TurnKeyConfig.pk is an auto int; DatasetVersion.pk is a UUID. Use
    # PrimaryKeyRelatedField so both serialize/accept their natural pk type.
    dataset_version = serializers.PrimaryKeyRelatedField(
        queryset=DatasetVersion.objects.all(),
    )
    turnkey_config = serializers.PrimaryKeyRelatedField(
        queryset=TurnKeyConfig.objects.all(),
    )

    class Meta:
        model = TurnKeyModelLink
        fields = [
            'id', 'dataset_version', 'turnkey_config', 'turnkey_model_id',
            'turnkey_model_name', 'turnkey_version_id', 'purpose', 'status',
            'error_detail', 'created_at', 'linked_by',
        ]
        read_only_fields = [
            'id', 'turnkey_model_id', 'turnkey_model_name', 'turnkey_version_id',
            'status', 'error_detail', 'created_at', 'linked_by',
        ]


class PredictionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionRecord
        fields = [
            'id', 'model_link', 'input_data_row', 'input_hash', 'prediction',
            'actual', 'feedback_submitted_at', 'feedback_by', 'created_at',
        ]
        read_only_fields = fields


class DriftAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriftAlert
        fields = [
            'id', 'model_link', 'turnkey_alert_id', 'metric', 'value',
            'threshold', 'severity', 'dq_job_triggered', 'received_at',
            'acknowledged_at', 'acknowledged_by',
        ]
        read_only_fields = fields


class PredictionFeedbackSerializer(serializers.Serializer):
    """Body for POST .../predictions/{id}/feedback/ — the actual outcome."""
    actual = serializers.JSONField(required=True)
