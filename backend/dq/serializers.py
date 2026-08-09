# dq/serializers.py
from rest_framework import serializers
from .models import TableProfile, FieldProfile, DQRule, DQResult


class TableProfileSerializer(serializers.ModelSerializer):
    """Serializer for table data quality profiles."""
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    
    class Meta:
        model = TableProfile
        fields = [
            'id', 'data_table', 'table_name', 'row_count', 
            'completeness_pct', 'profiled_at'
        ]
        read_only_fields = ['id', 'profiled_at']


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


class DQRuleSerializer(serializers.ModelSerializer):
    """Serializer for data quality rules with validation."""
    results_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.get_full_name', read_only=True, allow_null=True
    )
    
    class Meta:
        model = DQRule
        fields = [
            'id', 'scope', 'data_table', 'data_field', 'rule_type', 'name',
            'params', 'severity', 'is_active', 'created_by', 'created_by_name',
            'results_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'results_count', 'created_by', 'created_at', 'updated_at']

    def get_results_count(self, obj):
        """Return count of results for this rule."""
        return obj.results.count()

    def validate_rule_type(self, value):
        """Validate rule_type is one of allowed types."""
        ALLOWED = ['not_null', 'unique', 'allowed_values', 'range', 'regex', 'reference_integrity', 'threshold', 'custom']
        if value not in ALLOWED:
            raise serializers.ValidationError(
                f"rule_type must be one of {ALLOWED}"
            )
        return value

    THRESHOLD_OPERATORS = {'gte', 'gt', 'lte', 'lt', 'eq', 'neq'}

    def validate(self, data):
        """Ensure either data_table or data_field is provided, but not both."""
        scope = data.get('scope')
        data_table = data.get('data_table')
        data_field = data.get('data_field')
        
        if scope == 'table' and not data_table:
            raise serializers.ValidationError("data_table is required for table-level rules")
        if scope == 'field' and not data_field:
            raise serializers.ValidationError("data_field is required for field-level rules")
        
        # Validate threshold rule params
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
