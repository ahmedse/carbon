"""Healthy app serializers."""
from rest_framework import serializers

from .models import ERPSnapshot, LoadoutSheet, RepHealthCard


class ERPSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ERPSnapshot
        fields = [
            'id', 'source_view', 'extract_params', 'row_count',
            'dataset_version_id', 'data_source', 'status', 'error_detail',
            'started_at', 'completed_at', 'triggered_by',
        ]
        read_only_fields = [
            'id', 'row_count', 'dataset_version_id', 'status', 'error_detail',
            'started_at', 'completed_at', 'triggered_by',
        ]


class LoadoutSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoadoutSheet
        fields = [
            'id', 'week_start', 'rep_code', 'rep_name', 'prediction_ref',
            'line_items', 'generated_at', 'generated_by',
        ]
        read_only_fields = ['id', 'generated_at', 'generated_by']


class RepHealthCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepHealthCard
        fields = [
            'id', 'week_start', 'rep_code', 'churn_probability',
            'active_customer_count', 'visit_coverage', 'avg_order_value',
            'ar_overdue_amount', 'prediction_ref', 'generated_at',
        ]
        read_only_fields = ['id', 'generated_at']
