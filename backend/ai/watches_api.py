"""Phase H3-B — user-configurable anomaly watches CRUD API.

GET    /carbon-api/ai/watches/       — list (own watches, or scoped for admins)
POST   /carbon-api/ai/watches/       — create (``ai:manage_console`` required)
PATCH  /carbon-api/ai/watches/{pk}/  — update (``ai:manage_console`` or owner)
DELETE /carbon-api/ai/watches/{pk}/  — delete (``ai:manage_console`` or owner)

The read path uses CBAC scoping via ``scope_ai_queryset`` (the established
AI read-layer pattern, RULE_20 / I1). A watch's ``condition`` is a
machine-evaluable spec (``table`` / ``column`` / ``operator`` /
``aggregation``); ``kpi_expression`` is a natural-language LABEL that is
never executed.
"""

import logging

from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.capabilities import (
    AI_MANAGE_CONSOLE,
    AI_VIEW_CONSOLE,
    has_capability,
)
from ai.models import AIAnomalyWatch

logger = logging.getLogger("carbon.ai.watches_api")

User = get_user_model()

_ALLOWED_CONDITION_KEYS = {"table", "column", "operator", "aggregation"}
_ALLOWED_OPERATORS = {"<", "<=", ">", ">=", "==", "!="}
_ALLOWED_AGGREGATIONS = {"latest", "avg", "max", "min", "count"}


def _validate_condition(condition) -> str | None:
    """Return an error message when ``condition`` is malformed, else ``None``."""
    if condition is None:
        return None
    if not isinstance(condition, dict):
        return "condition must be a JSON object"
    extra = set(condition.keys()) - _ALLOWED_CONDITION_KEYS
    if extra:
        return f"unknown condition keys: {sorted(extra)}"
    operator = condition.get("operator")
    if operator is not None and operator not in _ALLOWED_OPERATORS:
        return f"invalid operator: {operator}"
    aggregation = condition.get("aggregation")
    if aggregation is not None and aggregation not in _ALLOWED_AGGREGATIONS:
        return f"invalid aggregation: {aggregation}"
    return None


class AIAnomalyWatchSerializer(serializers.ModelSerializer):
    recipients = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )

    class Meta:
        model = AIAnomalyWatch
        fields = [
            "id",
            "name",
            "kpi_expression",
            "condition",
            "threshold",
            "comparison_window_days",
            "enabled",
            "last_fired_at",
            "fire_count",
            "recipients",
            "instance_id",
        ]
        read_only_fields = ["id", "last_fired_at", "fire_count"]

    def validate_condition(self, value):
        error = _validate_condition(value)
        if error:
            raise serializers.ValidationError(error)
        return value


def _scoped_queryset(user):
    """List queryset: scoped for console viewers, else the caller's own rows."""
    if has_capability(user, AI_VIEW_CONSOLE.key):
        return scope_ai_queryset(AIAnomalyWatch.objects.all(), user)
    return AIAnomalyWatch.objects.filter(user=user)


class WatchesListView(APIView):
    """GET/POST / — list or create anomaly watches."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _scoped_queryset(request.user).order_by("-created_at")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginator.max_page_size = 100
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                AIAnomalyWatchSerializer(page, many=True).data
            )
        return Response(AIAnomalyWatchSerializer(qs, many=True).data)

    def post(self, request):
        if not has_capability(request.user, AI_MANAGE_CONSOLE.key):
            return Response(
                {"detail": "You do not have permission to create anomaly watches."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = AIAnomalyWatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        watch = serializer.save(user=request.user)
        return Response(
            AIAnomalyWatchSerializer(watch).data,
            status=status.HTTP_201_CREATED,
        )


class WatchDetailView(APIView):
    """PATCH/DELETE /{pk}/ — update or delete a single watch."""

    permission_classes = [IsAuthenticated]

    def _get_object(self):
        pk = self.kwargs.get("pk")
        if has_capability(self.request.user, AI_MANAGE_CONSOLE.key):
            qs = scope_ai_queryset(AIAnomalyWatch.objects.all(), self.request.user)
        else:
            qs = AIAnomalyWatch.objects.filter(user=self.request.user)
        try:
            return qs.get(pk=pk)
        except AIAnomalyWatch.DoesNotExist:
            return None

    def patch(self, request, pk=None):
        watch = self._get_object()
        if watch is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AIAnomalyWatchSerializer(watch, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        watch = serializer.save()
        return Response(AIAnomalyWatchSerializer(watch).data)

    def delete(self, request, pk=None):
        watch = self._get_object()
        if watch is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        watch.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
