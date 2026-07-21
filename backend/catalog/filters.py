import django_filters
from django_filters import rest_framework as filters

from .models import GovernanceEvent


class GovernanceEventFilter(filters.FilterSet):
    entity_type = filters.CharFilter(field_name='entity_type', lookup_expr='exact')
    action = filters.CharFilter(field_name='action', lookup_expr='exact')
    user_id = filters.NumberFilter(field_name='user__id')
    start_date = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    end_date = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = GovernanceEvent
        fields = ['entity_type', 'action', 'user_id', 'start_date', 'end_date']
