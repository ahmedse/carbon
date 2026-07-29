# File: emissions/serializers.py
# Serializers for Emission Factor Calculator API

from rest_framework import serializers
from .models import ReportingPeriod, EmissionFactor, GWP, Calculation, CalculationRule, ReportConfig, VerificationRecord, SBTiTarget, CalculationAudit


class ReportingPeriodSerializer(serializers.ModelSerializer):
    """Serializer for reporting periods."""
    duration_days = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ReportingPeriod
        fields = [
            'id', 'name',
            'start_date', 'end_date', 'period_type', 'status',
            'description', 'is_baseline', 'duration_days', 'is_active',
            'submitted_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'status', 'submitted_at']


class VerificationRecordSerializer(serializers.ModelSerializer):
    verifier_name = serializers.CharField(source='verifier.username', read_only=True)

    class Meta:
        model = VerificationRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'verifier_name']


class EmissionFactorSerializer(serializers.ModelSerializer):
    """Serializer for emission factors."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    
    class Meta:
        model = EmissionFactor
        fields = [
            'id', 'name', 'code', 'category', 'category_display', 'subcategory',
            'scope', 'scope_display', 'factor_value', 'factor_unit', 'activity_unit',
            'co2_factor', 'ch4_factor', 'n2o_factor',
            'country', 'country_code', 'region',
            'source', 'source_url', 'valid_from', 'valid_to',
            'notes', 'is_active', 'tags',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class EmissionFactorSummarySerializer(serializers.ModelSerializer):
    """Minimal serializer for emission factor dropdowns."""
    
    class Meta:
        model = EmissionFactor
        fields = ['id', 'name', 'code', 'category', 'scope', 'factor_value', 'activity_unit']


class GWPSerializer(serializers.ModelSerializer):
    """Serializer for Global Warming Potentials."""
    
    class Meta:
        model = GWP
        fields = [
            'id', 'gas_name', 'gas_formula',
            'gwp_ar5_100yr', 'gwp_ar6_100yr', 'gwp_ar5_20yr', 'gwp_ar6_20yr',
            'cas_number', 'notes'
        ]


class CalculationSerializer(serializers.ModelSerializer):
    """Serializer for emission calculations."""
    emission_factor_name = serializers.CharField(source='emission_factor.name', read_only=True)
    emission_factor_code = serializers.CharField(source='emission_factor.code', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    reporting_period_name = serializers.CharField(source='reporting_period.name', read_only=True)
    
    class Meta:
        model = Calculation
        fields = [
            'id', 'data_row', 'module', 'module_name',
            'emission_factor', 'emission_factor_name', 'emission_factor_code',
            'activity_value', 'activity_unit', 
            'co2e_kg', 'co2_kg', 'ch4_kg', 'n2o_kg',
            'scope', 'scope_display', 'category',
            'reporting_period', 'reporting_period_name',
            'reporting_year', 'reporting_month', 'activity_date',
            'calculated_at', 'calculated_by', 'calculation_method'
        ]
        read_only_fields = ['calculated_at']


class CalculationRuleSerializer(serializers.ModelSerializer):
    """Serializer for calculation rules."""
    data_table_name = serializers.CharField(source='data_table.title', read_only=True)
    activity_field_name = serializers.CharField(source='activity_field.label', read_only=True)
    emission_factor_name = serializers.CharField(source='emission_factor.name', read_only=True)
    emission_factor_code = serializers.CharField(source='emission_factor.code', read_only=True)
    
    class Meta:
        model = CalculationRule
        fields = [
            'id', 'name', 'description',
            'data_table', 'data_table_name',
            'activity_field', 'activity_field_name',
            'date_field', 'output_field',
            'emission_factor', 'emission_factor_name', 'emission_factor_code',
            'factor_selector_field', 'factor_selector_mapping',
            'rule_type', 'unit_conversion_factor', 'custom_formula',
            'is_active', 'auto_calculate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


# ============= Dashboard Serializers =============

class ScopeSummarySerializer(serializers.Serializer):
    """Scope emission summary."""
    scope = serializers.IntegerField()
    scope_name = serializers.CharField()
    co2e_tonnes = serializers.DecimalField(max_digits=20, decimal_places=2)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)


class CategorySummarySerializer(serializers.Serializer):
    """Category emission summary."""
    category = serializers.CharField()
    category_name = serializers.CharField()
    scope = serializers.IntegerField()
    co2e_tonnes = serializers.DecimalField(max_digits=20, decimal_places=2)
    count = serializers.IntegerField()


class MonthlyTrendSerializer(serializers.Serializer):
    """Monthly emission trend."""
    month = serializers.CharField()
    month_name = serializers.CharField()
    scope1 = serializers.DecimalField(max_digits=20, decimal_places=2)
    scope2 = serializers.DecimalField(max_digits=20, decimal_places=2)
    scope3 = serializers.DecimalField(max_digits=20, decimal_places=2)
    total = serializers.DecimalField(max_digits=20, decimal_places=2)


class DashboardSummarySerializer(serializers.Serializer):
    """Complete dashboard summary."""
    reporting_period = ReportingPeriodSerializer()
    total_co2e_tonnes = serializers.DecimalField(max_digits=20, decimal_places=2)
    scope_breakdown = ScopeSummarySerializer(many=True)
    category_breakdown = CategorySummarySerializer(many=True)
    monthly_trend = MonthlyTrendSerializer(many=True)
    data_quality_score = serializers.IntegerField()
    calculation_count = serializers.IntegerField()
    last_updated = serializers.DateTimeField()


# ============= Report Serializers =============

class EmissionReportRowSerializer(serializers.Serializer):
    """Single row in an emission report."""
    module = serializers.CharField()
    table = serializers.CharField()
    category = serializers.CharField()
    scope = serializers.IntegerField()
    activity_description = serializers.CharField()
    activity_value = serializers.DecimalField(max_digits=20, decimal_places=2)
    activity_unit = serializers.CharField()
    emission_factor = serializers.CharField()
    co2e_kg = serializers.DecimalField(max_digits=20, decimal_places=2)
    co2e_tonnes = serializers.DecimalField(max_digits=20, decimal_places=4)


class EmissionReportSerializer(serializers.Serializer):
    """Complete emission report."""
    title = serializers.CharField()
    reporting_period = ReportingPeriodSerializer()
    generated_at = serializers.DateTimeField()
    summary = serializers.DictField()
    scope_details = serializers.ListField()
    rows = EmissionReportRowSerializer(many=True)


class ReportConfigSerializer(serializers.ModelSerializer):
    """Serializer for saved report configurations."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    reporting_period_name = serializers.CharField(source='reporting_period.name', read_only=True, allow_null=True)
    org_unit_name = serializers.CharField(source='org_unit.name', read_only=True, allow_null=True)
    
    class Meta:
        model = ReportConfig
        fields = [
            'id', 'name', 'created_by', 'created_by_username',
            'reporting_period', 'reporting_period_name',
            'custom_start', 'custom_end',
            'org_unit', 'org_unit_name',
            'ghg_scopes', 'categories',
            'output_format', 'grouping',
            'include_dq_status', 'include_unverified',
            'last_run_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'last_run_at', 'created_at', 'updated_at']


# ============= Console Serializers =============

class ActivePeriodConsoleSerializer(serializers.Serializer):
    """Active reporting period for the console."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = serializers.CharField()
    days_remaining = serializers.IntegerField()


class StatsConsoleSerializer(serializers.Serializer):
    """Aggregated stats for the console."""
    total_modules = serializers.IntegerField()
    total_tables = serializers.IntegerField()
    total_calculations = serializers.IntegerField()
    avg_quality_score = serializers.FloatField()
    total_emissions_tonnes = serializers.FloatField()


class AlertConsoleSerializer(serializers.Serializer):
    """Alert item for the console."""
    type = serializers.ChoiceField(choices=['dq', 'pending_submission'])
    module_name = serializers.CharField(allow_null=True)
    message = serializers.CharField()
    # DQ-specific fields
    score = serializers.IntegerField(required=False, allow_null=True)
    threshold = serializers.IntegerField(required=False, allow_null=True)
    # Pending submission-specific fields
    module_id = serializers.IntegerField(required=False, allow_null=True)
    pending_rows = serializers.IntegerField(required=False, allow_null=True)


class RecentActivityConsoleSerializer(serializers.Serializer):
    """Recent activity item for the console."""
    id = serializers.IntegerField()
    action = serializers.CharField()
    module_name = serializers.CharField(allow_null=True)
    timestamp = serializers.DateTimeField(allow_null=True)
    detail = serializers.CharField(allow_null=True)


class SBTiTargetSerializer(serializers.ModelSerializer):
    org_unit_name = serializers.CharField(source='org_unit.name', read_only=True)

    class Meta:
        model = SBTiTarget
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'org_unit_name']


class CalculationAuditSerializer(serializers.ModelSerializer):
    triggered_by_name = serializers.CharField(source='triggered_by.username', read_only=True)
    rule_name = serializers.CharField(source='calculation_rule.name', read_only=True)
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    period_name = serializers.CharField(source='reporting_period.name', read_only=True)

    class Meta:
        model = CalculationAudit
        fields = '__all__'
        read_only_fields = ['triggered_at', 'triggered_by_name', 'rule_name', 'table_name', 'period_name']


class ConsoleResponseSerializer(serializers.Serializer):
    """Complete console response."""
    active_period = ActivePeriodConsoleSerializer(allow_null=True)
    stats = StatsConsoleSerializer()
    alerts = AlertConsoleSerializer(many=True)
    recent_activity = RecentActivityConsoleSerializer(many=True)
