# dq/views.py
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q

from .models import TableProfile, FieldProfile, DQRule, DQResult
from .serializers import (
    TableProfileSerializer, FieldProfileSerializer, DQRuleSerializer, DQResultSerializer,
)
from accounts.permissions import ReadAnyWriteGlobalAdmin, ReadScopedWriteAdmin
from accounts.rbac_utils import get_allowed_org_unit_ids, user_has_global_role, get_allowed_module_ids
from .services import profile_table, run_dq
from dataschema.models import DataTable, DataField


class FieldProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FieldProfileSerializer
    permission_classes = [ReadScopedWriteAdmin]

    def get_queryset(self):
        qs = FieldProfile.objects.all()
        p = self.request.query_params
        
        # Apply org-scoped filtering
        user = self.request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            qs = qs.filter(data_field__data_table__org_unit_id__in=allowed_org_ids)
        
        if p.get('data_table'):
            qs = qs.filter(data_field__data_table_id=p['data_table'])
        if p.get('data_field'):
            qs = qs.filter(data_field_id=p['data_field'])
        return qs


class TableProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TableProfileSerializer
    permission_classes = [ReadScopedWriteAdmin]

    def get_queryset(self):
        qs = TableProfile.objects.all()
        
        # Apply org-scoped filtering
        user = self.request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            qs = qs.filter(data_table__org_unit_id__in=allowed_org_ids)
        
        if self.request.query_params.get('data_table'):
            qs = qs.filter(data_table_id=self.request.query_params['data_table'])
        return qs


class DQRuleViewSet(viewsets.ModelViewSet):
    queryset = DQRule.objects.all()
    serializer_class = DQRuleSerializer
    permission_classes = [ReadScopedWriteAdmin]

    def get_queryset(self):
        qs = DQRule.objects.all()
        
        # Apply org-scoped filtering
        user = self.request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            qs = qs.filter(data_table__org_unit_id__in=allowed_org_ids) | qs.filter(data_field__data_table__org_unit_id__in=allowed_org_ids)
        
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_table_id=p['data_table'])
        if p.get('data_field'):
            qs = qs.filter(data_field_id=p['data_field'])
        return qs.distinct()


class DQResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DQResultSerializer
    permission_classes = [ReadScopedWriteAdmin]

    def get_queryset(self):
        qs = DQResult.objects.all()
        
        # Apply org-scoped filtering
        user = self.request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            qs = qs.filter(rule__data_table__org_unit_id__in=allowed_org_ids) | qs.filter(rule__data_field__data_table__org_unit_id__in=allowed_org_ids)
        
        p = self.request.query_params
        if p.get('rule'):
            qs = qs.filter(rule_id=p['rule'])
        if p.get('data_table'):
            qs = qs.filter(rule__data_table_id=p['data_table']) | qs.filter(rule__data_field__data_table_id=p['data_table'])
        return qs.distinct()


class ProfileTriggerView(APIView):
    """POST /dq/profile/ {"data_table": <id>} -> profile the table. Admin only."""
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def post(self, request):
        table_id = request.data.get('data_table')
        if not table_id:
            return Response({'error': 'data_table is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(profile_table(table_id))
        except Exception as exc:  # table not found etc.
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DQRunView(APIView):
    """POST /dq/run/ {"data_table": <id>} -> run active rules + roll up to catalog. Admin only."""
    permission_classes = [ReadAnyWriteGlobalAdmin]

    def post(self, request):
        table_id = request.data.get('data_table')
        if not table_id:
            return Response({'error': 'data_table is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(run_dq(table_id))
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


# --- NEW ENDPOINTS FOR A10 DQ INTEGRATION ---

class DQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/ - Org-scoped DQ summary"""
    permission_classes = [ReadScopedWriteAdmin]

    def get(self, request):
        user = request.user
        
        # Get user's allowed org units
        if user.is_superuser or user_has_global_role(user, ["admin", "admins_group"]):
            profiles = TableProfile.objects.all()
        else:
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            profiles = TableProfile.objects.filter(data_table__org_unit_id__in=allowed_org_ids)
        
        # Calculate aggregates
        total_rows = sum(p.row_count for p in profiles) if profiles else 0
        
        if total_rows > 0:
            weighted_completeness = sum(p.completeness_pct * p.row_count for p in profiles) / total_rows
        else:
            weighted_completeness = 0.0
        
        # Placeholder for uniqueness and compliance (would need FieldProfile and DQResult aggregation)
        return Response({
            'org_count': len(allowed_org_ids) if not user.is_superuser else 'all',
            'table_count': profiles.count(),
            'total_rows': total_rows,
            'completeness_pct': round(weighted_completeness, 2),
            'uniqueness_pct': 85.0,  # TODO: Calculate from FieldProfile
            'compliance_pct': 88.0,  # TODO: Calculate from DQResult
        })


class TableDQMetricsView(APIView):
    """GET /carbon-api/dq/metrics/table/{tableId}/ - Table-level DQ metrics"""
    permission_classes = [ReadScopedWriteAdmin]

    def get(self, request, table_id):
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission: user must have access to this table's module
        user = request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            if table.org_unit_id not in allowed_org_ids:
                return Response({'error': 'Not authorized for this table'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get table profile
        profile = TableProfile.objects.filter(data_table=table).first()
        
        # Get active rules
        rules = DQRule.objects.filter(
            (Q(data_table=table) | Q(data_field__data_table=table)) & Q(is_active=True)
        ).distinct()
        
        # Get field profiles
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
    permission_classes = [ReadScopedWriteAdmin]

    def get(self, request, field_id):
        try:
            field = DataField.objects.get(id=field_id)
        except DataField.DoesNotExist:
            return Response({'error': f'Field {field_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            if field.data_table.org_unit_id not in allowed_org_ids:
                return Response({'error': 'Not authorized for this field'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get field profile
        profile = FieldProfile.objects.filter(data_field=field).first()
        
        # Get rules for this field
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
    """POST /carbon-api/dq/run-validation/ - Trigger DQ check for table"""
    permission_classes = [ReadScopedWriteAdmin]

    def post(self, request):
        table_id = request.data.get('data_table')
        if not table_id:
            return Response({'error': 'data_table is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response({'error': f'Table {table_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if not (user.is_superuser or user_has_global_role(user, ["admin", "admins_group"])):
            allowed_org_ids = get_allowed_org_unit_ids(user, ["admin", "admins_group", "dataowners_group", "auditors_group"])
            if table.org_unit_id not in allowed_org_ids:
                return Response({'error': 'Not authorized for this table'}, status=status.HTTP_403_FORBIDDEN)
        
        # Trigger DQ validation
        try:
            result = run_dq(table_id)
            return Response({
                'status': 'complete',
                'message': 'DQ validation completed',
                'result': result
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
