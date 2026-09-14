# File: core/filters.py
# FilterSet for the general request audit trail (RequestAuditLog).

from django_filters import rest_framework as filters

from .models import RequestAuditLog


class RequestAuditLogFilter(filters.FilterSet):
    """Filters for RequestAuditLogViewSet.

    Query params:
      - user            -> username (case-insensitive contains)
      - method          -> comma-separated HTTP method(s), e.g. method=POST,PATCH
      - path            -> case-insensitive substring on request path
      - timestamp__gte  -> timestamp >= value
      - timestamp__lte  -> timestamp <= value
    """
    user = filters.CharFilter(field_name='user__username', lookup_expr='icontains')
    method = filters.BaseInFilter(field_name='method', lookup_expr='in')
    path = filters.CharFilter(field_name='path', lookup_expr='icontains')
    timestamp__gte = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp__lte = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = RequestAuditLog
        fields = ['user', 'method', 'path', 'timestamp__gte', 'timestamp__lte']
