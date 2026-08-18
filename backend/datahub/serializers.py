"""
datahub/serializers.py — thin DRF serializers for the Dataset Hub.

Validation at the serializer boundary; business logic lives in services/ingest.
"""
from rest_framework import serializers

from .models import (
    Dataset, DatasetVersion, DataContract, DataContractViolation,
    DatasetAccessPolicy,
)


class DatasetVersionListSerializer(serializers.ModelSerializer):
    """Lean version row for list views — no heavy JSON payloads."""

    class Meta:
        model = DatasetVersion
        fields = [
            'id', 'version_number', 'row_count', 'health_score',
            'dq_job_id', 'status', 'approved_at', 'rejection_reason',
            'created_at', 'created_by',
        ]
        read_only_fields = fields


class DatasetVersionSerializer(serializers.ModelSerializer):
    """Full version detail — includes schema snapshot + health breakdown."""

    class Meta:
        model = DatasetVersion
        fields = [
            'id', 'dataset', 'version_number', 'data_table',
            'row_count', 'schema_snapshot', 'health_score', 'health_detail',
            'dq_job_id', 'lineage', 'status', 'approved_by', 'approved_at',
            'rejection_reason', 'created_at', 'created_by',
        ]
        read_only_fields = [
            'id', 'dataset', 'version_number', 'data_table', 'row_count',
            'schema_snapshot', 'health_score', 'health_detail', 'dq_job_id',
            'lineage', 'status', 'approved_by', 'approved_at',
            'rejection_reason', 'created_at', 'created_by',
        ]


class DatasetListSerializer(serializers.ModelSerializer):
    """Lean dataset row for the catalog grid."""
    current_version = DatasetVersionListSerializer(read_only=True)

    class Meta:
        model = Dataset
        fields = [
            'id', 'name', 'slug', 'description', 'module', 'domain',
            'classification', 'status', 'owner', 'current_version',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'current_version']


class DatasetSerializer(serializers.ModelSerializer):
    """Full dataset detail / create / update."""
    current_version = DatasetVersionSerializer(read_only=True)

    class Meta:
        model = Dataset
        fields = [
            'id', 'name', 'slug', 'description', 'module', 'domain',
            'classification', 'status', 'owner', 'source', 'current_version',
            'tags', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['id', 'current_version', 'created_at', 'updated_at', 'created_by']

    def validate_slug(self, value):
        if not value:
            # slug is required by the model; let the model's own validation catch empties
            return value
        return value


class DataContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataContract
        fields = [
            'id', 'dataset', 'required_fields', 'min_completeness',
            'min_validity', 'min_health_score', 'freshness_hours',
            'consumer_apps', 'is_active', 'created_at', 'updated_at',
            'created_by',
        ]
        read_only_fields = ['id', 'dataset', 'created_at', 'updated_at', 'created_by']


class DataContractViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataContractViolation
        fields = [
            'id', 'contract', 'dataset_version', 'violation_type',
            'detail', 'detected_at', 'resolved_at',
        ]
        read_only_fields = fields


class DatasetAccessPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetAccessPolicy
        fields = [
            'id', 'dataset', 'user', 'group', 'can_view', 'can_ingest',
            'can_approve', 'granted_by', 'granted_at', 'note',
        ]
        read_only_fields = ['id', 'dataset', 'granted_by', 'granted_at']
