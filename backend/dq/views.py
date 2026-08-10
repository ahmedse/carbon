# dq/views.py
import logging
import time
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

from .models import TableProfile, FieldProfile, DQRule, DQResult
from .models import FreshnessCheck, SchemaSnapshot, SchemaChange, RuleTag, RuleFieldAssignment
from .serializers import (
    TableProfileSerializer, FieldProfileSerializer, DQRuleSerializer, DQResultSerializer,
    FreshnessCheckSerializer, SchemaSnapshotSerializer, SchemaChangeSerializer,
    RuleTagSerializer, RuleFieldAssignmentSerializer,
)
from accounts.permissions import ReadAnyWriteGlobalAdmin, ReadScopedWriteAdmin, AdminOrSuperuserOnly
from accounts.rbac_utils import get_allowed_org_unit_ids, user_has_global_role, get_allowed_module_ids
from accounts.models import ScopedRole
from .services import profile_table, run_dq, run_single_rule, bulk_profile
from .rule_schema import DIMENSIONS
from dataschema.models import DataTable, DataField


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

def _get_user_org_units(user):
    return ScopedRole.objects.filter(
        user=user, is_active=True
    ).values_list('org_unit_id', flat=True).distinct()


def _check_table_access(user, table):
    """Raise PermissionDenied if user cannot access this table."""
    if user.is_superuser or user.is_staff:
        return
    org_units = _get_user_org_units(user)
    if table.module.org_unit_id not in list(org_units):
        raise PermissionDenied("You don't have access to this table's org unit.")


def _check_rule_access(user, rule):
    """Raise PermissionDenied if user cannot access this rule's data."""
    if user.is_superuser or user.is_staff:
        return
    org_units = list(_get_user_org_units(user))
    # Check through RuleFieldAssignment M2M
    assignments = rule.field_assignments.select_related('data_table__module').all()
    has_access = any(
        a.data_table.module.org_unit_id in org_units for a in assignments
    )
    if not has_access:
        raise PermissionDenied("You don't have access to this rule's data.")


# ---------------------------------------------------------------------------
# Read-only ViewSets (field/table profiles)
# ---------------------------------------------------------------------------

class FieldProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FieldProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['data_field__name']
    ordering_fields = ['profiled_at', 'completeness_pct']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return FieldProfile.objects.none()
        # Optimize: select_related the FK chain the serializer touches
        # (data_field.name + org-scope filters on data_field__data_table__module)
        qs = FieldProfile.objects.select_related(
            'data_field__data_table__module',
        )
        user = self.request.user
        if user.is_superuser or user.is_staff:
            pass
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return FieldProfile.objects.none()
            qs = qs.filter(data_field__data_table__module__org_unit_id__in=org_units)
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_field__data_table_id=p['data_table'])
        if p.get('data_field'):
            qs = qs.filter(data_field_id=p['data_field'])
        return qs.distinct()


class TableProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TableProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['data_table__name']
    ordering_fields = ['profiled_at', 'completeness_pct']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TableProfile.objects.none()
        # Optimize: select_related the FK chain the serializer touches
        # (data_table.name + org-scope filters on data_table__module)
        qs = TableProfile.objects.select_related(
            'data_table__module',
        )
        user = self.request.user
        if user.is_superuser or user.is_staff:
            pass
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return TableProfile.objects.none()
            qs = qs.filter(data_table__module__org_unit_id__in=org_units)
        if self.request.query_params.get('data_table'):
            qs = qs.filter(data_table_id=self.request.query_params['data_table'])
        return qs.distinct()


# ---------------------------------------------------------------------------
# DQRule CRUD + execute + history actions
# ---------------------------------------------------------------------------

class DQRuleViewSet(viewsets.ModelViewSet):
    serializer_class = DQRuleSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteGlobalAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'rule_type']
    ordering_fields = ['created_at', 'name', 'severity', 'rule_level']
    filterset_fields = ['rule_level', 'rule_type', 'severity', 'is_active', 'dimension', 'archived']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DQRule.objects.none()
        # Optimize: prefetch M2M through tables + tags
        include_archived = self.request.query_params.get('include_archived') == '1'
        base_qs = DQRule.objects.prefetch_related(
            'field_assignments__data_table__module',
            'field_assignments__data_field',
            'tags',
            'results',
        ).select_related('created_by')
        if not include_archived:
            base_qs = base_qs.filter(archived=False)
        user = self.request.user
        if user.is_superuser or user.is_staff:
            qs = base_qs
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return DQRule.objects.none()
            qs = base_qs.filter(
                field_assignments__data_table__module__org_unit_id__in=org_units
            )
        p = self.request.query_params
        if p.get('rule_level'):
            qs = qs.filter(rule_level=p['rule_level'])
        if p.get('rule_type'):
            qs = qs.filter(rule_type=p['rule_type'])
        if p.get('tag'):
            qs = qs.filter(tags__id=p['tag'])
        if p.get('data_table'):
            qs = qs.filter(field_assignments__data_table_id=p['data_table'])
        if p.get('data_field'):
            qs = qs.filter(field_assignments__data_field_id=p['data_field'])
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        rule = self.get_object()
        results_count = rule.results.count()
        if results_count > 0:
            # Archive instead of hard-deleting when results exist.
            # Use update() to bypass the save() override which would
            # resync is_active from definition.active.
            DQRule.objects.filter(pk=rule.pk).update(
                archived=True, is_active=False,
                updated_at=timezone.now(),
            )
            return Response(
                {
                    'archived': True,
                    'results_count': results_count,
                    'detail': f'Rule archived. {results_count} historical results preserved.',
                },
                status=status.HTTP_200_OK,
            )
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description='Execute a single data quality rule and return the resulting DQ result.',
        responses={201: 'DQ result created', 400: 'Invalid request', 404: 'Rule not found'},
    )
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """POST /dq/rules/{id}/execute/ — Execute this rule."""
        rule = self.get_object()
        _check_rule_access(request.user, rule)
        result_list = run_single_rule(rule.id, user=request.user)
        return Response(result_list, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description='Return the recent execution history for a data quality rule.',
        responses={200: 'Recent execution history', 404: 'Rule not found'},
    )
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """GET /dq/rules/{id}/history/ — Last 10 runs with trend analysis."""
        rule = self.get_object()
        _check_rule_access(request.user, rule)
        runs_qs = rule.results.order_by('-run_at')[:10]
        runs = list(runs_qs)
        run_data = [
            {'run_at': r.run_at.isoformat(), 'passed': r.passed, 'score': r.score}
            for r in runs
        ]
        trend = 'stable'
        if len(runs) >= 4:
            latest = runs[0].score
            prev_avg = sum(r.score for r in runs[1:4]) / 3
            if latest > prev_avg:
                trend = 'improving'
            elif latest < prev_avg:
                trend = 'degrading'
        return Response({
            'rule_id': rule.id,
            'rule_name': rule.name,
            'runs': run_data,
            'trend': trend,
        })

    @swagger_auto_schema(
        operation_description=(
            'Bulk-execute multiple DQ rules or all rules for a table. '
            'Provide either rule_ids (array) or data_table_id (int).'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'rule_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of DQRule IDs to execute',
                ),
                'data_table_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Run all active rules for this DataTable',
                ),
            },
        ),
        responses={
            200: openapi.Response(description='Bulk execution summary with total/passed/failed/results'),
            400: 'Neither rule_ids nor data_table_id provided',
        },
    )
    @action(detail=False, methods=['post'], url_path='bulk-execute')
    def bulk_execute(self, request):
        """POST /dq/rules/bulk-execute/ — Execute multiple rules at once."""
        rule_ids = request.data.get('rule_ids')
        table_id = request.data.get('data_table_id')

        if not rule_ids and not table_id:
            return Response(
                {'error': 'Either rule_ids (array) or data_table_id (int) is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve rules
        if rule_ids:
            if not isinstance(rule_ids, list):
                return Response(
                    {'error': 'rule_ids must be an array of integers'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rules = DQRule.objects.filter(
                id__in=rule_ids, is_active=True
            ).prefetch_related('field_assignments__data_field', 'field_assignments__data_table')
        else:
            try:
                table = DataTable.objects.get(id=table_id)
            except DataTable.DoesNotExist:
                return Response(
                    {'error': f'Table {table_id} not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            _check_table_access(request.user, table)
            field_ids = list(table.fields.values_list('id', flat=True))
            rules = DQRule.objects.filter(is_active=True).filter(
                Q(field_assignments__data_table_id=table_id) |
                Q(field_assignments__data_field_id__in=field_ids)
            ).prefetch_related('field_assignments__data_field', 'field_assignments__data_table')

        if not rules.exists():
            return Response({
                'total': 0, 'passed': 0, 'failed': 0, 'results': [],
                'message': 'No active rules found to execute',
            })

        results = []
        passed = 0
        failed = 0
        for rule in rules:
            _check_rule_access(request.user, rule)
            try:
                result_list = run_single_rule(rule.id, user=request.user)
                for result in result_list:
                    results.append(result)
                    if result['passed']:
                        passed += 1
                    else:
                        failed += 1
            except Exception as exc:
                results.append({
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'passed': False,
                    'error': str(exc),
                })
                failed += 1

        return Response({
            'total': len(results),
            'passed': passed,
            'failed': failed,
            'results': results,
        })


# ---------------------------------------------------------------------------
# DQResult read + failures action
# ---------------------------------------------------------------------------

class DQResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DQResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['run_at', 'score', 'passed']
    ordering = ['-run_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DQResult.objects.none()
        
        # Optimize with select_related to avoid N+1 queries
        qs = DQResult.objects.select_related(
            'rule__created_by', 'data_field', 'data_field__data_table'
        )
        
        user = self.request.user
        if user.is_superuser or user.is_staff:
            pass  # Use full queryset
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return DQResult.objects.none()
            qs = qs.filter(
                Q(rule__field_assignments__data_table__module__org_unit_id__in=org_units) |
                Q(rule__field_assignments__data_field__data_table__module__org_unit_id__in=org_units)
            )
        
        p = self.request.query_params
        if p.get('rule_id'):
            qs = qs.filter(rule_id=p['rule_id'])
        elif p.get('rule'):
            qs = qs.filter(rule_id=p['rule'])
        if p.get('data_table_id'):
            qs = qs.filter(
                Q(rule__field_assignments__data_table_id=p['data_table_id']) |
                Q(rule__field_assignments__data_field__data_table_id=p['data_table_id'])
            )
        if p.get('passed') is not None:
            if p['passed'].lower() == 'true':
                qs = qs.filter(passed=True)
            elif p['passed'].lower() == 'false':
                qs = qs.filter(passed=False)
        return qs.order_by('-run_at').distinct()

    @swagger_auto_schema(
        operation_description='Return a paged list of DQ execution results for the current scope.',
        responses={200: 'List of DQ results'},
    )
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @swagger_auto_schema(
        operation_description='Return a sample of failed rows and reasons for a DQ execution result.',
        responses={200: 'Sample failures', 404: 'Result not found'},
    )
    @action(detail=True, methods=['get'])
    def failures(self, request, pk=None):
        """GET /dq/results/{id}/failures/ — Sample failures with context."""
        result = self.get_object()
        _check_rule_access(request.user, result.rule)
        rule = result.rule
        field_name = None
        first_assn = rule.field_assignments.select_related('data_field').first()
        if first_assn and first_assn.data_field:
            field_name = first_assn.data_field.name
        raw_failures = result.sample_failures[:100]
        failures = []
        for f in raw_failures:
            failures.append({
                'row_id': f.get('row'),
                'row_display': f"Row {f.get('row', '?')}",
                'field_name': field_name,
                'value': f.get('value'),
                'reason': f.get('reason', f"Rule '{rule.rule_type}' violation"),
            })
        return Response({
            'result_id': result.id,
            'rule_name': rule.name,
            'rule_type': rule.rule_type,
            'failed_count': result.failed_count,
            'sample_size': len(failures),
            'failures': failures,
        })


# ---------------------------------------------------------------------------
# Profile action endpoints (A2)
# ---------------------------------------------------------------------------

class ProfileTriggerView(APIView):
    """POST /dq/profile/ — Profile a single table."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description=(
            'Profile a single data table, computing row count, completeness, null counts, '
            'and uniqueness for each field. Results are persisted as TableProfile / FieldProfile records.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data_table_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the DataTable to profile'),
            },
            required=['data_table_id'],
        ),
        responses={
            200: openapi.Response(description='Profile result with row count and per-field stats'),
            400: 'data_table_id is required',
            403: 'Not authorized for this table',
            404: 'Table not found',
        },
    )
    def post(self, request):
        table_id = request.data.get('data_table_id') or request.data.get('data_table')
        correlation_id = getattr(request, 'correlation_id', 'unknown')
        
        if not table_id:
            logger.warning(
                "DQ profiling triggered without table_id",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": request.user.id if request.user.is_authenticated else None,
                    "action": "dq_profile_missing_param",
                }
            )
            return Response({'error': 'data_table_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(
            "DQ profiling triggered",
            extra={
                "correlation_id": correlation_id,
                "user_id": request.user.id,
                "table_id": table_id,
                "action": "dq_profile_start",
            }
        )
        
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            logger.warning(
                "DQ profiling table not found",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "user_id": request.user.id,
                    "action": "dq_profile_table_not_found",
                }
            )
            return Response(
                {
                    "error": "TableNotFound",
                    "message": f"DataTable with ID {table_id} does not exist",
                    "details": {
                        "table_id": [f"No table found with ID {table_id}. Verify the ID or check if the table was archived."]
                    },
                    "suggested_action": "Use GET /dataschema/tables/ to list available tables",
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            _check_table_access(request.user, table)
        except PermissionDenied:
            logger.warning(
                "DQ profiling permission denied",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "user_id": request.user.id,
                    "action": "dq_profile_permission_denied",
                }
            )
            raise
        
        # Check if table has data
        row_count = table.rows.filter(is_archived=False).count()
        if row_count == 0:
            logger.info(
                "DQ profiling skipped - empty table",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "user_id": request.user.id,
                    "action": "dq_profile_empty_table",
                }
            )
            return Response(
                {
                    "error": "EmptyTable",
                    "message": f"Table '{table.name}' has no data rows to profile",
                    "details": {
                        "table_id": [f"Table {table_id} exists but contains 0 rows. Add data before profiling."]
                    },
                    "suggested_action": "Import data via POST /dataschema/rows/bulk-import/ first",
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start = time.time()
        try:
            result = profile_table(table_id)
            duration = time.time() - start
            
            logger.info(
                "DQ profiling completed",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "user_id": request.user.id,
                    "duration_ms": round(duration * 1000, 2),
                    "row_count": result.get('row_count', 0),
                    "field_count": result.get('field_count', 0),
                    "action": "dq_profile_success",
                }
            )
            return Response(result)
        except Exception as exc:
            duration = time.time() - start
            logger.error(
                "DQ profiling failed",
                extra={
                    "correlation_id": correlation_id,
                    "table_id": table_id,
                    "user_id": request.user.id,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "action": "dq_profile_error",
                },
                exc_info=True
            )
            return Response(
                {
                    "error": "ProfilingFailed",
                    "message": f"An error occurred while profiling table {table_id}",
                    "details": {"error": [str(exc)]},
                    "suggested_action": "Check server logs for details or contact administrator",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BulkProfileView(APIView):
    """POST /dq/profile/bulk/ — Profile multiple tables."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description=(
            'Profile multiple data tables in a single request. '
            'Non-admin users have inaccessible tables silently skipped. '
            'Returns total/success/failed counts plus per-table results.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data_table_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of DataTable IDs to profile',
                ),
            },
            required=['data_table_ids'],
        ),
        responses={
            200: openapi.Response(description='Bulk profile result with total/success/failed counts and per-table results'),
            400: 'data_table_ids must be a non-empty list',
        },
    )
    def post(self, request):
        table_ids = request.data.get('data_table_ids', [])
        if not isinstance(table_ids, list) or not table_ids:
            return Response({'error': 'data_table_ids must be a non-empty list'}, status=status.HTTP_400_BAD_REQUEST)
        # RBAC: check each table; skip inaccessible ones for non-staff
        user = request.user
        accessible_ids = []
        for tid in table_ids:
            try:
                table = DataTable.objects.get(id=tid)
                _check_table_access(user, table)
                accessible_ids.append(tid)
            except DataTable.DoesNotExist:
                accessible_ids.append(tid)  # will fail gracefully in bulk_profile
            except PermissionDenied:
                pass  # silently skip inaccessible tables for non-staff
        return Response(bulk_profile(accessible_ids, user=user))


class DQRunView(APIView):
    """POST /dq/run/ — Run a single rule (rule_id) or all rules for a table (data_table_id)."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description=(
            'Run DQ rules and record results. Provide either:\n'
            '- `rule_id` to execute a single rule\n'
            '- `data_table_id` to run all active rules scoped to that table\n\n'
            'Results are persisted as DQResult records and written back to AssetProfile quality_status/quality_score.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'rule_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of a specific DQRule to execute'),
                'data_table_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Run all active rules for this DataTable'),
            },
        ),
        responses={
            200: openapi.Response(description='DQ run result with passed/score/rules_run counts'),
            400: 'Neither rule_id nor data_table_id provided',
            403: 'Not authorized for this rule or table',
            404: 'Rule or table not found',
        },
    )
    def post(self, request):
        rule_id = request.data.get('rule_id')
        table_id = request.data.get('data_table_id') or request.data.get('data_table')

        if rule_id:
            try:
                rule = DQRule.objects.prefetch_related('field_assignments__data_field',
                    'field_assignments__data_table').get(id=rule_id)
            except DQRule.DoesNotExist:
                return Response({'error': f'Rule {rule_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            _check_rule_access(request.user, rule)
            try:
                return Response(run_single_rule(rule_id, user=request.user))
            except Exception as exc:
                return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if table_id:
            try:
                table = DataTable.objects.get(id=table_id)
            except DataTable.DoesNotExist:
                return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            _check_table_access(request.user, table)
            try:
                return Response(run_dq(table_id, user=request.user))
            except Exception as exc:
                return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {'error': 'Either rule_id or data_table_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )


# ---------------------------------------------------------------------------
# Metrics views (existing — kept for compatibility)
# ---------------------------------------------------------------------------

class DQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/ - Org-scoped DQ summary"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            'Return aggregated DQ metrics for the authenticated user\'s org scope: '
            'total tables profiled, total rows, and weighted completeness percentage.'
        ),
        responses={200: openapi.Response(description='DQ metrics summary (table_count, total_rows, completeness_pct)')},
    )
    def get(self, request):
        user = request.user
        if user.is_superuser or user.is_staff:
            profiles = TableProfile.objects.all()
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                profiles = TableProfile.objects.none()
            else:
                profiles = TableProfile.objects.filter(
                    data_table__module__org_unit_id__in=org_units
                )
        total_rows = sum(p.row_count for p in profiles)
        if total_rows > 0:
            weighted_completeness = sum(
                p.completeness_pct * p.row_count for p in profiles
            ) / total_rows
        else:
            weighted_completeness = 0.0
        
        # Add rule-level metrics
        from .models import DQRule, DQResult
        if user.is_superuser or user.is_staff:
            rules = DQRule.objects.filter(is_active=True)
            results = DQResult.objects.all()
        else:
            org_units = _get_user_org_units(user)
            rules = DQRule.objects.filter(
                field_assignments__data_table__module__org_unit_id__in=org_units,
                is_active=True,
            ).distinct()
            results = DQResult.objects.filter(
                rule__field_assignments__data_table__module__org_unit_id__in=org_units,
            ).distinct()
        
        total_rules = rules.count()
        latest_results = results.order_by('rule_id', '-run_at').distinct('rule_id')
        passing_rules = latest_results.filter(passed=True).count()
        failing_rules = latest_results.filter(passed=False).count()
        overall_score = round(passing_rules / total_rules * 100, 1) if total_rules > 0 else 0.0
        
        # Per-dimension scores: group rules by dimension, average latest DQResult.score
        scores_by_dimension = {}
        dim_rules = {}
        for rule in rules:
            dim_rules.setdefault(rule.dimension or 'validity', []).append(rule.id)

        for dim_code, _dim_label in DIMENSIONS:
            dim_rule_ids = dim_rules.get(dim_code, [])
            if not dim_rule_ids:
                continue
            dim_results = [r for r in latest_results if r.rule_id in dim_rule_ids]
            if dim_results:
                scores_by_dimension[dim_code] = round(
                    sum(r.score for r in dim_results) / len(dim_results), 1
                )
            else:
                scores_by_dimension[dim_code] = None

        return Response({
            'table_count': profiles.count(),
            'total_rows': total_rows,
            'completeness_pct': round(weighted_completeness, 2),
            'total_rules': total_rules,
            'passing_rules': passing_rules,
            'failing_rules': failing_rules,
            'overall_score': overall_score,
            'scores_by_dimension': scores_by_dimension,
        })


class TableDQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/table/{tableId}/ - Table-level DQ metrics"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            'Return DQ metrics for a specific table: row count, completeness percentage, '
            'per-field profiles, and all active DQ rules scoped to this table.'
        ),
        responses={
            200: openapi.Response(description='Table-level DQ metrics with field profiles and active rules'),
            403: 'Not authorized for this table',
            404: 'Table not found',
        },
    )
    def get(self, request, table_id):
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        _check_table_access(request.user, table)
        profile = TableProfile.objects.filter(data_table=table).first()
        rules = DQRule.objects.filter(
            Q(field_assignments__data_table=table) | Q(field_assignments__data_field__data_table=table), is_active=True
        ).distinct()
        field_profiles = FieldProfile.objects.filter(data_field__data_table=table)

        # Compute rule-level stats from latest DQResults
        total_rules = len(rules)
        failing_rules = 0
        latest_scores = []
        if total_rules > 0:
            from django.db.models import OuterRef, Subquery
            latest_results = DQResult.objects.filter(
                rule=OuterRef('pk')
            ).order_by('-run_at')
            rule_ids = [r.id for r in rules]
            for rule_id in rule_ids:
                latest = DQResult.objects.filter(rule_id=rule_id).order_by('-run_at').first()
                if latest:
                    if not latest.passed:
                        failing_rules += 1
                    latest_scores.append(latest.score)

        overall_score = (
            round(sum(latest_scores) / len(latest_scores))
            if latest_scores else 0
        )

        return Response({
            'table_id': table.id,
            'table_name': table.name,
            'row_count': profile.row_count if profile else 0,
            'completeness_pct': profile.completeness_pct if profile else 0,
            'total_rules': total_rules,
            'failing_rules': failing_rules,
            'score': overall_score,
            'field_profiles': FieldProfileSerializer(field_profiles, many=True).data,
            'active_rules': DQRuleSerializer(rules, many=True).data,
        })


class FieldDQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/field/{fieldId}/ - Field-level DQ metrics"""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description=(
            'Return DQ metrics for a specific field: null count, completeness percentage, '
            'uniqueness percentage, and all active DQ rules targeting this field.'
        ),
        responses={
            200: openapi.Response(description='Field-level DQ metrics with active rules'),
            403: 'Not authorized for this field',
            404: 'Field not found',
        },
    )
    def get(self, request, field_id):
        try:
            field = DataField.objects.get(id=field_id)
        except DataField.DoesNotExist:
            return Response({'error': f'Field {field_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        if not (user.is_superuser or user.is_staff):
            org_units = list(_get_user_org_units(user))
            if field.data_table.module.org_unit_id not in org_units:
                raise PermissionDenied("Not authorized for this field")
        profile = FieldProfile.objects.filter(data_field=field).first()
        rules = DQRule.objects.filter(field_assignments__data_field=field, is_active=True).distinct()
        return Response({
            'field_id': field.id,
            'field_name': field.name,
            'null_count': profile.null_count if profile else 0,
            'completeness_pct': profile.completeness_pct if profile else 0,
            'uniqueness_pct': profile.uniqueness_pct if profile else 0,
            'active_rules': DQRuleSerializer(rules, many=True).data,
        })


class RunDQValidationView(APIView):
    """POST /carbon-api/dq/run-validation/ - Trigger DQ check for table (legacy alias)."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description=(
            'Legacy alias for POST /dq/run/ with data_table. '
            'Run all active DQ rules against a table and return a summary. '
            'Prefer POST /dq/run/ for new integrations.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data_table': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the DataTable to validate'),
            },
            required=['data_table'],
        ),
        responses={
            200: openapi.Response(description='Validation complete with status and result summary'),
            400: 'data_table is required',
            404: 'Table not found',
        },
    )
    def post(self, request):
        table_id = request.data.get('data_table')
        if not table_id:
            return Response({'error': 'data_table is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        _check_table_access(request.user, table)
        try:
            result = run_dq(table_id, user=request.user)
            return Response({'status': 'complete', 'message': 'DQ validation completed', 'result': result})
        except Exception as exc:
            return Response({'status': 'error', 'message': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# AI-suggested DQ rules via Pulse
# ---------------------------------------------------------------------------

class DQSuggestView(APIView):
    """POST /carbon-api/dq/suggest/ — Get AI-suggested DQ rules for a table."""
    permission_classes = [AdminOrSuperuserOnly]

    @swagger_auto_schema(
        operation_description=(
            'Ask Pulse AI to suggest NL-based DQ rules for a table, '
            'using its current profile (field statistics, distributions). '
            'Returns a list of suggestions with prompts, rationale, severity, and confidence.'
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'data_table_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the DataTable to suggest rules for',
                ),
            },
            required=['data_table_id'],
        ),
        responses={
            200: openapi.Response(description='Suggestions with prompts and rationale'),
            400: 'data_table_id is required',
            404: 'Table not found',
        },
    )
    def post(self, request):
        table_id = request.data.get('data_table_id')
        if not table_id:
            return Response(
                {'error': 'data_table_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': f'Table {table_id} not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        _check_table_access(request.user, table)

        from dq.services import suggest_rules_for_table

        try:
            result = suggest_rules_for_table(table_id)
        except Exception as exc:
            logger.error('Suggest failed for table %s: %s', table_id, exc)
            return Response(
                {'error': 'Suggest failed', 'detail': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if result['status'] == 'pulse_unavailable':
            return Response(
                {
                    'table_id': table_id,
                    'status': 'pulse_unavailable',
                    'suggestions': [],
                    'message': 'Pulse AI is currently unavailable. Please try again later.',
                },
                status=status.HTTP_200_OK,  # 200 not 503 — soft failure
            )

        return Response(result)


# ── Phase 1.8: Freshness & Schema Monitoring ViewSets ─────────────────────

class FreshnessCheckViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FreshnessCheckSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['checked_at', 'is_fresh']
    ordering = ['-checked_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return FreshnessCheck.objects.none()
        qs = FreshnessCheck.objects.select_related('data_table__module')
        user = self.request.user
        if user.is_superuser or user.is_staff:
            pass
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return FreshnessCheck.objects.none()
            qs = qs.filter(data_table__module__org_unit_id__in=org_units)
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_table_id=p['data_table'])
        if p.get('is_fresh') is not None:
            qs = qs.filter(is_fresh=p['is_fresh'].lower() == 'true')
        return qs.distinct()


class SchemaSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SchemaSnapshotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['snapshot_at', 'row_count']
    ordering = ['-snapshot_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SchemaSnapshot.objects.none()
        qs = SchemaSnapshot.objects.select_related('data_table__module')
        user = self.request.user
        if user.is_superuser or user.is_staff:
            pass
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return SchemaSnapshot.objects.none()
            qs = qs.filter(data_table__module__org_unit_id__in=org_units)
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_table_id=p['data_table'])
        return qs.distinct()


class SchemaChangeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SchemaChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['detected_at', 'change_type']
    ordering = ['-detected_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SchemaChange.objects.none()
        qs = SchemaChange.objects.select_related('data_table__module')
        user = self.request.user
        if user.is_superuser or user.is_staff:
            pass
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return SchemaChange.objects.none()
            qs = qs.filter(data_table__module__org_unit_id__in=org_units)
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_table_id=p['data_table'])
        if p.get('change_type'):
            qs = qs.filter(change_type=p['change_type'])
        return qs.distinct()


# ── Rule Tags & Field Assignments ─────────────────────────────────────────

class RuleTagViewSet(viewsets.ModelViewSet):
    """Full CRUD for rule categorization tags."""
    queryset = RuleTag.objects.all()
    serializer_class = RuleTagSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteGlobalAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


class RuleFieldAssignmentViewSet(viewsets.ModelViewSet):
    """Create/delete field assignments for a DQ rule.

    POST   /dq/rule-assignments/  {rule, data_field?, data_table}
    DELETE /dq/rule-assignments/{id}/
    """
    queryset = RuleFieldAssignment.objects.select_related('data_table__module', 'data_field')
    serializer_class = RuleFieldAssignmentSerializer
    permission_classes = [IsAuthenticated, ReadAnyWriteGlobalAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['rule__name', 'data_field__name', 'data_table__name']
    ordering_fields = ['data_table__name', 'data_field__name']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return qs
        org_units = _get_user_org_units(user)
        if not org_units:
            return RuleFieldAssignment.objects.none()
        return qs.filter(data_table__module__org_unit_id__in=org_units)



