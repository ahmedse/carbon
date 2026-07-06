# dq/serializers.py
from rest_framework import serializers
from .models import TableProfile, FieldProfile, DQRule, DQResult


class TableProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableProfile
        fields = ['id', 'data_table', 'row_count', 'completeness_pct', 'profiled_at']


class FieldProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldProfile
        fields = ['id', 'data_field', 'row_count', 'null_count', 'distinct_count',
                  'completeness_pct', 'uniqueness_pct', 'min_value', 'max_value',
                  'mean_value', 'top_values', 'profiled_at']


class DQRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DQRule
        fields = ['id', 'scope', 'data_table', 'data_field', 'rule_type',
                  'params', 'severity', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class DQResultSerializer(serializers.ModelSerializer):
    rule_type = serializers.CharField(source='rule.rule_type', read_only=True)

    class Meta:
        model = DQResult
        fields = ['id', 'rule', 'rule_type', 'run_at', 'passed', 'checked_count',
                  'failed_count', 'sample_failures', 'score']
