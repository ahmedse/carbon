# dq/views.py
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound
from django.db.models import Q

from .models import TableProfile, FieldProfile, DQRule, DQResult
from .serializers import (
    TableProfileSerializer, FieldProfileSerializer, DQRuleSerializer, DQResultSerializer,
)
from accounts.permissions import ReadAnyWriteGlobalAdmin, ReadScopedWriteAdmin
from accounts.rbac_utils import get_allowed_org_unit_ids, user_has_global_role, get_allowed_module_ids
from accounts.models import ScopedRole
from .services import profile_table, run_dq, run_single_rule, bulk_profile
from .executor import DQRuleExecutor
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
    has_access = False
    if rule.data_field_id and rule.data_field:
        has_access = rule.data_field.data_table.module.org_unit_id in org_units
    elif rule.data_table_id and rule.data_table:
        has_access = rule.data_table.module.org_unit_id in org_units
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
        qs = FieldProfile.objects.all()
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
        qs = TableProfile.objects.all()
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
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'params']
    ordering_fields = ['created_at', 'name', 'severity']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            qs = DQRule.objects.filter(is_active=True)
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return DQRule.objects.none()
            qs = DQRule.objects.filter(is_active=True).filter(
                Q(data_field__data_table__module__org_unit_id__in=org_units) |
                Q(data_table__module__org_unit_id__in=org_units)
            )
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(Q(data_table_id=p['data_table']) | Q(data_field__data_table_id=p['data_table']))
        if p.get('data_field'):
            qs = qs.filter(data_field_id=p['data_field'])
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """POST /dq/rules/{id}/execute/ — Execute this rule."""
        rule = self.get_object()
        _check_rule_access(request.user, rule)
        executor = DQRuleExecutor(rule)
        result = executor.execute()
        return Response(DQResultSerializer(result).data, status=status.HTTP_201_CREATED)

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
        user = self.request.user
        if user.is_superuser or user.is_staff:
            qs = DQResult.objects.all()
        else:
            org_units = _get_user_org_units(user)
            if not org_units:
                return DQResult.objects.none()
            qs = DQResult.objects.filter(
                Q(rule__data_field__data_table__module__org_unit_id__in=org_units) |
                Q(rule__data_table__module__org_unit_id__in=org_units)
            )
        p = self.request.query_params
        if p.get('rule_id'):
            qs = qs.filter(rule_id=p['rule_id'])
        elif p.get('rule'):
            qs = qs.filter(rule_id=p['rule'])
        if p.get('data_table_id'):
            qs = qs.filter(
                Q(rule__data_table_id=p['data_table_id']) |
                Q(rule__data_field__data_table_id=p['data_table_id'])
            )
        if p.get('passed') is not None:
            if p['passed'].lower() == 'true':
                qs = qs.filter(passed=True)
            elif p['passed'].lower() == 'false':
                qs = qs.filter(passed=False)
        return qs.distinct()

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        limit = min(int(request.query_params.get('limit', 50)), 200)
        page = self.paginate_queryset(qs[:limit])
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs[:limit], many=True).data)

    @action(detail=True, methods=['get'])
    def failures(self, request, pk=None):
        """GET /dq/results/{id}/failures/ — Sample failures with context."""
        result = self.get_object()
        _check_rule_access(request.user, result.rule)
        rule = result.rule
        field_name = rule.data_field.name if rule.data_field else None
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        table_id = request.data.get('data_table_id') or request.data.get('data_table')
        if not table_id:
            return Response({'error': 'data_table_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        _check_table_access(request.user, table)
        try:
            return Response(profile_table(table_id))
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkProfileView(APIView):
    """POST /dq/profile/bulk/ — Profile multiple tables."""
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        rule_id = request.data.get('rule_id')
        table_id = request.data.get('data_table_id') or request.data.get('data_table')

        if rule_id:
            try:
                rule = DQRule.objects.select_related('data_field', 'data_table').get(id=rule_id)
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
        return Response({
            'table_count': profiles.count(),
            'total_rows': total_rows,
            'completeness_pct': round(weighted_completeness, 2),
        })


class TableDQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/table/{tableId}/ - Table-level DQ metrics"""
    permission_classes = [IsAuthenticated]

    def get(self, request, table_id):
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        _check_table_access(request.user, table)
        profile = TableProfile.objects.filter(data_table=table).first()
        rules = DQRule.objects.filter(
            Q(data_table=table) | Q(data_field__data_table=table), is_active=True
        ).distinct()
        field_profiles = FieldProfile.objects.filter(data_field__data_table=table)
        return Response({
            'table_id': table.id,
            'table_name': table.name,
            'row_count': profile.row_count if profile else 0,
            'completeness_pct': profile.completeness_pct if profile else 0,
            'field_profiles': FieldProfileSerializer(field_profiles, many=True).data,
            'active_rules': DQRuleSerializer(rules, many=True).data,
        })


class FieldDQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/field/{fieldId}/ - Field-level DQ metrics"""
    permission_classes = [IsAuthenticated]

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
        rules = DQRule.objects.filter(data_field=field, is_active=True)
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
    permission_classes = [IsAuthenticated]

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



