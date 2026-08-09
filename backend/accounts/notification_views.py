# File: accounts/notification_views.py
# Phase 1.6 — Notification API endpoints

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserAlert


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """User-scoped notifications: list, retrieve, mark-read, mark-all-read."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserAlert.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        from .serializers import NotificationSerializer
        return NotificationSerializer

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user."""
        count = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'detail': f'{count} notification(s) marked as read.', 'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'detail': 'Notification marked as read.', 'id': notification.id})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Return only the count of unread notifications."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})
