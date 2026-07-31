# connections/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DataSource, ConsumingConnection
from .serializers import DataSourceSerializer, ConsumingConnectionSerializer
from .services import ConnectionService
from accounts.permissions import ReadAnyWriteGlobalAdmin
from catalog.permissions import AdminOrSuperuserOnly


class DataSourceViewSet(viewsets.ModelViewSet):
    """
    CRUD for data sources.
    Write/delete: global admin only.
    Read: any authenticated user.
    """
    queryset = DataSource.objects.select_related('domain', 'owner').order_by('-updated_at')
    serializer_class = DataSourceSerializer
    permission_classes = [AdminOrSuperuserOnly]

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        POST /connections/sources/{id}/test/ -> test connectivity
        Response: { "status": "success|failure", "message": "..." }
        """
        source = self.get_object()
        payload, status_code = ConnectionService.test_connection(source)
        return Response(payload, status=status_code)


class ConsumingConnectionViewSet(viewsets.ModelViewSet):
    """
    CRUD for consuming connections (API clients, webhooks, etc).
    Write/delete: global admin only.
    Read: any authenticated user.
    """
    queryset = ConsumingConnection.objects.select_related('owner').order_by('-updated_at')
    serializer_class = ConsumingConnectionSerializer
    permission_classes = [AdminOrSuperuserOnly]

    @action(detail=True, methods=['post'])
    def rotate_key(self, request, pk=None):
        """
        POST /connections/consuming/{id}/rotate-key/ -> generate new API key
        Response: { "api_key": "..." } (shown ONCE, never again)
        """
        conn = self.get_object()
        return Response(ConnectionService.rotate_key(conn))
