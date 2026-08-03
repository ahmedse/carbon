# File: emissions/views.py
# REST API Views for Emission Factor Calculator.
# Business logic lives in emissions/services.py — views are thin.

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission, SAFE_METHODS
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Count, Q, Max
from django.utils import timezone
from decimal import Decimal
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from .models import ReportingPeriod, EmissionFactor, GWP, Calculation, CalculationRule, ReportConfig, SBTiTarget, VerificationRecord, CalculationAudit
from accounts.rbac_utils import get_visible_module_ids, get_visible_org_units, user_is_global_admin
from accounts.constants import ADMINS_GROUP
from core.models import Module
from catalog.permissions import AdminOrSuperuserOnly, ReadAnyWriteAdmin
from dataschema.models import DataRow, DataTable
from .serializers import (
    ReportingPeriodSerializer,
    EmissionFactorSerializer,
    EmissionFactorSummarySerializer,
    GWPSerializer,
    CalculationSerializer,
    CalculationRuleSerializer,
    ReportConfigSerializer,
    SBTiTargetSerializer,
    VerificationRecordSerializer,
    CalculationAuditSerializer,
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
    VerificationService,
    PeriodLockService,
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
    permission_classes = [ReadAnyWriteAdmin]
    
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

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit period for verification. Delegates to VerificationService."""
        period = self.get_object()
        try:
            VerificationService.submit(period, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ReportingPeriodSerializer(period).data)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a submitted period (admin only). Delegates to VerificationService."""
        period = self.get_object()
        try:
            VerificationService.verify(period, request.user)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ReportingPeriodSerializer(period).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a submitted period with notes (admin only). Delegates to VerificationService."""
        period = self.get_object()
        notes = request.data.get('notes', '')
        try:
            VerificationService.reject(period, request.user, notes)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ReportingPeriodSerializer(period).data)

    @action(detail=True, methods=['post'])
    def open(self, request, pk=None):
        """Open a period for data entry (from draft or locked). Delegates to PeriodLockService."""
        period = self.get_object()
        try:
            PeriodLockService.open_period(period, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ReportingPeriodSerializer(period).data)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Lock a period for review. Locks linked tables. Delegates to PeriodLockService."""
        period = self.get_object()
        try:
            PeriodLockService.lock_period(period, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ReportingPeriodSerializer(period).data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a verified period. Delegates to PeriodLockService."""
        period = self.get_object()
        try:
            PeriodLockService.close_period(period, request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(ReportingPeriodSerializer(period).data)


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


class GWPViewSet(viewsets.ModelViewSet):
    """ViewSet for Global Warming Potentials (CRUD)."""
    queryset = GWP.objects.all()
    serializer_class = GWPSerializer
    permission_classes = [AdminOrSuperuserOnly]


class CalculationWritePermission(BasePermission):
    """
    Read: any authenticated user can list/view calculations.
    Write (create/update/delete): requires admins_group or analysts_group role
    on the target module, or global admin.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        # Write requires admin or analyst role on the module
        if user.is_superuser or user_is_global_admin(user):
            return True
        # DRF serializers use the FK field name 'module', but callers may also
        # pass 'module_id' as a query param or data key.
        module_id = (
            request.data.get('module_id') or request.query_params.get('module_id') or
            request.data.get('module') or request.query_params.get('module')
        )
        if not module_id:
            return False
        from accounts.rbac_utils import user_has_module_role
        return user_has_module_role(user, module_id, [ADMINS_GROUP, "analysts_group"])


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
    permission_classes = [IsAuthenticated, CalculationWritePermission]
    
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
        detail = request.query_params.get('detail', '').lower() in ('true', '1', 'yes')
        if detail:
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return Response({
            'count': queryset.count(),
            'results': list(queryset.values(
                'id', 'module_id', 'module__name',
                'reporting_year', 'reporting_period_id',
                'scope', 'co2e_kg', 'category',
                'emission_factor__name', 'emission_factor__code',
                'emission_factor_id',
                'calculated_at', 'activity_date',
                'data_row_id',
            ))
        })

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """Re-run a single calculation with its existing parameters."""
        calculation = self.get_object()

        # Gating: reject if period is locked/verified/closed (E2-B3 pattern)
        period = calculation.reporting_period
        if period and period.status in {'locked', 'verified', 'closed'}:
            return Response(
                {'detail': f'Reporting period is {period.status} and cannot be recalculated.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            updated = CalculationEngineService.recalculate(calculation)
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = self.get_serializer(updated)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def batch_recalculate(self, request):
        """Re-run calculations matching period_id, module_id, or explicit IDs."""
        period_id = request.data.get('period_id')
        module_id = request.data.get('module_id')
        calculation_ids = request.data.get('calculation_ids')

        if not period_id and not module_id and not calculation_ids:
            return Response(
                {'detail': 'Provide period_id, module_id, or calculation_ids.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Gating: reject if period is locked/verified/closed (E2-B3 pattern)
        if period_id:
            from .models import ReportingPeriod
            period = ReportingPeriod.objects.filter(id=period_id).first()
            if period and period.status in {'locked', 'verified', 'closed'}:
                return Response(
                    {'detail': f'Reporting period is {period.status} and cannot be recalculated.'},
                    status=status.HTTP_409_CONFLICT,
                )

        result = CalculationEngineService.batch_recalculate(
            period_id=period_id,
            module_id=module_id,
            calculation_ids=calculation_ids,
        )
        return Response(result)


class CalculationSummaryAPIView(APIView):
    """
    Aggregated summary of calculations.

    GET /emissions/calculations/summary/?reporting_period_id=N

    Returns period context, totals by scope/status/module, latest run time.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description='Return aggregated calculation summary for a reporting period.',
        manual_parameters=[
            openapi.Parameter('reporting_period_id', openapi.IN_QUERY, description='Filter by reporting period', type=openapi.TYPE_INTEGER),
        ],
        responses={200: openapi.Response('OK')}
    )
    def get(self, request):
        period_id = request.query_params.get('reporting_period_id')
        qs = scope_calculations(
            request.user,
            Calculation.objects.select_related('module', 'reporting_period', 'emission_factor')
        )
        if period_id:
            qs = qs.filter(reporting_period_id=period_id)

        total_calculations = qs.count()
        if total_calculations == 0:
            return Response({
                'period_id': int(period_id) if period_id else None,
                'total_calculations': 0,
                'by_scope': {},
                'by_status': {},
                'by_module': [],
                'latest_run_at': None,
                'last_audit': None,
            })

        by_scope_list = list(qs.values('scope').annotate(count=Count('id'), total_co2e_kg=Sum('co2e_kg')).values('scope', 'count', 'total_co2e_kg'))
        by_scope_dict = {}
        for item in by_scope_list:
            scope_val = item.pop('scope')
            by_scope_dict[scope_val] = item

        by_module_data = qs.values('module_id', 'module__name').annotate(
            count=Count('id'), total_co2e_kg=Sum('co2e_kg')
        ).order_by('-total_co2e_kg')
        by_module = [
            {
                'module_id': m['module_id'],
                'module_name': m['module__name'],
                'count': m['count'],
                'total_co2e_kg': float(m['total_co2e_kg'] or 0),
            }
            for m in by_module_data
        ]

        latest_run = qs.aggregate(latest=Max('calculated_at'))
        latest_run_at = latest_run['latest']

        last_audit = None
        if period_id:
            audit = CalculationAudit.objects.filter(
                reporting_period_id=period_id
            ).order_by('-triggered_at').first()
            if audit:
                last_audit = {
                    'id': audit.id,
                    'trigger_type': audit.trigger_type,
                    'triggered_by_name': audit.triggered_by.username if audit.triggered_by else None,
                    'triggered_at': audit.triggered_at,
                    'created_count': audit.created_count,
                    'skipped_count': audit.skipped_count,
                    'error_count': audit.error_count,
                }

        return Response({
            'period_id': int(period_id) if period_id else None,
            'total_calculations': total_calculations,
            'by_scope': by_scope_dict,
            'by_status': {},
            'by_module': by_module,
            'latest_run_at': latest_run_at,
            'last_audit': last_audit,
        })


class CalculationRuleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for calculation rules.
    
    Additional Actions:
    - POST /emissions/rules/{id}/execute/ - Run calculations for a rule
    """
    serializer_class = CalculationRuleSerializer
    permission_classes = [AdminOrSuperuserOnly]
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
    format_kwarg = None  # Let view handle format param directly

    def get(self, request):
        period_id = request.query_params.get('reporting_period_id')
        org_unit_id = request.query_params.get('org_unit_id')
        year = request.query_params.get('year', timezone.now().year)
        report_format = request.query_params.get('output_format', 'json')

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
        "rule_id": 1,           // Single rule
        "reporting_period_id": 1, // optional
        "recalculate": false
    }

    POST /emissions/calculate/  — recalculate ALL active rules
    {
        "recalculate": true
    }
    """
    permission_classes = [AdminOrSuperuserOnly]

    def post(self, request):
        rule_id = request.data.get('rule_id')
        period_id = request.data.get('reporting_period_id')
        recalculate = request.data.get('recalculate', False)

        # ── Recalculate-all mode: no rule_id, just recalculate=true ──
        if not rule_id and recalculate:
            return self._recalculate_all(request, period_id)

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

        # Audit trail
        CalculationAudit.objects.create(
            trigger_type='single',
            triggered_by=request.user,
            calculation_rule=rule,
            data_table=rule.data_table,
            reporting_period=period,
            recalculate=recalculate,
            created_count=created,
            skipped_count=skipped,
            error_count=err_count,
        )

        return Response({
            'success': True,
            'total_created': created,
            'total_skipped': skipped,
            'total_errors': err_count,
            'rule': rule.name,
        })

    def _recalculate_all(self, request, period_id):
        """Recalculate all active calculation rules. Used by the dashboard."""
        from emissions.models import CalculationRule

        rules = CalculationRule.objects.filter(is_active=True).select_related('data_table')
        if not rules.exists():
            return Response(
                {'error': 'No active calculation rules found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        total_created = 0
        total_skipped = 0
        total_errors = 0
        rules_processed = 0
        rule_results = []

        for rule in rules:
            _, period, errors = CalculationEngineService.validate_calculation_request(
                rule.id, period_id=period_id,
            )
            if errors:
                rule_results.append({'rule': rule.name, 'status': 'skipped', 'error': errors.get('rule_id', str(errors))})
                total_errors += 1
                continue

            created, skipped, err_count = CalculationEngineService.execute_rule(
                rule, reporting_period=period, user=request.user, recalculate=True,
            )

            CalculationAudit.objects.create(
                trigger_type='single',
                triggered_by=request.user,
                calculation_rule=rule,
                data_table=rule.data_table,
                reporting_period=period,
                recalculate=True,
                created_count=created,
                skipped_count=skipped,
                error_count=err_count,
            )

            total_created += created
            total_skipped += skipped
            total_errors += err_count
            rules_processed += 1
            rule_results.append({
                'rule': rule.name,
                'status': 'ok',
                'created': created,
                'skipped': skipped,
                'errors': err_count,
            })

        return Response({
            'success': True,
            'total_created': total_created,
            'total_skipped': total_skipped,
            'total_errors': total_errors,
            'rules_processed': rules_processed,
            'rule_results': rule_results,
        })


class BatchCalculateAPIView(APIView):
    """Run calculations across multiple tables at once."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description="Batch calculate emissions for multiple tables",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['table_ids', 'period_id'],
            properties={
                'table_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description="DataTable IDs to calculate",
                ),
                'period_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="ReportingPeriod ID",
                ),
            },
        ),
    )
    def post(self, request):
        table_ids = request.data.get('table_ids')
        period_id = request.data.get('period_id')

        if not table_ids or not isinstance(table_ids, list):
            return Response(
                {'detail': 'table_ids is required and must be a list of integers.'},
                status=400,
            )
        if not period_id:
            return Response(
                {'detail': 'period_id is required.'},
                status=400,
            )

        try:
            result = CalculationEngineService.batch_calculate(
                table_ids, period_id, user=request.user,
            )
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

        # Audit trail
        CalculationAudit.objects.create(
            trigger_type='batch',
            triggered_by=request.user,
            reporting_period_id=period_id,
            table_ids=table_ids,
            created_count=result.get('total_created', 0),
            skipped_count=result.get('total_skipped', 0),
            error_count=result.get('total_errors', 0),
        )

        return Response(result, status=200)


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


class SBTiTargetViewSet(viewsets.ModelViewSet):
    """CRUD for SBTi targets — org-scoped visibility."""
    serializer_class = SBTiTargetSerializer
    permission_classes = [AdminOrSuperuserOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        from accounts.rbac_utils import get_visible_org_units
        allowed = get_visible_org_units(self.request.user)
        if allowed is None:
            return SBTiTarget.objects.all()
        return SBTiTarget.objects.filter(org_unit_id__in=allowed)


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


class VerificationRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = VerificationRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = VerificationRecord.objects.select_related('reporting_period', 'verifier')
        period_id = self.request.query_params.get('period_id')
        if period_id:
            qs = qs.filter(reporting_period_id=period_id)
        return qs

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify the reporting period linked to this verification record."""
        record = self.get_object()
        try:
            VerificationService.verify(record.reporting_period, request.user)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        record.refresh_from_db()
        return Response(VerificationRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject the reporting period linked to this verification record."""
        record = self.get_object()
        notes = request.data.get('notes', '')
        try:
            VerificationService.reject(record.reporting_period, request.user, notes)
        except PermissionDenied as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        record.refresh_from_db()
        return Response(VerificationRecordSerializer(record).data)


class CalculationAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit trail for calculation triggers."""
    serializer_class = CalculationAuditSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CalculationAudit.objects.select_related(
            'triggered_by', 'calculation_rule', 'data_table', 'reporting_period'
        )
        trigger_type = self.request.query_params.get('trigger_type')
        if trigger_type:
            qs = qs.filter(trigger_type=trigger_type)
        period_id = self.request.query_params.get('period_id')
        if period_id:
            qs = qs.filter(reporting_period_id=period_id)
        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(triggered_by_id=user_id)
        return qs
