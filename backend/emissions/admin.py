# File: emissions/admin.py
# Django admin registration for emissions app models.

from django.contrib import admin
from .models import (
    EmissionFactor, GWP, Calculation, ReportingPeriod, CalculationRule,
    OrganizationalBoundary, BaseYear, RecalculationTrigger,
)


@admin.register(ReportingPeriod)
class ReportingPeriodAdmin(admin.ModelAdmin):
    """Admin interface for reporting periods/cycles."""
    
    list_display = [
        'name', 'start_date', 'end_date', 
        'period_type', 'status', 'is_baseline'
    ]
    list_filter = ['status', 'period_type', 'is_baseline']
    search_fields = ['name', 'description']
    ordering = ['-start_date']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Identity', {
            'fields': ('name',)
        }),
        ('Period Dates', {
            'fields': ('start_date', 'end_date', 'period_type')
        }),
        ('Status', {
            'fields': ('status', 'is_baseline')
        }),
        ('Details', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'created_by']


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    """Admin interface for emission factors."""
    
    list_display = [
        'code', 'name', 'category', 'scope', 'factor_value', 
        'activity_unit', 'country_code', 'is_active'
    ]
    list_filter = ['category', 'scope', 'country_code', 'is_active', 'source']
    search_fields = ['name', 'code', 'subcategory', 'country', 'source']
    ordering = ['category', 'name']
    
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'code')
        }),
        ('Classification', {
            'fields': ('category', 'subcategory', 'scope')
        }),
        ('Factor Details', {
            'fields': ('factor_value', 'factor_unit', 'activity_unit')
        }),
        ('GHG Breakdown', {
            'fields': ('co2_factor', 'ch4_factor', 'n2o_factor'),
            'classes': ('collapse',)
        }),
        ('Geographic Scope', {
            'fields': ('country', 'country_code', 'region'),
            'classes': ('collapse',)
        }),
        ('Source & Validity', {
            'fields': ('source', 'source_url', 'valid_from', 'valid_to')
        }),
        ('Metadata & Smart Matching', {
            'fields': ('notes', 'tags', 'is_active'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GWP)
class GWPAdmin(admin.ModelAdmin):
    """Admin interface for Global Warming Potentials."""
    
    list_display = [
        'gas_name', 'gas_formula', 'gwp_ar6_100yr', 'gwp_ar5_100yr', 'cas_number'
    ]
    search_fields = ['gas_name', 'gas_formula', 'cas_number']
    ordering = ['gas_name']
    
    fieldsets = (
        ('Gas Identity', {
            'fields': ('gas_name', 'gas_formula', 'cas_number')
        }),
        ('GWP Values (100-year horizon)', {
            'fields': ('gwp_ar6_100yr', 'gwp_ar5_100yr')
        }),
        ('GWP Values (20-year horizon)', {
            'fields': ('gwp_ar6_20yr', 'gwp_ar5_20yr'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    """Admin interface for emission calculations."""
    
    list_display = [
        'id', 'module', 'scope', 'category',
        'activity_value', 'activity_unit', 'co2e_kg',
        'reporting_period', 'reporting_year', 'calculated_at'
    ]
    list_filter = ['scope', 'category', 'reporting_year', 'reporting_period', 'calculation_method']
    search_fields = ['module__name', 'emission_factor__name']
    ordering = ['-calculated_at']
    date_hierarchy = 'calculated_at'
    
    readonly_fields = [
        'data_row', 'module', 'emission_factor',
        'activity_value', 'activity_unit', 'co2e_kg', 'co2_kg', 
        'ch4_kg', 'n2o_kg', 'scope', 'category', 'reporting_period',
        'reporting_year', 'reporting_month', 'activity_date',
        'calculated_at', 'calculated_by', 'calculation_method'
    ]
    
    fieldsets = (
        ('Source Data', {
            'fields': ('data_row', 'module')
        }),
        ('Calculation Details', {
            'fields': ('emission_factor', 'activity_value', 'activity_unit')
        }),
        ('Results', {
            'fields': ('co2e_kg', 'co2_kg', 'ch4_kg', 'n2o_kg')
        }),
        ('Classification', {
            'fields': ('scope', 'category')
        }),
        ('Reporting Period', {
            'fields': ('reporting_period', 'reporting_year', 'reporting_month', 'activity_date')
        }),
        ('Audit', {
            'fields': ('calculated_at', 'calculated_by', 'calculation_method')
        }),
    )
    
    def has_add_permission(self, request):
        """Disable adding calculations via admin - should be done via API."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing calculations - they should be immutable for audit."""
        return False


@admin.register(CalculationRule)
class CalculationRuleAdmin(admin.ModelAdmin):
    """Admin interface for calculation rules (dynamic field → emission factor binding)."""
    
    list_display = [
        'name', 'data_table', 'activity_field', 'emission_factor', 
        'rule_type', 'auto_calculate', 'is_active'
    ]
    list_filter = ['rule_type', 'is_active', 'auto_calculate', 'data_table__module']
    search_fields = ['name', 'description', 'data_table__title', 'emission_factor__code']
    ordering = ['data_table', 'name']
    
    fieldsets = (
        ('Rule Identity', {
            'fields': ('name', 'description')
        }),
        ('Source Data Binding', {
            'fields': ('data_table', 'activity_field', 'date_field'),
            'description': 'Link to the dynamic DataTable and the field containing activity data'
        }),
        ('Emission Factor', {
            'fields': ('emission_factor',),
            'description': 'The emission factor to apply (or use dynamic selection below)'
        }),
        ('Dynamic Factor Selection', {
            'fields': ('factor_selector_field', 'factor_selector_mapping'),
            'classes': ('collapse',),
            'description': 'Optionally select emission factor based on another field value'
        }),
        ('Output', {
            'fields': ('output_field',),
            'classes': ('collapse',),
            'description': 'Optionally write calculated CO2e back to a field in the DataTable'
        }),
        ('Calculation Options', {
            'fields': ('rule_type', 'unit_conversion_factor', 'custom_formula', 'auto_calculate', 'is_active')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'data_table', 'activity_field', 'emission_factor'
        )


# ═══════════════════════════════════════════════════════════════════════════
# GHG Protocol Phase 2 Admin Registrations
# ═══════════════════════════════════════════════════════════════════════════


@admin.register(OrganizationalBoundary)
class OrganizationalBoundaryAdmin(admin.ModelAdmin):
    list_display = ['name', 'consolidation_approach', 'is_active', 'created_at']
    list_filter = ['consolidation_approach', 'is_active']
    search_fields = ['name', 'description']
    ordering = ['-created_at']


@admin.register(BaseYear)
class BaseYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'reporting_period', 'recalculation_policy',
                   'significance_threshold_pct', 'is_active']
    list_filter = ['recalculation_policy', 'is_active']
    search_fields = ['description']
    ordering = ['-year']


@admin.register(RecalculationTrigger)
class RecalculationTriggerAdmin(admin.ModelAdmin):
    list_display = ['id', 'base_year', 'trigger_type', 'variance_pct',
                   'resolution_status', 'triggered_at']
    list_filter = ['trigger_type', 'resolution_status']
    search_fields = ['description', 'resolution_notes']
    ordering = ['-triggered_at']
    readonly_fields = ['triggered_at', 'resolved_at']
