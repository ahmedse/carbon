# connections/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DataSource, ConsumingConnection
from .serializers import DataSourceSerializer, ConsumingConnectionSerializer
from .services import ConnectionService
from accounts.permissions import AdminOrSuperuserOnly
from core.feedback import AppFeedback
from catalog.audit_utils import emit_governance_event


class DataSourceViewSet(viewsets.ModelViewSet):
    """
    CRUD for data sources.
    Write/delete: global admin only.
    Read: any authenticated user.
    """
    queryset = DataSource.objects.select_related('domain', 'owner').order_by('-updated_at')
    serializer_class = DataSourceSerializer
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = 'connections:manage'

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        POST /connections/sources/{id}/test/ -> test connectivity
        Response: { "status": "success|failure", "message": "..." }
        """
        source = self.get_object()
        payload, status_code = ConnectionService.test_connection(source)
        return Response(payload, status=status_code)

    def destroy(self, request, *args, **kwargs):
        source = self.get_object()
        source.status = 'inactive'
        source.save(update_fields=['status'])
        emit_governance_event(
            entity_type='DataSource', entity_id=source.id,
            action='delete', before={'status': 'active'}, after={'status': 'inactive'},
            user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConsumingConnectionViewSet(viewsets.ModelViewSet):
    """
    CRUD for consuming connections (API clients, webhooks, etc).
    Write/delete: global admin only.
    Read: any authenticated user.
    """
    queryset = ConsumingConnection.objects.select_related('owner').order_by('-updated_at')
    serializer_class = ConsumingConnectionSerializer
    permission_classes = [AdminOrSuperuserOnly]
    required_capability = 'connections:manage'

    @action(detail=True, methods=['post'])
    def rotate_key(self, request, pk=None):
        """
        POST /connections/consuming/{id}/rotate-key/ -> generate new API key
        Response: { "api_key": "..." } (shown ONCE, never again)
        """
        conn = self.get_object()
        return Response(ConnectionService.rotate_key(conn))

    def destroy(self, request, *args, **kwargs):
        conn = self.get_object()
        conn.is_active = False
        conn.save(update_fields=['is_active'])
        emit_governance_event(
            entity_type='ConsumingConnection', entity_id=conn.id,
            action='delete', before={'is_active': True}, after={'is_active': False},
            user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
