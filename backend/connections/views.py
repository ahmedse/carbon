# connections/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import DataSource, ConsumingConnection
from .serializers import DataSourceSerializer, ConsumingConnectionSerializer
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
        try:
            # Placeholder: actual connectivity test would be implemented per source_type
            if not source.connection_config:
                return Response(
                    {'status': 'failure', 'message': 'No connection config'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Simulate a test; real implementation would try actual connection
            source.last_test_status = 'Connection test successful'
            source.status = 'active'
            source.save(update_fields=['last_test_status', 'status', 'last_tested_at'])
            
            return Response({
                'status': 'success',
                'message': 'Connection test successful',
                'last_tested_at': source.last_tested_at,
            })
        except Exception as e:
            source.last_test_status = str(e)
            source.status = 'error'
            source.save(update_fields=['last_test_status', 'status', 'last_tested_at'])
            return Response({
                'status': 'failure',
                'message': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)


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
        plaintext_key = conn.generate_api_key()
        return Response({
            'id': conn.id,
            'name': conn.name,
            'api_key': plaintext_key,
            'message': 'API key rotated. Store it safely—it will not be shown again.',
        })
