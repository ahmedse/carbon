# File: emissions/serializers.py
# Serializers for Emission Factor Calculator API

from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum
from .models import ReportingPeriod, EmissionFactor, GWP, Calculation, CalculationRule, ReportConfig, VerificationRecord, SBTiTarget, CalculationAudit, ExportAudit, OrganizationalBoundary, BaseYear, RecalculationTrigger


class ReportingPeriodSerializer(serializers.ModelSerializer):
    """Serializer for reporting periods."""
    duration_days = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    organizational_boundary_name = serializers.CharField(
        source='organizational_boundary.name', read_only=True
    )
    
    class Meta:
        model = ReportingPeriod
        fields = [
            'id', 'name',
            'start_date', 'end_date', 'period_type', 'status',
            'description', 'is_baseline',
            'organizational_boundary', 'organizational_boundary_name',
            'duration_days', 'is_active',
            'submitted_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'status', 'submitted_at']


class VerificationRecordSerializer(serializers.ModelSerializer):
    verifier_name = serializers.CharField(source='verifier.username', read_only=True)
    period_name = serializers.CharField(source='reporting_period.name', read_only=True)
    period_status = serializers.CharField(source='reporting_period.status', read_only=True)
    period_start_date = serializers.DateField(source='reporting_period.start_date', read_only=True)
    period_end_date = serializers.DateField(source='reporting_period.end_date', read_only=True)
    period_label = serializers.SerializerMethodField(read_only=True)
    total_co2e_tonnes = serializers.SerializerMethodField(read_only=True)
    scope_summary = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VerificationRecord
        fields = '__all__'
        read_only_fields = [
            'created_at', 'verifier_name', 'period_name', 'period_status',
            'period_start_date', 'period_end_date', 'period_label',
            'total_co2e_tonnes', 'scope_summary',
        ]

    def get_period_label(self, obj):
        return f"{obj.reporting_period.name} ({obj.reporting_period.start_date} – {obj.reporting_period.end_date})"

    def get_total_co2e_tonnes(self, obj):
        from .models import Calculation
        total = Calculation.objects.filter(
            reporting_period=obj.reporting_period
        ).aggregate(total=Sum('co2e_kg'))['total']
        if total is None:
            return None
        return round(total / 1000, 2)

    def get_scope_summary(self, obj):
        from .models import Calculation
        scopes = Calculation.objects.filter(
            reporting_period=obj.reporting_period
        ).values('scope').annotate(total_kg=Sum('co2e_kg'))
        return {
            s['scope']: round((s['total_kg'] or 0) / 1000, 2)
            for s in scopes
        }


class EmissionFactorSerializer(serializers.ModelSerializer):
    """Serializer for emission factors."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)

    # Numeric gate — all factor values rounded to 5 decimal places on output
    # (and validated to max 5 decimals on input). Data max precision is 5,
    # so this loses nothing while trimming noise like 0.3500000000.
    factor_value = serializers.DecimalField(max_digits=20, decimal_places=5)
    co2_factor = serializers.DecimalField(
        max_digits=20, decimal_places=5, allow_null=True, required=False
    )
    ch4_factor = serializers.DecimalField(
        max_digits=20, decimal_places=5, allow_null=True, required=False
    )
    n2o_factor = serializers.DecimalField(
        max_digits=20, decimal_places=5, allow_null=True, required=False
    )

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
    factor_value = serializers.DecimalField(max_digits=20, decimal_places=5)

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
    factor_name = serializers.SerializerMethodField()
    factor_code = serializers.SerializerMethodField()
    data_row_label = serializers.SerializerMethodField()
    data_table_name = serializers.SerializerMethodField()
    quality_score = serializers.IntegerField(read_only=True)
    data_quality_tier = serializers.IntegerField(read_only=True)

    def get_factor_name(self, obj):
        return obj.emission_factor.name if obj.emission_factor else None

    def get_factor_code(self, obj):
        return obj.emission_factor.code if obj.emission_factor else None

    def get_data_row_label(self, obj):
        return f"Row #{obj.data_row_id}"

    def get_data_table_name(self, obj):
        if obj.emission_factor:
            rule = obj.emission_factor.calculation_rules.first()
            if rule and rule.data_table:
                return rule.data_table.name or rule.data_table.title
        return None

    class Meta:
        model = Calculation
        fields = [
            'id', 'data_row', 'module', 'module_name',
            'emission_factor', 'emission_factor_name', 'emission_factor_code',
            'factor_name', 'factor_code',
            'data_row_label', 'data_table_name',
            'activity_value', 'activity_unit', 
            'co2e_kg', 'co2_kg', 'ch4_kg', 'n2o_kg',
            'scope', 'scope_display', 'category',
            'reporting_period', 'reporting_period_name',
            'reporting_year', 'reporting_month', 'activity_date',
            'calculated_at', 'calculated_by', 'calculation_method',
            'scope2_method', 'emission_factor_snapshot', 'factor_applied_at',
            'is_stale', 'quality_score', 'data_quality_tier',
        ]
        read_only_fields = ['calculated_at', 'quality_score', 'data_quality_tier']


class CalculationRuleSerializer(serializers.ModelSerializer):
    """Serializer for calculation rules."""
    data_table_name = serializers.CharField(source='data_table.title', read_only=True)
    activity_field_name = serializers.CharField(source='activity_field.label', read_only=True)
    emission_factor_name = serializers.CharField(source='emission_factor.name', read_only=True)
    emission_factor_code = serializers.CharField(source='emission_factor.code', read_only=True)
    last_executed_at = serializers.SerializerMethodField()

    def get_last_executed_at(self, obj):
        latest_audit = obj.calculationaudit_set.order_by('-triggered_at').first()
        if latest_audit:
            return latest_audit.triggered_at
        return None

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
            'scope2_calculation_method', 'data_quality_tier',
            'last_executed_at',
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
    progress = serializers.SerializerMethodField()

    def get_progress(self, obj):
        """Return current-year emissions for this target's scope + org_unit."""
        from decimal import Decimal

        scopes = obj.scope.replace('+', ',').split(',')
        year = timezone.now().year

        actual = Calculation.objects.filter(
            module__org_unit_id=obj.org_unit_id,
            reporting_year=year,
            scope__in=scopes,
        ).aggregate(total=Sum('co2e_kg'))['total'] or Decimal('0')

        return {
            'current_year': year,
            'current_emissions_tco2e': float(actual),
        }

    class Meta:
        model = SBTiTarget
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'org_unit_name', 'progress']


class CalculationAuditSerializer(serializers.ModelSerializer):
    triggered_by_name = serializers.CharField(source='triggered_by.username', read_only=True)
    rule_name = serializers.CharField(source='calculation_rule.name', read_only=True)
    table_name = serializers.CharField(source='data_table.name', read_only=True)
    period_name = serializers.CharField(source='reporting_period.name', read_only=True)

    class Meta:
        model = CalculationAudit
        fields = '__all__'
        read_only_fields = ['triggered_at', 'triggered_by_name', 'rule_name', 'table_name', 'period_name']


class ExportAuditSerializer(serializers.ModelSerializer):
    """E3-1: Audit trail for report exports."""
    exported_by_name = serializers.CharField(source='exported_by.username', read_only=True)

    class Meta:
        model = ExportAudit
        fields = '__all__'
        read_only_fields = ['exported_at', 'exported_by_name']


class ConsoleResponseSerializer(serializers.Serializer):
    """Complete console response."""
    active_period = ActivePeriodConsoleSerializer(allow_null=True)
    stats = StatsConsoleSerializer()
    alerts = AlertConsoleSerializer(many=True)
    recent_activity = RecentActivityConsoleSerializer(many=True)


# ═══════════════════════════════════════════════════════════════════════════
# GHG Protocol Phase 2 Serializers
# ═══════════════════════════════════════════════════════════════════════════


class OrganizationalBoundarySerializer(serializers.ModelSerializer):
    consolidation_approach_display = serializers.CharField(
        source='get_consolidation_approach_display', read_only=True
    )
    included_org_units_names = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationalBoundary
        fields = [
            'id', 'name', 'consolidation_approach', 'consolidation_approach_display',
            'description', 'included_org_units', 'included_org_units_names',
            'is_active', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_included_org_units_names(self, obj):
        return [ou.name for ou in obj.included_org_units.all()]


class BaseYearSerializer(serializers.ModelSerializer):
    reporting_period_name = serializers.CharField(
        source='reporting_period.name', read_only=True
    )
    recalculation_policy_display = serializers.CharField(
        source='get_recalculation_policy_display', read_only=True
    )
    open_triggers_count = serializers.SerializerMethodField()

    class Meta:
        model = BaseYear
        fields = [
            'id', 'year', 'reporting_period', 'reporting_period_name',
            'recalculation_policy', 'recalculation_policy_display',
            'significance_threshold_pct', 'description', 'is_active',
            'open_triggers_count',
            'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by',
                           'reporting_period_name', 'open_triggers_count']

    def get_open_triggers_count(self, obj):
        return obj.recalculation_triggers.filter(resolution_status='open').count()


class RecalculationTriggerSerializer(serializers.ModelSerializer):
    trigger_type_display = serializers.CharField(
        source='get_trigger_type_display', read_only=True
    )
    resolution_status_display = serializers.CharField(
        source='get_resolution_status_display', read_only=True
    )
    base_year_label = serializers.CharField(source='base_year.__str__', read_only=True)
    triggered_by_name = serializers.CharField(
        source='triggered_by.username', read_only=True
    )

    class Meta:
        model = RecalculationTrigger
        fields = [
            'id', 'base_year', 'base_year_label',
            'trigger_type', 'trigger_type_display',
            'description', 'variance_pct',
            'resolution_status', 'resolution_status_display',
            'resolution_notes',
            'triggered_at', 'triggered_by', 'triggered_by_name',
            'resolved_at',
        ]
        read_only_fields = ['id', 'triggered_at', 'triggered_by_name', 'base_year_label']
