# dq/serializers.py
from rest_framework import serializers
from .models import TableProfile, FieldProfile, DQRule, DQResult, DQProfileConfig
from .models import FreshnessCheck, SchemaSnapshot, SchemaChange, RuleTag, RuleFieldAssignment


class TableProfileSerializer(serializers.ModelSerializer):
    """Serializer for table data quality profiles."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    
    class Meta:
        model = TableProfile
        fields = [
            'id', 'data_table', 'table_name', 'row_count',
            'completeness_pct', 'null_counts', 'distinct_counts',
            'min_values', 'max_values', 'mean_values', 'profiled_at'
        ]
        read_only_fields = fields


DQProfileConfigSerializer = type('DQProfileConfigSerializer', (serializers.ModelSerializer,), {
    'Meta': type('Meta', (), {
        'model': DQProfileConfig,
        'fields': ['id', 'freshness_threshold_hours', 'volume_anomaly_pct'],
    })
})


class FieldProfileSerializer(serializers.ModelSerializer):
    """Serializer for field data quality profiles."""
    field_name = serializers.CharField(source='data_field.name', read_only=True)
    
    class Meta:
        model = FieldProfile
        fields = [
            'id', 'data_field', 'field_name', 'row_count', 'null_count', 
            'distinct_count', 'completeness_pct', 'uniqueness_pct', 
            'min_value', 'max_value', 'mean_value', 'top_values', 'profiled_at'
        ]
        read_only_fields = ['id', 'profiled_at']


class RuleTagSerializer(serializers.ModelSerializer):
    """Simple serializer for rule categorization tags."""
    class Meta:
        model = RuleTag
        fields = ['id', 'name', 'color', 'description']


class RuleFieldAssignmentSerializer(serializers.ModelSerializer):
    """Read-only serializer for field assignments embedded in rule responses."""
    field_name = serializers.CharField(source='data_field.name', read_only=True, allow_null=True)
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = RuleFieldAssignment
        fields = ['id', 'data_field', 'field_name', 'data_table', 'table_name']
        read_only_fields = ['id']


class DQRuleSerializer(serializers.ModelSerializer):
    """Serializer for data quality rules with M2M field assignments + tags.

    Write: provide `tag_ids` (list of int) and `field_assignments` (list of
    {data_field, data_table}). Read: returns nested `tags` and `field_assignments`.
    """
    tags = RuleTagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
        help_text='List of RuleTag IDs to assign'
    )
    field_assignments = RuleFieldAssignmentSerializer(many=True, read_only=True)
    field_assignments_write = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False,
        help_text='List of {data_table (required), data_field (optional, int|null)} dicts'
    )
    results_count = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )

    class Meta:
        model = DQRule
        fields = [
            'id', 'rule_level', 'rule_type', 'name', 'description',
            'params', 'severity', 'is_active', 'tags', 'tag_ids',
            'field_assignments', 'field_assignments_write', 'results_count', 'is_locked',
            'dimension', 'definition', 'version', 'archived',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'results_count', 'is_locked', 'version',
                           'created_by', 'created_at', 'updated_at']

    def get_results_count(self, obj):
        return obj.results.count()

    def get_is_locked(self, obj):
        """Rule is locked if it has been executed at least once (has DQResults)."""
        return obj.results.exists()

    def validate_rule_type(self, value):
        ALLOWED = ['not_null', 'unique', 'allowed_values', 'range', 'regex',
                   'reference_integrity', 'threshold', 'nl_check']
        if value not in ALLOWED:
            raise serializers.ValidationError(f"rule_type must be one of {ALLOWED}")
        return value

    THRESHOLD_OPERATORS = {'gte', 'gt', 'lte', 'lt', 'eq', 'neq'}

    def validate(self, data):
        rule_type = data.get('rule_type')
        if rule_type == 'threshold':
            params = data.get('params', {})
            if not isinstance(params, dict):
                raise serializers.ValidationError({"params": "params must be a JSON object"})
            operator = params.get('operator', 'gte')
            if operator not in self.THRESHOLD_OPERATORS:
                raise serializers.ValidationError({
                    "params": f"operator must be one of {sorted(self.THRESHOLD_OPERATORS)}, got '{operator}'"
                })
            if 'value' not in params:
                raise serializers.ValidationError({"params": "value is required for threshold rules"})
            try:
                float(params['value'])
            except (TypeError, ValueError):
                raise serializers.ValidationError({
                    "params": f"value must be numeric, got '{params['value']}'"
                })
        return data

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        field_assignments_data = validated_data.pop('field_assignments_write', [])
        rule = super().create(validated_data)
        if tag_ids:
            rule.tags.set(tag_ids)
        for assn in field_assignments_data:
            RuleFieldAssignment.objects.create(
                rule=rule,
                data_table_id=assn['data_table'],
                data_field_id=assn.get('data_field'),
            )
        return rule

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        field_assignments_data = validated_data.pop('field_assignments_write', None)
        rule = super().update(instance, validated_data)
        if tag_ids is not None:
            rule.tags.set(tag_ids)
        if field_assignments_data is not None:
            # Replace all existing assignments
            instance.field_assignments.all().delete()
            for assn in field_assignments_data:
                RuleFieldAssignment.objects.create(
                    rule=instance,
                    data_table_id=assn['data_table'],
                    data_field_id=assn.get('data_field'),
                )
        return rule


class DQResultSerializer(serializers.ModelSerializer):
    """Serializer for data quality rule execution results."""
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_type = serializers.CharField(source='rule.rule_type', read_only=True)

    class Meta:
        model = DQResult
        fields = [
            'id', 'rule', 'rule_name', 'rule_type', 'run_at', 'passed', 
            'checked_count', 'failed_count', 'sample_failures', 'score'
        ]
        read_only_fields = ['id', 'run_at']


class DQSuggestResponseSerializer(serializers.Serializer):
    """Serializer for DQ suggest API response."""
    table_id = serializers.IntegerField()
    status = serializers.CharField()
    suggestions = serializers.ListField(child=serializers.DictField())
    error = serializers.DictField(required=False)


# ── Phase 1.8: Freshness & Schema Monitoring serializers ──────────────

class FreshnessCheckSerializer(serializers.ModelSerializer):
    """Serializer for per-table freshness checks."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = FreshnessCheck
        fields = [
            'id', 'data_table', 'table_name', 'expected_max_age_hours',
            'last_data_timestamp', 'is_fresh', 'checked_at',
        ]
        read_only_fields = ['id', 'checked_at']


class SchemaSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for table schema snapshots."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    column_count = serializers.SerializerMethodField()

    class Meta:
        model = SchemaSnapshot
        fields = [
            'id', 'data_table', 'table_name', 'column_schema',
            'row_count', 'snapshot_at', 'column_count',
        ]
        read_only_fields = ['id', 'snapshot_at']

    def get_column_count(self, obj):
        if isinstance(obj.column_schema, dict):
            return len(obj.column_schema)
        return 0


class SchemaChangeSerializer(serializers.ModelSerializer):
    """Serializer for detected schema changes between snapshots."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)

    class Meta:
        model = SchemaChange
        fields = [
            'id', 'data_table', 'table_name', 'snapshot_from', 'snapshot_to',
            'change_type', 'field_name', 'old_definition', 'new_definition',
            'detected_at',
        ]
        read_only_fields = ['id', 'detected_at']
