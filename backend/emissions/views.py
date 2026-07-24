# File: emissions/views.py
# REST API Views for Emission Factor Calculator

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, Count, Avg, F, Q, Max
from django.db.models.functions import TruncMonth, ExtractMonth
from django.utils import timezone
from decimal import Decimal
from collections import defaultdict
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .models import ReportingPeriod, EmissionFactor, GWP, Calculation, CalculationRule, ReportConfig
from accounts.rbac_utils import get_visible_module_ids, get_visible_org_units
from accounts.models import ScopedRole
from core.models import Module
from dataschema.models import DataRow, DataTable
from .serializers import (
    ReportingPeriodSerializer,
    EmissionFactorSerializer,
    EmissionFactorSummarySerializer,
    GWPSerializer,
    CalculationSerializer,
    CalculationRuleSerializer,
    DashboardSummarySerializer,
    EmissionReportSerializer,
    ReportConfigSerializer,
)


def _scope_calcs(user, queryset):
    """Restrict a Calculation queryset to the modules the user may see.
    Superusers / global admins are unrestricted (get_visible_module_ids returns None)."""
    allowed = get_visible_module_ids(user)
    if allowed is None:
        return queryset
    return queryset.filter(module_id__in=allowed)


class ReportingPeriodViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reporting periods.
    
    Endpoints:
    - GET /emissions/periods/ - List all periods
    - POST /emissions/periods/ - Create new period
    - GET /emissions/periods/{id}/ - Get period details
    - PUT/PATCH /emissions/periods/{id}/ - Update period
    - DELETE /emissions/periods/{id}/ - Delete period
    - GET /emissions/periods/active/ - Get currently active period
    """
    serializer_class = ReportingPeriodSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return all reporting periods for authenticated users."""
        return ReportingPeriod.objects.all()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get the currently active reporting period."""
        queryset = self.get_queryset()
        today = timezone.now().date()
        
        active_period = queryset.filter(
            start_date__lte=today,
            end_date__gte=today,
            status__in=['open', 'locked']
        ).first()
        
        if active_period:
            serializer = self.get_serializer(active_period)
            return Response(serializer.data)
        
        return Response({'detail': 'No active reporting period found.'}, status=404)


class EmissionFactorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for emission factors.
    
    Query Parameters:
    - category: Filter by category (e.g., 'electricity', 'transport')
    - scope: Filter by scope (1, 2, or 3)
    - country_code: Filter by country (ISO 3166-1 alpha-3)
    - search: Search by name or code
    - active: Filter by active status (true/false)
    """
    serializer_class = EmissionFactorSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = EmissionFactor.objects.all()
        
        # Apply filters
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        country_code = self.request.query_params.get('country_code')
        if country_code:
            queryset = queryset.filter(country_code=country_code)
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        
        active = self.request.query_params.get('active')
        if active is not None:
            queryset = queryset.filter(is_active=active.lower() == 'true')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get minimal list for dropdowns."""
        queryset = self.get_queryset().filter(is_active=True)
        serializer = EmissionFactorSummarySerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get list of available categories."""
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in EmissionFactor.CATEGORY_CHOICES
        ])


class GWPViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Global Warming Potentials (read-only)."""
    queryset = GWP.objects.all()
    serializer_class = GWPSerializer
    permission_classes = [IsAuthenticated]


class CalculationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for emission calculations.
    
    Query Parameters:
    - project_id: Filter by project
    - module_id: Filter by module
    - scope: Filter by scope (1, 2, 3)
    - category: Filter by category
    - reporting_period_id: Filter by reporting period
    - reporting_year: Filter by year
    """
    serializer_class = CalculationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Calculation.objects.none()
        queryset = Calculation.objects.select_related(
            'module', 'emission_factor', 'reporting_period'
        )
        
        module_id = self.request.query_params.get('module_id')
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        period_id = self.request.query_params.get('reporting_period_id')
        if period_id:
            queryset = queryset.filter(reporting_period_id=period_id)
        
        year = self.request.query_params.get('reporting_year')
        if year:
            queryset = queryset.filter(reporting_year=year)
        
        queryset = _scope_calcs(self.request.user, queryset)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response({
            'count': queryset.count(),
            'results': list(queryset.values('id', 'module_id', 'reporting_year', 'scope', 'co2e_kg'))
        })


class CalculationRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for calculation rules.
    
    Additional Actions:
    - POST /emissions/rules/{id}/execute/ - Run calculations for a rule
    """
    serializer_class = CalculationRuleSerializer
    permission_classes = [IsAuthenticated]
    queryset = CalculationRule.objects.select_related(
        'data_table', 'activity_field', 'emission_factor'
    )
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute calculations for this rule."""
        rule = self.get_object()
        
        # Get optional reporting period
        period_id = request.data.get('reporting_period_id')
        period = None
        if period_id:
            period = ReportingPeriod.objects.filter(id=period_id).first()
        
        recalculate = request.data.get('recalculate', False)
        
        created, skipped, errors = rule.calculate_for_table(
            reporting_period=period,
            user=request.user,
            recalculate=recalculate
        )
        
        return Response({
            'rule': rule.name,
            'created': created,
            'skipped': skipped,
            'errors': errors,
            'message': f'Created {created} calculations, skipped {skipped}, {errors} errors'
        })


class DashboardAPIView(APIView):
    """
    Dashboard API for emission summaries and visualizations.
    
    GET /emissions/dashboard/?project_id=1&reporting_period_id=1
    
    Returns complete dashboard data including:
    - Scope breakdown (Scope 1, 2, 3 totals)
    - Category breakdown
    - Monthly trends
    - Data quality metrics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        period_id = request.query_params.get('reporting_period_id')
        year = request.query_params.get('year', timezone.now().year)
        
        # Base queryset (org-scoped to the requesting user)
        base_queryset = _scope_calcs(request.user, Calculation.objects.all())
        queryset = base_queryset
        
        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
            if reporting_period:
                queryset = queryset.filter(reporting_period=reporting_period)
        else:
            queryset = queryset.filter(reporting_year=year)
        
        # Calculate scope breakdown
        scope_data = queryset.values('scope').annotate(
            total_kg=Sum('co2e_kg'),
            count=Count('id')
        ).order_by('scope')
        
        grand_total_kg = sum(s['total_kg'] or 0 for s in scope_data)
        
        scope_names = {1: 'Scope 1 - Direct', 2: 'Scope 2 - Indirect Energy', 3: 'Scope 3 - Value Chain'}
        scope_breakdown = []
        for s in scope_data:
            total_kg = s['total_kg'] or Decimal('0')
            scope_breakdown.append({
                'scope': s['scope'],
                'scope_name': scope_names.get(s['scope'], f"Scope {s['scope']}"),
                'co2e_tonnes': round(total_kg / 1000, 2),
                'percentage': round((total_kg / grand_total_kg * 100) if grand_total_kg else 0, 2)
            })
        
        # Calculate category breakdown
        category_data = queryset.values('category', 'scope').annotate(
            total_kg=Sum('co2e_kg'),
            count=Count('id')
        ).order_by('scope', 'category')
        
        category_names = dict(EmissionFactor.CATEGORY_CHOICES)
        category_breakdown = []
        for c in category_data:
            total_kg = c['total_kg'] or Decimal('0')
            category_breakdown.append({
                'category': c['category'],
                'category_name': category_names.get(c['category'], c['category']),
                'scope': c['scope'],
                'co2e_tonnes': round(total_kg / 1000, 2),
                'count': c['count']
            })
        
        # Calculate monthly trends
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        monthly_data = queryset.values('reporting_month', 'scope').annotate(
            total_kg=Sum('co2e_kg')
        ).order_by('reporting_month', 'scope')
        
        # Reorganize into monthly structure
        monthly_dict = defaultdict(lambda: {'scope1': Decimal('0'), 'scope2': Decimal('0'), 'scope3': Decimal('0')})
        for m in monthly_data:
            month = m['reporting_month']
            if month:
                scope_key = f"scope{m['scope']}"
                monthly_dict[month][scope_key] = m['total_kg'] or Decimal('0')
        
        monthly_trend = []
        for month_num in range(1, 13):
            data = monthly_dict.get(month_num, {})
            scope1 = data.get('scope1', Decimal('0')) / 1000
            scope2 = data.get('scope2', Decimal('0')) / 1000
            scope3 = data.get('scope3', Decimal('0')) / 1000
            monthly_trend.append({
                'month': str(month_num).zfill(2),
                'month_name': month_names[month_num] if month_num < len(month_names) else str(month_num),
                'scope1': round(scope1, 2),
                'scope2': round(scope2, 2),
                'scope3': round(scope3, 2),
                'total': round(scope1 + scope2 + scope3, 2)
            })
        
        # Data quality score (simplified)
        total_expected = 12 * 3  # 12 months, 3 scopes
        months_with_data = len([m for m in monthly_trend if m['total'] > 0])
        data_quality = min(100, int((months_with_data / total_expected) * 100 * 3))
        
        # Build response
        response_data = {
            'reporting_period': ReportingPeriodSerializer(reporting_period).data if reporting_period else None,
            'total_co2e_tonnes': round(grand_total_kg / 1000, 2),
            'scope_breakdown': scope_breakdown,
            'category_breakdown': category_breakdown,
            'monthly_trend': monthly_trend,
            'data_quality_score': data_quality,
            'calculation_count': base_queryset.count(),
            'last_updated': queryset.order_by('-calculated_at').values_list('calculated_at', flat=True).first()
        }
        
        return Response(response_data)


class YearlyComparisonAPIView(APIView):
    """
    API for year-over-year emissions comparison.
    
    GET /emissions/yearly-comparison/?project_id=1&years=2020,2021,2022,2023,2024,2025,2026
    
    Returns yearly emissions data for comparison charts.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        years_param = request.query_params.get('years', '')
        
        # Default to all years from 2020 to current year
        current_year = timezone.now().year
        if years_param:
            try:
                years = [int(y.strip()) for y in years_param.split(',')]
            except ValueError:
                years = list(range(2020, current_year + 1))
        else:
            years = list(range(2020, current_year + 1))
        
        queryset = _scope_calcs(request.user, Calculation.objects.all())
        
        # Get yearly totals
        yearly_data = queryset.filter(reporting_year__in=years).values('reporting_year').annotate(
            total_kg=Sum('co2e_kg'),
            count=Count('id')
        ).order_by('reporting_year')
        
        # Get baseline year
        baseline_period = ReportingPeriod.objects.filter(is_baseline=True).first()
        baseline_year = baseline_period.start_date.year if baseline_period else 2020
        
        # Build response with calculated metrics
        yearly_comparison = []
        baseline_total = None
        previous_total = None
        
        for y in yearly_data:
            year = y['reporting_year']
            total_kg = y['total_kg'] or Decimal('0')
            total_tonnes = round(total_kg / 1000, 2)
            
            if year == baseline_year:
                baseline_total = total_tonnes
            
            reduction_from_baseline = 0
            if baseline_total and baseline_total > 0:
                reduction_from_baseline = round(((baseline_total - total_tonnes) / baseline_total) * 100, 1)
            
            yoy_change = 0
            if previous_total and previous_total > 0:
                yoy_change = round(((total_tonnes - previous_total) / previous_total) * 100, 1)
            
            yearly_comparison.append({
                'year': year,
                'total_co2e_tonnes': total_tonnes,
                'calculation_count': y['count'],
                'reduction_from_baseline': reduction_from_baseline,
                'yoy_change': yoy_change,
                'is_baseline': year == baseline_year,
            })
            
            previous_total = total_tonnes
        
        # Get scope breakdown by year
        scope_by_year = queryset.filter(reporting_year__in=years).values(
            'reporting_year', 'scope'
        ).annotate(
            total_kg=Sum('co2e_kg')
        ).order_by('reporting_year', 'scope')
        
        scope_data = defaultdict(lambda: {'scope1': 0, 'scope2': 0, 'scope3': 0})
        for s in scope_by_year:
            year = s['reporting_year']
            scope_key = f"scope{s['scope']}"
            scope_data[year][scope_key] = round((s['total_kg'] or Decimal('0')) / 1000, 2)
        
        # Add scope breakdown to yearly comparison
        for item in yearly_comparison:
            scopes = scope_data.get(item['year'], {})
            item['scope1'] = scopes.get('scope1', 0)
            item['scope2'] = scopes.get('scope2', 0)
            item['scope3'] = scopes.get('scope3', 0)
        
        # Calculate target trajectory (SBTi 1.5°C aligned: 50% reduction by 2030)
        target_reduction_by_2030 = 0.50
        years_to_2030 = 2030 - baseline_year if baseline_year else 10
        annual_reduction = target_reduction_by_2030 / years_to_2030
        
        targets = []
        for year in years:
            years_from_baseline = year - baseline_year if baseline_year else 0
            target_reduction = min(target_reduction_by_2030, annual_reduction * years_from_baseline)
            target_value = round(float(baseline_total) * (1 - target_reduction), 2) if baseline_total else 0
            targets.append({
                'year': year,
                'target_co2e_tonnes': target_value,
                'target_reduction_pct': round(target_reduction * 100, 1),
            })
        
        response_data = {
            'baseline_year': baseline_year,
            'baseline_total_tonnes': baseline_total,
            'current_year': max(years),
            'yearly_comparison': yearly_comparison,
            'targets': targets,
        }
        
        return Response(response_data)


class ReportAPIView(APIView):
    """
    Report API for generating emission reports.
    
    GET /emissions/report/?project_id=1&reporting_period_id=1&format=json
    
    Generates a detailed emission report suitable for:
    - GHG Protocol reporting
    - Regulatory compliance
    - Stakeholder disclosure
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        period_id = request.query_params.get('reporting_period_id')
        org_unit_id = request.query_params.get('org_unit_id')
        year = request.query_params.get('year', timezone.now().year)
        report_format = request.query_params.get('format', 'json')
        
        # Base queryset (org-scoped to the requesting user)
        queryset = _scope_calcs(request.user, Calculation.objects.select_related(
            'module', 'emission_factor', 'data_row', 'data_row__data_table'
        ))
        
        # Apply org_unit filter if provided
        if org_unit_id:
            from mdm.models import OrgUnit
            try:
                ou = OrgUnit.objects.get(pk=org_unit_id)
                descendant_ids = ou.get_descendant_ids(include_self=True)
                queryset = queryset.filter(module__org_unit_id__in=descendant_ids)
            except OrgUnit.DoesNotExist:
                pass
        
        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
            if reporting_period:
                queryset = queryset.filter(reporting_period=reporting_period)
        else:
            queryset = queryset.filter(reporting_year=year)
        
        # Calculate summary
        scope_totals = queryset.values('scope').annotate(
            total_kg=Sum('co2e_kg'),
            count=Count('id')
        ).order_by('scope')
        
        scope_names = {1: 'Scope 1 - Direct', 2: 'Scope 2 - Indirect Energy', 3: 'Scope 3 - Value Chain'}
        
        summary = {
            'total_emissions_tonnes': Decimal('0'),
            'scope_breakdown': []
        }
        
        for s in scope_totals:
            total_kg = s['total_kg'] or Decimal('0')
            tonnes = total_kg / 1000
            summary['total_emissions_tonnes'] += tonnes
            summary['scope_breakdown'].append({
                'scope': s['scope'],
                'name': scope_names.get(s['scope'], f"Scope {s['scope']}"),
                'emissions_tonnes': round(tonnes, 2),
                'calculation_count': s['count']
            })
        
        summary['total_emissions_tonnes'] = round(summary['total_emissions_tonnes'], 2)
        
        # Scope details with categories
        scope_details = []
        for scope in [1, 2, 3]:
            scope_qs = queryset.filter(scope=scope)
            categories = scope_qs.values('category').annotate(
                total_kg=Sum('co2e_kg'),
                count=Count('id')
            ).order_by('category')
            
            category_names = dict(EmissionFactor.CATEGORY_CHOICES)
            scope_total = sum(c['total_kg'] or 0 for c in categories)
            
            scope_details.append({
                'scope': scope,
                'name': scope_names.get(scope, f"Scope {scope}"),
                'total_tonnes': round(scope_total / 1000, 2),
                'categories': [
                    {
                        'name': category_names.get(c['category'], c['category']),
                        'code': c['category'],
                        'emissions_tonnes': round((c['total_kg'] or 0) / 1000, 2),
                        'count': c['count']
                    }
                    for c in categories
                ]
            })
        
        # Detailed rows (limit to prevent huge responses)
        rows = []
        for calc in queryset[:1000]:
            rows.append({
                'module': calc.module.name if calc.module else '',
                'table': calc.data_row.data_table.title if calc.data_row and calc.data_row.data_table else '',
                'category': calc.category,
                'scope': calc.scope,
                'activity_description': calc.emission_factor.name if calc.emission_factor else '',
                'activity_value': calc.activity_value,
                'activity_unit': calc.activity_unit,
                'emission_factor': f"{calc.emission_factor.factor_value} {calc.emission_factor.factor_unit}/{calc.emission_factor.activity_unit}" if calc.emission_factor else '',
                'co2e_kg': calc.co2e_kg,
                'co2e_tonnes': round(calc.co2e_kg / 1000, 4)
            })
        
        # Build report
        report = {
            'title': f"Carbon Emissions Report - {reporting_period.name if reporting_period else year}",
            'reporting_period': ReportingPeriodSerializer(reporting_period).data if reporting_period else {
                'year': year,
                'name': f'Year {year}'
            },
            'generated_at': timezone.now(),
            'summary': summary,
            'scope_details': scope_details,
            'rows': rows
        }
        
        # CSV export
        if report_format == 'csv':
            import csv
            import io
            from django.http import HttpResponse
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Scope', 'Category', 'CO2e (tonnes)', 'Count'])
            
            for scope_detail in scope_details:
                for category in scope_detail.get('categories', []):
                    writer.writerow([
                        scope_detail['name'],
                        category['name'],
                        category['emissions_tonnes'],
                        category['count']
                    ])
            
            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="emissions_report.csv"'
            return response
        
        return Response(report)


class CalculateAPIView(APIView):
    """
    API to trigger emission calculations.
    
    POST /emissions/calculate/
    {
        "rule_id": 1,  // OR
        "project_id": 1,  // Calculate all rules for a project
        "reporting_period_id": 1,
        "recalculate": false
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        rule_id = request.data.get('rule_id')
        project_id = request.data.get('project_id')
        period_id = request.data.get('reporting_period_id')
        recalculate = request.data.get('recalculate', False)
        
        # Get reporting period
        period = None
        if period_id:
            period = ReportingPeriod.objects.filter(id=period_id).first()
        
        results = []
        
        if rule_id:
            # Execute single rule
            rule = CalculationRule.objects.filter(id=rule_id).first()
            if not rule:
                return Response({'error': 'Rule not found'}, status=404)
            
            created, skipped, errors = rule.calculate_for_table(
                reporting_period=period,
                user=request.user,
                recalculate=recalculate
            )
            results.append({
                'rule': rule.name,
                'created': created,
                'skipped': skipped,
                'errors': errors
            })
        
        else:
            # Execute all active rules across all data tables
            rules = CalculationRule.objects.filter(is_active=True)
            
            for rule in rules:
                created, skipped, errors = rule.calculate_for_table(
                    reporting_period=period,
                    user=request.user,
                    recalculate=recalculate
                )
                results.append({
                    'rule': rule.name,
                    'created': created,
                    'skipped': skipped,
                    'errors': errors
                })
        
        total_created = sum(r['created'] for r in results)
        total_skipped = sum(r['skipped'] for r in results)
        total_errors = sum(r['errors'] for r in results)
        
        return Response({
            'success': True,
            'total_created': total_created,
            'total_skipped': total_skipped,
            'total_errors': total_errors,
            'rules_executed': len(results),
            'details': results
        })


def _generate_report_from_config(config, user):
    """Generate report data from a ReportConfig instance."""
    from datetime import datetime
    from mdm.models import OrgUnit
    
    queryset = Calculation.objects.select_related(
        'reporting_period', 'module', 'module__org_unit'
    ).all()
    
    # Apply RBAC scoping
    queryset = _scope_calcs(user, queryset)
    
    # Apply config filters
    if config.org_unit_id:
        try:
            ou = OrgUnit.objects.get(pk=config.org_unit_id)
            descendant_ids = ou.get_descendant_ids(include_self=True)
            queryset = queryset.filter(module__org_unit_id__in=descendant_ids)
        except OrgUnit.DoesNotExist:
            pass
    
    if config.reporting_period_id:
        queryset = queryset.filter(reporting_period_id=config.reporting_period_id)
    elif config.custom_start and config.custom_end:
        queryset = queryset.filter(
            activity_date__gte=config.custom_start,
            activity_date__lte=config.custom_end
        )
    
    if config.ghg_scopes:
        queryset = queryset.filter(scope__in=config.ghg_scopes)
    
    if config.categories:
        queryset = queryset.filter(category__in=config.categories)
    
    # Aggregate data
    scope_breakdown = []
    scope_data = queryset.values('scope').annotate(
        total_kg=Sum('co2e_kg'),
        count=Count('id')
    ).order_by('scope')
    
    category_breakdown = []
    category_data = queryset.values('category').annotate(
        total_kg=Sum('co2e_kg'),
        count=Count('id')
    ).order_by('category')
    
    module_breakdown = []
    if config.grouping == 'module':
        module_data = queryset.values('module__name').annotate(
            total_kg=Sum('co2e_kg'),
            count=Count('id')
        ).order_by('module__name')
        for m in module_data:
            module_breakdown.append({
                'module': m['module__name'],
                'co2e_tonnes': round((m['total_kg'] or 0) / 1000, 2),
                'calculation_count': m['count']
            })
    
    grand_total_kg = sum(s['total_kg'] or 0 for s in scope_data)
    scope_names = {1: 'Scope 1 - Direct', 2: 'Scope 2 - Indirect Energy', 3: 'Scope 3 - Value Chain'}
    
    for s in scope_data:
        total_kg = s['total_kg'] or Decimal('0')
        scope_breakdown.append({
            'scope': s['scope'],
            'scope_name': scope_names.get(s['scope'], f"Scope {s['scope']}"),
            'co2e_tonnes': round(total_kg / 1000, 2),
            'percentage': round((total_kg / grand_total_kg * 100) if grand_total_kg else 0, 2)
        })
    
    for c in category_data:
        total_kg = c['total_kg'] or Decimal('0')
        category_breakdown.append({
            'category': c['category'],
            'co2e_tonnes': round(total_kg / 1000, 2),
            'calculation_count': c['count']
        })
    
    return {
        'config_id': config.id,
        'config_name': config.name,
        'reporting_period_id': config.reporting_period_id,
        'date_range': {
            'start': config.custom_start.isoformat() if config.custom_start else None,
            'end': config.custom_end.isoformat() if config.custom_end else None,
        },
        'org_unit_id': config.org_unit_id,
        'total_co2e_tonnes': round(grand_total_kg / 1000, 2),
        'calculation_count': queryset.count(),
        'scope_breakdown': scope_breakdown,
        'category_breakdown': category_breakdown,
        'module_breakdown': module_breakdown,
        'generated_at': datetime.now().isoformat(),
    }


class ReportConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for managing saved report configurations."""
    serializer_class = ReportConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Non-staff users see only their own configs; staff sees all."""
        if self.request.user.is_staff or self.request.user.is_superuser:
            return ReportConfig.objects.all()
        return ReportConfig.objects.filter(created_by=self.request.user)
    
    def perform_create(self, serializer):
        """Auto-set created_by to current user."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """Generate report from this config."""
        config = self.get_object()
        config.last_run_at = timezone.now()
        config.save()
        
        report_data = _generate_report_from_config(config, request.user)
        return Response(report_data)


class OwnerDashboardAPIView(APIView):
    """
    Data owner scoped dashboard: emissions + DQ metrics for owned assets.
    
    GET /emissions/owner-dashboard/
    
    Returns:
    - Org-unit scoped emissions summary
    - DQ metrics for owned data
    - Reporting status
    - Quality badges
    
    Accessible only to users with org_unit scopes via ScopedRole.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        period_id = request.query_params.get('reporting_period_id')
        
        # Get user's org units from ScopedRole
        if user.is_superuser or user.is_staff:
            org_units = None  # All org units
        else:
            org_units = list(
                ScopedRole.objects.filter(
                    user=user, is_active=True
                ).values_list('org_unit_id', flat=True).distinct()
            )
            if not org_units:
                return Response({'detail': 'No accessible org units'}, status=403)
        
        # Get reporting period (default to active)
        reporting_period = None
        if period_id:
            reporting_period = ReportingPeriod.objects.filter(id=period_id).first()
        else:
            today = timezone.now().date()
            reporting_period = ReportingPeriod.objects.filter(
                start_date__lte=today,
                end_date__gte=today,
                status__in=['open', 'locked']
            ).first()
        
        # Scope calculations to user's org units
        calc_qs = Calculation.objects.all()
        if org_units is not None:
            calc_qs = calc_qs.filter(module__org_unit_id__in=org_units)
        
        if reporting_period:
            calc_qs = calc_qs.filter(reporting_period=reporting_period)
        
        # Calculate scope breakdown
        scope_breakdown = []
        scope_data = calc_qs.values('scope').annotate(
            total_kg=Sum('co2e_kg'),
            count=Count('id')
        ).order_by('scope')
        
        grand_total_kg = sum(s['total_kg'] or 0 for s in scope_data)
        scope_names = {1: 'Scope 1 - Direct', 2: 'Scope 2 - Indirect Energy', 3: 'Scope 3 - Value Chain'}
        
        for s in scope_data:
            total_kg = s['total_kg'] or Decimal('0')
            scope_breakdown.append({
                'scope': s['scope'],
                'scope_name': scope_names.get(s['scope'], f"Scope {s['scope']}"),
                'co2e_tonnes': round(total_kg / 1000, 2),
                'percentage': round((total_kg / grand_total_kg * 100) if grand_total_kg else 0, 2)
            })
        
        # DQ metrics — real data from AssetProfile quality_status
        from catalog.models import AssetProfile
        
        # Scope asset profiles to user's org units (same scoping as calc_qs above)
        if org_units is not None:
            asset_qs = AssetProfile.objects.filter(
                Q(data_table__module__org_unit_id__in=org_units) |
                Q(data_field__data_table__module__org_unit_id__in=org_units)
            )
        else:
            asset_qs = AssetProfile.objects.all()
        
        total_assets = asset_qs.count()
        passing_count = asset_qs.filter(quality_status='passing').count()
        warning_count = asset_qs.filter(quality_status='warning').count()
        failing_count = asset_qs.filter(quality_status='failing').count()
        unknown_count = asset_qs.filter(quality_status='unknown').count()
        
        # Quality score = (passing / total * 100) if any assets exist
        quality_score = round((passing_count / total_assets * 100), 1) if total_assets > 0 else 0.0
        
        dq_summary = {
            'quality_score': quality_score,
            'passing_count': passing_count,
            'warning_count': warning_count,
            'failing_count': failing_count,
            'unknown_count': unknown_count,
            'total_assets': total_assets,
        }
        
        # Build response
        response_data = {
            'reporting_period': ReportingPeriodSerializer(reporting_period).data if reporting_period else None,
            'total_co2e_tonnes': round(grand_total_kg / 1000, 2),
            'scope_breakdown': scope_breakdown,
            'category_breakdown': [],  # Can be expanded later
            'monthly_trend': [],  # Can be expanded later
            'data_quality_summary': dq_summary,
            'calculation_count': calc_qs.count(),
            'submission_status': 'pending' if reporting_period and reporting_period.status == 'open' else 'submitted',
        }
        
        return Response(response_data)


class OwnerSummaryAPIView(APIView):
    """Get high-level summary data for the data owner landing page."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Return a summary of emission modules and data quality for the current org unit.',
        responses={200: openapi.Response('OK', schema=openapi.Schema(type=openapi.TYPE_OBJECT))}
    )
    def get(self, request):
        org_units = get_visible_org_units(request.user)
        if not org_units:
            return Response({'detail': 'No accessible org units'}, status=403)

        org_unit = org_units[0]
        modules = Module.objects.filter(org_unit=org_unit).select_related('org_unit').order_by('name')

        module_ids = list(modules.values_list('id', flat=True))
        row_counts = dict(
            DataTable.objects.filter(module_id__in=module_ids)
            .annotate(row_count=Count('rows'))
            .values_list('module_id', 'row_count')
        )
        modules_with_data = sum(1 for module_id in module_ids if row_counts.get(module_id, 0) > 0)

        latest_row = DataRow.objects.filter(data_table__module__org_unit=org_unit).order_by('-created_at').first()
        latest_submission = latest_row.created_at if latest_row else None

        module_data = [{
            'id': module.id,
            'name': module.name,
            'scope': module.scope,
            'table_name': module.name.lower().replace(' ', '_'),
        } for module in modules]

        return Response({
            'org_unit': {
                'id': org_unit.id,
                'name': org_unit.name,
                'code': getattr(org_unit, 'code', ''),
            },
            'modules': module_data,
            'summary': {
                'total_modules': len(module_data),
                'modules_with_data': modules_with_data,
                'latest_submission': latest_submission.isoformat() if latest_submission else None,
                'data_quality': {'passing': 0, 'warning': 0, 'failing': 0},
            },
        })


class OwnerAssetsAPIView(APIView):
    """Return emission-generating assets scoped to the current owner org unit."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='List emission source modules for the current org unit.',
        manual_parameters=[
            openapi.Parameter('search', openapi.IN_QUERY, description='Filter by module name', type=openapi.TYPE_STRING),
            openapi.Parameter('scope', openapi.IN_QUERY, description='Filter by emission scope', type=openapi.TYPE_INTEGER),
        ],
        responses={200: openapi.Response('OK', schema=openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)))}
    )
    def get(self, request):
        org_units = get_visible_org_units(request.user)
        if not org_units:
            return Response({'detail': 'No accessible org units'}, status=403)

        modules = Module.objects.filter(org_unit__in=org_units).select_related('org_unit').order_by('name')

        search = request.query_params.get('search')
        if search:
            modules = modules.filter(name__icontains=search)

        scope = request.query_params.get('scope')
        if scope:
            modules = modules.filter(scope=scope)

        module_ids = list(modules.values_list('id', flat=True))
        table_row_counts = dict(
            DataTable.objects.filter(module_id__in=module_ids)
            .annotate(row_count=Count('rows'))
            .values_list('module_id', 'row_count')
        )
        last_entry_map = dict(
            DataRow.objects.filter(data_table__module_id__in=module_ids)
            .values('data_table__module_id')
            .annotate(last_created_at=Max('created_at'))
            .values_list('data_table__module_id', 'last_created_at')
        )

        assets = []
        for module in modules:
            row_count = table_row_counts.get(module.id, 0)
            last_entry = last_entry_map.get(module.id)
            assets.append({
                'id': module.id,
                'name': module.name,
                'scope': module.scope,
                'category': module.name.lower().replace(' ', '_'),
                'table_name': module.name.lower().replace(' ', '_'),
                'row_count': row_count,
                'last_entry': last_entry.isoformat() if last_entry else None,
                'data_quality_status': 'passing' if row_count else 'warning',
            })

        return Response(assets)


class OwnerActivityAPIView(APIView):
    """Return recent emission submission activity for the current owner org unit."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Return recent emission activity for the current org unit.',
        responses={200: openapi.Response('OK', schema=openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)))}
    )
    def get(self, request):
        org_units = get_visible_org_units(request.user)
        if not org_units:
            return Response({'detail': 'No accessible org units'}, status=403)

        activity_items = Calculation.objects.filter(module__org_unit__in=org_units).select_related('module', 'reporting_period').order_by('-calculated_at')[:10]
        payload = []
        for calculation in activity_items:
            payload.append({
                'id': calculation.id,
                'activity_type': 'submission',
                'module_id': calculation.module_id,
                'module_name': calculation.module.name,
                'scope': calculation.scope,
                'category': calculation.category,
                'co2e_tonnes': round((calculation.co2e_kg or Decimal('0')) / Decimal('1000'), 2),
                'reported_at': calculation.calculated_at.isoformat(),
                'period_name': calculation.reporting_period.name if calculation.reporting_period else None,
            })
        return Response(payload)
