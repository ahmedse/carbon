"""Work Objectives REST API — list + status update (Pulse v2 Phase 8).

GET    /carbon-api/ai/work-objectives/          list the user's objectives
PATCH  /carbon-api/ai/work-objectives/{id}/     update status only
"""
from __future__ import annotations

import logging

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ai.models.core import WorkObjective
from ai.serializers import WorkObjectiveSerializer

logger = logging.getLogger("carbon.ai.work_objectives_api")


class WorkObjectiveViewSet(viewsets.ModelViewSet):
    """Read + status-update access to a user's durable work objectives."""

    serializer_class = WorkObjectiveSerializer
    http_method_names = ["get", "patch", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = WorkObjective.objects.filter(
            host_user_id=str(self.request.user.pk),
        ).order_by("-updated_at")

        status_filter = self.request.query_params.get("status_filter", "open")
        if status_filter != "all":
            statuses = (
                ["open", "in_progress", "waiting_for_user"]
                if status_filter == "open" else [status_filter]
            )
            qs = qs.filter(status__in=statuses)
        return qs

    def perform_update(self, serializer):
        # Defense-in-depth: only status is ever writable via this endpoint.
        # The serializer marks everything else read-only, but filter here too
        # so a crafted payload can never mutate title/description/summary.
        allowed = {"status"}
        data = {k: v for k, v in serializer.validated_data.items() if k in allowed}
        serializer.save(**data)
