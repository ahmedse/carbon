"""Admin skill promote/reject decision API (PEC-6A).

Mounted at ``{api_prefix}/ai/skills/``:

    POST /{id}/promote/   — run admission gate → instance_promoted (on admit)
    POST /{id}/reject/    — deprecate with optional reason

CBAC: ``ai:publisher`` or ``ai:process_owner`` (same posture as registry
deprecate).  Promotion never bypasses ``_authority`` / the admission gate.
"""

from __future__ import annotations

import logging

from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import AI_PROCESS_OWNER, AI_PUBLISHER, has_any_capability
from ai.skills_decision_service import promote_skill, reject_skill

logger = logging.getLogger("carbon.ai.skills_decision_api")


class SkillDecisionPermission(BasePermission):
    """Promote/reject requires publisher or process-owner capability."""

    message = (
        "Promoting or rejecting a skill requires ai:publisher or ai:process_owner."
    )

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return has_any_capability(
            user, {AI_PUBLISHER.key, AI_PROCESS_OWNER.key}
        )


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )


class SkillPromoteView(APIView):
    """POST /skills/{id}/promote/ — gate-only promotion."""

    permission_classes = [IsAuthenticated, SkillDecisionPermission]

    def post(self, request, pk):
        try:
            from ai.instance_registry import resolve_instance_id
            from ai.models.control_state import get_or_create_control_state

            state = get_or_create_control_state(resolve_instance_id())
            if state.learning_admissions_frozen or state.containment_level in (
                "learning_freeze",
                "full_stop",
            ):
                return Response(
                    {
                        "error": "learning_frozen",
                        "detail": (
                            "Learning admissions are frozen by Control Plane "
                            f"containment ({state.containment_level})."
                        ),
                    },
                    status=status.HTTP_423_LOCKED,
                )
        except Exception:  # noqa: BLE001 — never block promote on control-state read failure
            logger.exception("containment check failed; continuing promote")

        result = promote_skill(user=request.user, skill_id=str(pk))
        return Response(result, status=status.HTTP_200_OK)


class SkillRejectView(APIView):
    """POST /skills/{id}/reject/ — deprecate with optional reason."""

    permission_classes = [IsAuthenticated, SkillDecisionPermission]

    def post(self, request, pk):
        ser = RejectSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        result = reject_skill(
            user=request.user,
            skill_id=str(pk),
            reason=ser.validated_data.get("reason") or "",
        )
        return Response(result, status=status.HTTP_200_OK)
