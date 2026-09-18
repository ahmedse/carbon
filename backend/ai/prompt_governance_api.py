"""Prompt version governance for Pulse Control Plane (ADR-0036 Phase 7).

Mounted under ``/carbon-api/ai/pulse/control/prompts/``:

    GET  versions/                    — list PromptVersion rows for instance
    POST versions/<id>/activate/      — make this version the active one
    POST versions/<id>/rollback/      — activate parent (or prior) version

PEC-7A: chat hot path uses ``instance.yaml``; these endpoints govern
optimizer/heartbeat PromptVersion rows for ops rollback — not live chat
prompt switching.
"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.capabilities import AI_MANAGE_CONSOLE, AI_PUBLISHER, has_any_capability
from ai.audit_service import AuditService
from ai.instance_registry import resolve_instance_id
from ai.models.core import PromptVersion


class PromptGovernPermission(BasePermission):
    message = "Requires ai:publisher or ai:manage_console."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return has_any_capability(
            user, {AI_PUBLISHER.key, AI_MANAGE_CONSOLE.key}
        )


class PromptVersionListView(APIView):
    """GET control/prompts/versions/ — list versions for current instance."""

    permission_classes = [IsAuthenticated, PromptGovernPermission]

    def get(self, request):
        instance_id = request.query_params.get("instance_id") or resolve_instance_id()
        qs = PromptVersion.objects.filter(instance_id=instance_id).order_by(
            "-improvement_round", "-created_at"
        )
        results = [
            {
                "id": row.id,
                "instance_id": row.instance_id,
                "is_active": row.is_active,
                "score": row.score,
                "improvement_round": row.improvement_round,
                "parent_version_id": row.parent_version_id,
                "content_hash": row.content_hash,
                "prompt_preview": (row.prompt_text or "")[:240],
                "synthesized_at": row.synthesized_at.isoformat()
                if row.synthesized_at
                else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in qs[:200]
        ]
        return Response(
            {
                "instance_id": instance_id,
                "count": len(results),
                "results": results,
                "note": (
                    "PEC-7A: activate/rollback governs optimizer PromptVersion "
                    "rows; live chat uses instance.yaml."
                ),
            }
        )


def _serialize(row: PromptVersion) -> dict:
    return {
        "id": row.id,
        "instance_id": row.instance_id,
        "is_active": row.is_active,
        "score": row.score,
        "improvement_round": row.improvement_round,
        "parent_version_id": row.parent_version_id,
        "content_hash": row.content_hash,
    }


def _activate(row: PromptVersion, actor: str, action: str) -> PromptVersion:
    with transaction.atomic():
        PromptVersion.objects.filter(instance_id=row.instance_id).update(
            is_active=False
        )
        row.is_active = True
        row.save(update_fields=["is_active"])
    AuditService.log(
        action=action,
        actor=actor,
        target=str(row.id),
        detail={
            "instance_id": row.instance_id,
            "improvement_round": row.improvement_round,
            "parent_version_id": row.parent_version_id,
        },
        visibility="shared",
    )
    return row


class PromptVersionActivateView(APIView):
    """POST control/prompts/versions/<id>/activate/."""

    permission_classes = [IsAuthenticated, PromptGovernPermission]

    def post(self, request, version_id):
        row = PromptVersion.objects.filter(pk=version_id).first()
        if row is None:
            return Response(
                {"detail": "Prompt version not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        activated = _activate(
            row, request.user.username, "ai.prompt.activate"
        )
        return Response({"activated": True, "version": _serialize(activated)})


class PromptVersionRollbackView(APIView):
    """POST control/prompts/versions/<id>/rollback/.

    Activates ``parent_version_id`` when present; otherwise the newest prior
    version for the same instance by ``created_at``.
    """

    permission_classes = [IsAuthenticated, PromptGovernPermission]

    def post(self, request, version_id):
        current = PromptVersion.objects.filter(pk=version_id).first()
        if current is None:
            return Response(
                {"detail": "Prompt version not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        target = None
        if current.parent_version_id:
            target = PromptVersion.objects.filter(
                pk=current.parent_version_id,
                instance_id=current.instance_id,
            ).first()
        if target is None:
            target = (
                PromptVersion.objects.filter(instance_id=current.instance_id)
                .exclude(pk=current.pk)
                .order_by("-created_at")
                .first()
            )
        if target is None:
            return Response(
                {"detail": "No prior version to roll back to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activated = _activate(
            target, request.user.username, "ai.prompt.rollback"
        )
        return Response(
            {
                "rolled_back": True,
                "from_version_id": current.id,
                "version": _serialize(activated),
            }
        )
