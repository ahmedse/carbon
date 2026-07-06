# dq/views.py
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import TableProfile, FieldProfile, DQRule, DQResult
from .serializers import (
    TableProfileSerializer, FieldProfileSerializer, DQRuleSerializer, DQResultSerializer,
)
from .permissions import ReadAnyWriteAdmin
from .services import profile_table, run_dq


class FieldProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FieldProfileSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        qs = FieldProfile.objects.all()
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_field__data_table_id=p['data_table'])
        if p.get('data_field'):
            qs = qs.filter(data_field_id=p['data_field'])
        return qs


class TableProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TableProfileSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        qs = TableProfile.objects.all()
        if self.request.query_params.get('data_table'):
            qs = qs.filter(data_table_id=self.request.query_params['data_table'])
        return qs


class DQRuleViewSet(viewsets.ModelViewSet):
    queryset = DQRule.objects.all()
    serializer_class = DQRuleSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        qs = DQRule.objects.all()
        p = self.request.query_params
        if p.get('data_table'):
            qs = qs.filter(data_table_id=p['data_table'])
        if p.get('data_field'):
            qs = qs.filter(data_field_id=p['data_field'])
        return qs


class DQResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DQResultSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        qs = DQResult.objects.all()
        p = self.request.query_params
        if p.get('rule'):
            qs = qs.filter(rule_id=p['rule'])
        if p.get('data_table'):
            qs = qs.filter(rule__data_table_id=p['data_table']) | qs.filter(rule__data_field__data_table_id=p['data_table'])
        return qs.distinct()


class ProfileTriggerView(APIView):
    """POST /dq/profile/ {"data_table": <id>} -> profile the table. Admin only."""
    permission_classes = [ReadAnyWriteAdmin]

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
    permission_classes = [ReadAnyWriteAdmin]

    def post(self, request):
        table_id = request.data.get('data_table')
        if not table_id:
            return Response({'error': 'data_table is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(run_dq(table_id))
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
