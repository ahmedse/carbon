"""AI usage + quota REST views (Phase 21-A).

Mounted at ``/carbon-api/ai/usage/``.  Aggregate-only (RULE_23): these return
summed tokens/cost, never provider keys, base URLs, or raw usage dumps.

CBAC scoping: a regular user always sees their own usage.  Superusers / global
admins may pass ``?user_id=`` to inspect another account (tenant-safe override).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.rbac_utils import user_is_global_admin
from ai.usage_service import AIUsage, parse_period

User = get_user_model()


class _UsageBaseView(views.APIView):
    permission_classes = [IsAuthenticated]

    def resolve_target(self, request):
        """Return the user whose usage is being queried (CBAC-scoped)."""
        if request.user.is_superuser or user_is_global_admin(request.user):
            user_id = request.query_params.get("user_id")
            if user_id:
                return User.objects.get(id=user_id)
        return request.user

    def period(self, request) -> int:
        return parse_period(request.query_params.get("period"))


class UsageSummaryView(_UsageBaseView):
    """GET /carbon-api/ai/usage/summary/?period=30d"""

    def get(self, request):
        target = self.resolve_target(request)
        return Response(AIUsage(target).summary(self.period(request)))


class UsageByConversationView(_UsageBaseView):
    """GET /carbon-api/ai/usage/by-conversation/?period=30d"""

    def get(self, request):
        target = self.resolve_target(request)
        return Response(AIUsage(target).by_conversation(self.period(request)))
