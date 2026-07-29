# File: emissions/views.py
# REST API Views for Emission Factor Calculator.
# Business logic lives in emissions/services.py — views are thin.

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Sum, Count, Q, Max
from django.utils import timezone
from decimal import Decimal
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .models import ReportingPeriod, EmissionFactor, GWP, Calculation, CalculationRule, ReportConfig
from accounts.rbac_utils import get_visible_module_ids, get_visible_org_units
from core.models import Module
from catalog.permissions import AdminOrSuperuserOnly
from dataschema.models import DataRow, DataTable
from .serializers import (
    ReportingPeriodSerializer,
    EmissionFactorSerializer,
    EmissionFactorSummarySerializer,
    GWPSerializer,
    CalculationSerializer,
    CalculationRuleSerializer,
    ReportConfigSerializer,
)
from .services import (
    scope_calculations,
    DashboardService,
    YearlyComparisonService,
    ReportService,
    CalculationEngineService,
    OwnerService,
    MyDataService,
    ConsoleService,
    ReportConfigService,
)


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
    permission_classes = [AdminOrSuperuserOnly]
    
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
    permission_classes = [AdminOrSuperuserOnly]
    
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
    permission_classes = [AdminOrSuperuserOnly]


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
        
        queryset = scope_calculations(self.request.user, queryset)
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

        data = DashboardService.get_dashboard_data(
            request.user, period_id=period_id, year=int(year) if year else None,
        )

        # Serialize reporting_period for the response
        reporting_period = data.pop('reporting_period', None)
        response_data = {
            'reporting_period': ReportingPeriodSerializer(reporting_period).data if reporting_period else None,
            **data,
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

        if years_param:
            try:
                years = [int(y.strip()) for y in years_param.split(',')]
            except ValueError:
                years = list(range(2020, timezone.now().year + 1))
        else:
            years = list(range(2020, timezone.now().year + 1))

        data = YearlyComparisonService.get_comparison(request.user, years)
        return Response(data)


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

        data = ReportService.generate_report(
            request.user,
            period_id=period_id,
            org_unit_id=org_unit_id,
            year=int(year) if year else None,
            report_format=report_format,
        )

        # CSV export
        if report_format == 'csv':
            import csv
            import io
            from django.http import HttpResponse

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Scope', 'Category', 'CO2e (tonnes)', 'Count'])

            for sd in data.get('scope_details', []):
                for cat in sd.get('categories', []):
                    writer.writerow([
                        sd['name'], cat['name'],
                        cat['emissions_tonnes'], cat['count'],
                    ])

            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="emissions_report.csv"'
            return response

        # Serialize reporting_period for JSON response
        reporting_period = data.pop('reporting_period', None)
        data['reporting_period'] = (
            ReportingPeriodSerializer(reporting_period).data if reporting_period
            else {'year': year, 'name': f'Year {year}'}
        )
        return Response(data)


class CalculateAPIView(APIView):
    """
    API to trigger emission calculations.

    POST /emissions/calculate/
    {
        "rule_id": 1,  // OR
        "reporting_period_id": 1,
        "recalculate": false
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        rule_id = request.data.get('rule_id')
        period_id = request.data.get('reporting_period_id')
        recalculate = request.data.get('recalculate', False)

        rule, period, errors = CalculationEngineService.validate_calculation_request(
            rule_id, period_id=period_id,
        )

        if errors:
            if 'rule_id' in errors and not rule:
                return Response({'error': errors['rule_id']}, status=status.HTTP_400_BAD_REQUEST)
            if 'rule_id' in errors:
                return Response({'error': errors['rule_id']}, status=status.HTTP_404_NOT_FOUND)
            if 'reporting_period_id' in errors:
                return Response({'error': errors['reporting_period_id']}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            if 'rule_id' in errors and 'inactive' in errors['rule_id'].lower():
                return Response({'error': errors['rule_id']}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            if 'rows' in errors:
                return Response({'error': errors['rows']}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            if 'incomplete_rows' in errors:
                return Response({
                    'error': 'Incomplete activity data for one or more rows.',
                    'incomplete_rows': errors['incomplete_rows'],
                }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        created, skipped, err_count = CalculationEngineService.execute_rule(
            rule, reporting_period=period, user=request.user, recalculate=recalculate,
        )

        return Response({
            'success': True,
            'total_created': created,
            'total_skipped': skipped,
            'total_errors': err_count,
            'rule': rule.name,
        })


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

        report_data = ReportConfigService.generate_from_config(config, request.user)
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
        period_id = request.query_params.get('reporting_period_id')
        data = OwnerService.get_owner_dashboard(request.user, period_id=period_id)

        if data is None:
            return Response({'detail': 'No accessible org units'}, status=403)

        reporting_period = data.pop('reporting_period', None)
        data['reporting_period'] = (
            ReportingPeriodSerializer(reporting_period).data if reporting_period else None
        )
        return Response(data)


class OwnerSummaryAPIView(APIView):
    """Get high-level summary data for the data owner landing page."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Return a summary of emission modules and data quality for the current org unit.',
        responses={200: openapi.Response('OK', schema=openapi.Schema(type=openapi.TYPE_OBJECT))}
    )
    def get(self, request):
        data = OwnerService.get_owner_summary(request.user)
        if data is None:
            return Response({'detail': 'No accessible org units'}, status=403)
        return Response(data)


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
        search = request.query_params.get('search')
        scope = request.query_params.get('scope')
        data = OwnerService.get_owner_assets(request.user, search=search, scope=scope)
        if data is None:
            return Response({'detail': 'No accessible org units'}, status=403)
        return Response(data)


class OwnerActivityAPIView(APIView):
    """Return recent emission submission activity for the current owner org unit."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Return recent emission activity for the current org unit.',
        responses={200: openapi.Response('OK', schema=openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)))}
    )
    def get(self, request):
        data = OwnerService.get_owner_activity(request.user)
        if data is None:
            return Response({'detail': 'No accessible org units'}, status=403)
        return Response(data)


class MyDataAPIView(APIView):
    """
    Consolidated My Data endpoint for Data Owner workspace.

    GET /api/v1/emissions/my-data/

    Returns org unit context, stats, modules, and recent activity
    in a single response — the only endpoint the My Data page calls.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = MyDataService.get_my_data(request.user)
        if data is None:
            return Response({'detail': 'No accessible org units'}, status=403)
        return Response(data)


class ConsoleAPIView(APIView):
    """
    Aggregated console data for the Carbon landing page.

    GET /api/v1/emissions/console/

    Returns active reporting period, stats, alerts, and recent activity
    in a single response — the only endpoint the Console page calls.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ConsoleService.get_console_data(request.user)
        return Response(data)
