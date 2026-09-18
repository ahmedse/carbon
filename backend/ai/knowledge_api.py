"""KnowledgeItem REST CRUD for Pulse Assets (ADR-0036 Phase 7).

Mounted under ``/carbon-api/ai/knowledge/``:

    GET    items/              list (scoped)
    POST   items/              create draft
    GET    items/<id>/         retrieve
    PATCH  items/<id>/         update
    POST   items/<id>/revoke/  soft revoke (deprecated + effective_end)
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.capabilities import (
    AI_MANAGE_CONSOLE,
    AI_PUBLISHER,
    AI_VIEW_CONSOLE,
    has_any_capability,
)
from ai.audit_service import AuditService
from ai.instance_registry import resolve_default_app_identifier
from ai.models.knowledge import (
    KNOWLEDGE_CLASSES,
    REVIEW_DEPRECATED,
    REVIEW_DRAFT,
    REVIEW_STATUSES,
    SENSITIVITIES,
    KnowledgeItem,
)


class KnowledgeReadPermission(BasePermission):
    message = "Requires ai:view_console."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return has_any_capability(user, {AI_VIEW_CONSOLE.key})


class KnowledgeWritePermission(BasePermission):
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


def _serialize(item: KnowledgeItem) -> dict:
    return {
        "id": item.id,
        "knowledge_class": item.knowledge_class,
        "source": item.source,
        "owner_id": item.owner_id,
        "scope": item.scope or {},
        "version": item.version,
        "effective_start": item.effective_start.isoformat()
        if item.effective_start
        else None,
        "effective_end": item.effective_end.isoformat()
        if item.effective_end
        else None,
        "review_status": item.review_status,
        "sensitivity": item.sensitivity,
        "supersedes_id": item.supersedes_id or "",
        "content": item.content,
        "is_mandatory": item.is_mandatory,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _scoped(qs, request):
    return scope_ai_queryset(qs, request.user)


class KnowledgeItemListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), KnowledgeWritePermission()]
        return [IsAuthenticated(), KnowledgeReadPermission()]

    def get(self, request):
        qs = _scoped(KnowledgeItem.objects.all(), request)
        kclass = request.query_params.get("knowledge_class")
        status_filter = request.query_params.get("review_status")
        if kclass:
            qs = qs.filter(knowledge_class=kclass)
        if status_filter:
            qs = qs.filter(review_status=status_filter)
        rows = list(qs.order_by("-updated_at")[:200])
        return Response(
            {
                "count": len(rows),
                "results": [_serialize(i) for i in rows],
            }
        )

    def post(self, request):
        data = request.data or {}
        kclass = str(data.get("knowledge_class") or "").strip()
        content = str(data.get("content") or "").strip()
        source = str(data.get("source") or "steward").strip() or "steward"
        if kclass not in KNOWLEDGE_CLASSES:
            return Response(
                {"detail": f"knowledge_class must be one of {list(KNOWLEDGE_CLASSES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not content:
            return Response(
                {"detail": "content is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        review_status = str(data.get("review_status") or REVIEW_DRAFT).strip()
        if review_status not in REVIEW_STATUSES:
            return Response(
                {"detail": f"review_status must be one of {list(REVIEW_STATUSES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sensitivity = str(data.get("sensitivity") or "internal").strip()
        if sensitivity not in SENSITIVITIES:
            return Response(
                {"detail": f"sensitivity must be one of {list(SENSITIVITIES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        item = KnowledgeItem(
            knowledge_class=kclass,
            source=source,
            owner_id=str(data.get("owner_id") or request.user.username),
            scope=data.get("scope") if isinstance(data.get("scope"), dict) else {},
            version=str(data.get("version") or "1"),
            review_status=review_status,
            sensitivity=sensitivity,
            content=content,
            is_mandatory=bool(data.get("is_mandatory")),
            supersedes_id=str(data.get("supersedes_id") or ""),
            host_user_id=str(request.user.pk),
            visibility="shared",
            app_identifier=resolve_default_app_identifier(),
        )
        item.save()
        AuditService.log(
            action="ai.knowledge.create",
            actor=request.user.username,
            host_user_id=str(request.user.pk),
            target=str(item.id),
            detail={"knowledge_class": item.knowledge_class},
            visibility="shared",
        )
        return Response(_serialize(item), status=status.HTTP_201_CREATED)


class KnowledgeItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAuthenticated(), KnowledgeWritePermission()]
        return [IsAuthenticated(), KnowledgeReadPermission()]

    def get(self, request, item_id):
        item = _scoped(KnowledgeItem.objects.filter(pk=item_id), request).first()
        if item is None:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(_serialize(item))

    def patch(self, request, item_id):
        item = _scoped(KnowledgeItem.objects.filter(pk=item_id), request).first()
        if item is None:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        data = request.data or {}
        fields = []
        if "content" in data:
            item.content = str(data["content"])
            fields.append("content")
        if "source" in data:
            item.source = str(data["source"]).strip() or item.source
            fields.append("source")
        if "version" in data:
            item.version = str(data["version"])
            fields.append("version")
        if "review_status" in data:
            rs = str(data["review_status"]).strip()
            if rs not in REVIEW_STATUSES:
                return Response(
                    {"detail": f"Invalid review_status"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.review_status = rs
            fields.append("review_status")
        if "sensitivity" in data:
            sens = str(data["sensitivity"]).strip()
            if sens not in SENSITIVITIES:
                return Response(
                    {"detail": "Invalid sensitivity"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.sensitivity = sens
            fields.append("sensitivity")
        if "is_mandatory" in data:
            item.is_mandatory = bool(data["is_mandatory"])
            fields.append("is_mandatory")
        if "scope" in data and isinstance(data["scope"], dict):
            item.scope = data["scope"]
            fields.append("scope")
        if not fields:
            return Response(_serialize(item))
        fields.append("updated_at")
        item.save(update_fields=fields)
        AuditService.log(
            action="ai.knowledge.update",
            actor=request.user.username,
            host_user_id=str(request.user.pk),
            target=str(item.id),
            detail={"fields": fields},
            visibility="shared",
        )
        return Response(_serialize(item))


class KnowledgeItemRevokeView(APIView):
    """POST items/<id>/revoke/ — soft revoke (keep for provenance)."""

    permission_classes = [IsAuthenticated, KnowledgeWritePermission]

    def post(self, request, item_id):
        item = _scoped(KnowledgeItem.objects.filter(pk=item_id), request).first()
        if item is None:
            return Response(
                {"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        reason = str((request.data or {}).get("reason") or "").strip()
        now = timezone.now()
        item.review_status = REVIEW_DEPRECATED
        item.effective_end = now
        item.save(update_fields=["review_status", "effective_end", "updated_at"])
        AuditService.log(
            action="ai.knowledge.revoke",
            actor=request.user.username,
            host_user_id=str(request.user.pk),
            target=str(item.id),
            detail={"reason": reason, "effective_end": now.isoformat()},
            visibility="shared",
        )
        return Response({**_serialize(item), "revoked": True})
