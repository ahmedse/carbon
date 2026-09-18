"""Process Registry REST API (P3-05a).

Mounted at ``{api_prefix}/ai/registry/`` (see ``config/urls.py``) with every
route under the literal ``processes/`` segment (see ``ai.registry_urls``):

    GET    /processes/                  list definitions (latest per process_id)
    POST   /processes/                  create a draft
    GET    /processes/{id}/             retrieve one definition
    PATCH  /processes/{id}/             edit a draft (draft status only)
    POST   /processes/{id}/submit/      draft → review
    POST   /processes/{id}/publish/     review → active (author ≠ publisher)
    POST   /processes/{id}/deprecate/   active → deprecated
    GET    /processes/{id}/diff/        diff latest draft/review vs active
    GET    /processes/{id}/autonomy/    effective autonomy per step
    PATCH  /processes/{id}/autonomy/    set the autonomy dial {step_id: autonomy}
    POST   /processes/{id}/kill/        set the kill switch {enabled: bool}

``{id}`` is the definition document ``id`` (the ``process_id`` column); versions
share a ``process_id`` and are ordered newest-first.

Permission model (CBAC): each action is gated by capability keys via
``accounts.capabilities.has_capability`` / ``has_any_capability`` — group/role
names are never hardcoded here. Reads (list/retrieve/diff/autonomy) require
``ai:process_owner``/``ai:auditor``/``ai:view_console``; writes map to
``ai:process_owner`` (create/edit/submit/autonomy), ``ai:publisher`` (publish),
``ai:process_owner`` or ``ai:publisher`` (deprecate), and ``ai:operator`` or
``ai:process_owner`` (kill). ``publish`` additionally refuses self-publish
(actor is the document author or the row creator) unless the actor is superuser.
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from accounts.capabilities import (
    AI_AUDITOR,
    AI_OPERATOR,
    AI_PROCESS_OWNER,
    AI_PUBLISHER,
    AI_VIEW_CONSOLE,
    has_any_capability,
)
from ai.audit_service import AuditService
from ai.models.process import (
    STATUS_ACTIVE,
    STATUS_DEPRECATED,
    STATUS_DRAFT,
    STATUS_REVIEW,
    VALID_AUTONOMY,
    ProcessDefinition,
    validate_definition,
)

logger = logging.getLogger("carbon.ai.registry_api")


# ── Capability permission classes ──────────────────────────────────────────

class HasCapability(BasePermission):
    """Allow authenticated users holding any of ``capability_keys`` (or ``*``)."""

    capability_keys: frozenset[str] = frozenset()
    message = "You do not have a required capability."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return has_any_capability(user, set(self.capability_keys))


class RegistryReadPermission(HasCapability):
    """Read access: process owner, auditor, or view-console."""

    message = "Reading the registry requires a governance capability."
    capability_keys = frozenset(
        {AI_PROCESS_OWNER.key, AI_AUDITOR.key, AI_VIEW_CONSOLE.key}
    )


class ProcessOwnerPermission(HasCapability):
    message = "This action requires the ai:process_owner capability."
    capability_keys = frozenset({AI_PROCESS_OWNER.key})


class PublisherPermission(HasCapability):
    message = "Publishing requires the ai:publisher capability."
    capability_keys = frozenset({AI_PUBLISHER.key})


class OwnerOrPublisherPermission(HasCapability):
    message = "Deprecating requires the ai:process_owner or ai:publisher capability."
    capability_keys = frozenset({AI_PROCESS_OWNER.key, AI_PUBLISHER.key})


class OperatorOrOwnerPermission(HasCapability):
    message = "Setting the kill switch requires the ai:operator or ai:process_owner capability."
    capability_keys = frozenset({AI_OPERATOR.key, AI_PROCESS_OWNER.key})


# ── Serializers ────────────────────────────────────────────────────────────

class DefinitionDocumentSerializer(serializers.Serializer):
    """Accept the raw definition document as the request body."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "Request body must be a JSON object (the full definition document)."
            )
        return {"document": data}


class AutonomyDialSerializer(serializers.Serializer):
    """Accept a flat ``{step_id: autonomy}`` autonomy dial."""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                "Autonomy dial must be a JSON object mapping step_id to autonomy."
            )
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise serializers.ValidationError(
                    "Autonomy dial must map step_id strings to autonomy strings."
                )
        return {"dial": data}


class KillSwitchSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=True)


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False, max_length=2000)


class ProcessDefinitionSerializer(serializers.ModelSerializer):
    """Output serializer — includes the effective ``kill_switch`` flag."""

    kill_switch = serializers.SerializerMethodField()

    class Meta:
        model = ProcessDefinition
        fields = [
            "id",
            "process_id",
            "version",
            "owner",
            "status",
            "definition",
            "kill_switch",
            "created_at",
            "updated_at",
        ]

    def get_kill_switch(self, obj) -> bool:
        return bool((obj.definition or {}).get("kill_switch", False))


def _serialize(obj: ProcessDefinition) -> dict:
    return ProcessDefinitionSerializer(obj).data


def _diff_dict(a, b):
    """Recursive diff returning (added, removed, changed) for ``b`` vs ``a``."""
    a = a if isinstance(a, dict) else {}
    b = b if isinstance(b, dict) else {}
    added: dict = {}
    removed: dict = {}
    changed: dict = {}
    for key in b:
        if key not in a:
            added[key] = b[key]
    for key in a:
        if key not in b:
            removed[key] = a[key]
    for key in a:
        if key not in b:
            continue
        av, bv = a[key], b[key]
        if isinstance(av, dict) and isinstance(bv, dict):
            sub_added, sub_removed, sub_changed = _diff_dict(av, bv)
            if sub_added or sub_removed or sub_changed:
                changed[key] = {
                    "added": sub_added,
                    "removed": sub_removed,
                    "changed": sub_changed,
                }
        elif av != bv:
            changed[key] = {"from": av, "to": bv}
    return added, removed, changed


class RegistryViewSet(viewsets.GenericViewSet):
    """Process registry — read-gated reads, capability-gated writes."""

    permission_classes = [IsAuthenticated]
    serializer_class = ProcessDefinitionSerializer

    action_permission_map = {
        "list": [RegistryReadPermission],
        "retrieve": [RegistryReadPermission],
        "create": [ProcessOwnerPermission],
        "partial_update": [ProcessOwnerPermission],
        "submit": [ProcessOwnerPermission],
        "publish": [PublisherPermission],
        "deprecate": [OwnerOrPublisherPermission],
        "diff": [RegistryReadPermission],
        "autonomy": [RegistryReadPermission],
        "set_autonomy": [ProcessOwnerPermission],
        "kill": [OperatorOrOwnerPermission],
        "reject": [OwnerOrPublisherPermission],
    }

    def get_permissions(self):
        perms = [IsAuthenticated()]
        for perm_cls in self.action_permission_map.get(self.action, []):
            perms.append(perm_cls())
        return perms

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _process_id(view) -> str:
        return str(view.kwargs.get("pk") or "")

    @staticmethod
    def _latest(process_id: str) -> ProcessDefinition | None:
        return (
            ProcessDefinition.objects.filter(process_id=process_id)
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def _not_found(process_id: str) -> Response:
        return Response(
            {
                "error": "not_found",
                "detail": f"No process definition found for {process_id!r}.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    @staticmethod
    def _invalid(detail) -> Response:
        return Response(
            {"error": "invalid", "detail": detail},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @staticmethod
    def _set_status(obj: ProcessDefinition, new_status: str) -> ProcessDefinition:
        doc = dict(obj.definition or {})
        doc["status"] = new_status
        obj.definition = doc
        obj.status = new_status
        obj.save()
        return obj

    @staticmethod
    def _is_self_publish(user, obj: ProcessDefinition) -> bool:
        if getattr(user, "is_superuser", False):
            return False
        if getattr(user, "username", None) == obj.owner:
            return True
        return str(getattr(user, "pk", "")) == str(obj.host_user_id or "")

    # ── collection ───────────────────────────────────────────────────

    def list(self, request):
        qs = ProcessDefinition.objects.all()
        process_id = request.query_params.get("process_id")
        status_filter = request.query_params.get("status")
        if process_id:
            qs = qs.filter(process_id=process_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs.order_by("process_id", "-created_at")

        seen: set[str] = set()
        rows = []
        for obj in qs:
            if obj.process_id in seen:
                continue
            seen.add(obj.process_id)
            rows.append(
                {
                    "process_id": obj.process_id,
                    "version": obj.version,
                    "owner": obj.owner,
                    "status": obj.status,
                    "kill_switch": bool((obj.definition or {}).get("kill_switch", False)),
                    "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
                }
            )
        return Response(rows)

    def create(self, request):
        serializer = DefinitionDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = dict(serializer.validated_data["document"])

        document["status"] = STATUS_DRAFT
        document["owner"] = request.user.username

        errors = validate_definition(document)
        if errors:
            return self._invalid({"definition": errors})

        instance = ProcessDefinition.from_document(document)
        instance.host_user_id = str(request.user.pk)
        instance.save()
        return Response(_serialize(instance), status=status.HTTP_201_CREATED)

    # ── detail ───────────────────────────────────────────────────────

    def retrieve(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))
        return Response(_serialize(obj))

    def partial_update(self, request, pk=None):
        process_id = self._process_id(self)
        current = self._latest(process_id)
        if current is None:
            return self._not_found(process_id)
        if current.status != STATUS_DRAFT:
            return self._invalid(
                f"Process {process_id!r} is {current.status!r}; only drafts can be edited."
            )

        serializer = DefinitionDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submitted = dict(serializer.validated_data["document"])

        merged = dict(current.definition or {})
        merged.update(submitted)
        merged["id"] = current.process_id
        merged["owner"] = current.owner
        merged["status"] = STATUS_DRAFT

        errors = validate_definition(merged)
        if errors:
            return self._invalid({"definition": errors})

        rebuilt = ProcessDefinition.from_document(merged)
        current.definition = merged
        current.version = rebuilt.version
        current.status = STATUS_DRAFT
        current.save()
        return Response(_serialize(current))

    # ── lifecycle ────────────────────────────────────────────────────

    def submit(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))
        if obj.status != STATUS_DRAFT:
            return self._invalid(
                f"Process {obj.process_id!r} is {obj.status!r}; only drafts can be submitted."
            )
        return Response(_serialize(self._set_status(obj, STATUS_REVIEW)))

    def publish(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))
        if obj.status != STATUS_REVIEW:
            return self._invalid(
                f"Process {obj.process_id!r} is {obj.status!r}; only review documents can be published."
            )
        if self._is_self_publish(request.user, obj):
            return Response(
                {
                    "error": "forbidden",
                    "detail": "Self-publish is refused: the publisher must differ from the author.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(_serialize(self._set_status(obj, STATUS_ACTIVE)))

    def deprecate(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))
        if obj.status != STATUS_ACTIVE:
            return self._invalid(
                f"Process {obj.process_id!r} is {obj.status!r}; only active documents can be deprecated."
            )
        return Response(_serialize(self._set_status(obj, STATUS_DEPRECATED)))

    def reject(self, request, pk=None):
        """Return a review document to draft with a persisted reason (ADR-0036)."""
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))
        if obj.status != STATUS_REVIEW:
            return self._invalid(
                f"Process {obj.process_id!r} is {obj.status!r}; only review documents can be rejected."
            )
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        doc = dict(obj.definition or {})
        history = list(doc.get("review_history") or [])
        history.append(
            {
                "action": "rejected",
                "reason": reason,
                "by": request.user.username,
                "at": timezone.now().isoformat(),
            }
        )
        doc["review_history"] = history
        doc["last_reject_reason"] = reason
        doc["status"] = STATUS_DRAFT
        obj.definition = doc
        obj.status = STATUS_DRAFT
        obj.save()

        AuditService.log(
            action="ai.process.rejected",
            actor=request.user.username,
            target=obj.process_id,
            detail={"reason": reason, "version": obj.version},
            host_user_id=str(request.user.pk),
            visibility="shared",
        )
        return Response(_serialize(obj))

    # ── diff ─────────────────────────────────────────────────────────

    def diff(self, request, pk=None):
        process_id = self._process_id(self)
        active = (
            ProcessDefinition.objects.filter(
                process_id=process_id, status=STATUS_ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )
        if active is None:
            return Response({"diff": None, "reason": "no_active_version"})

        current = (
            ProcessDefinition.objects.filter(process_id=process_id)
            .exclude(status=STATUS_ACTIVE)
            .order_by("-created_at")
            .first()
        ) or active

        added, removed, changed = _diff_dict(active.definition, current.definition)
        return Response(
            {
                "process_id": process_id,
                "from_version": active.version,
                "to_version": current.version,
                "added": added,
                "removed": removed,
                "changed": changed,
            }
        )

    # ── autonomy dial ────────────────────────────────────────────────

    def autonomy(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))
        dial = {
            step.get("id"): step.get("autonomy")
            for step in (obj.definition or {}).get("steps", [])
            if isinstance(step, dict) and step.get("id")
        }
        return Response(dial)

    def set_autonomy(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))

        serializer = AutonomyDialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dial = serializer.validated_data["dial"]

        steps = list((obj.definition or {}).get("steps", []))
        by_id = {
            step.get("id"): idx
            for idx, step in enumerate(steps)
            if isinstance(step, dict) and step.get("id")
        }
        for step_id, autonomy in dial.items():
            if step_id not in by_id:
                return self._invalid(
                    f"Unknown step {step_id!r}; known steps: {sorted(by_id)}."
                )
            if autonomy not in VALID_AUTONOMY:
                return self._invalid(
                    f"Invalid autonomy {autonomy!r}; expected one of {sorted(VALID_AUTONOMY)}."
                )

        for step_id, autonomy in dial.items():
            idx = by_id[step_id]
            steps[idx] = dict(steps[idx])
            steps[idx]["autonomy"] = autonomy

        doc = dict(obj.definition or {})
        doc["steps"] = steps
        obj.definition = doc
        obj.save()
        return Response(
            {
                step.get("id"): step.get("autonomy")
                for step in steps
                if isinstance(step, dict) and step.get("id")
            }
        )

    # ── kill switch ──────────────────────────────────────────────────

    def kill(self, request, pk=None):
        obj = self._latest(self._process_id(self))
        if obj is None:
            return self._not_found(self._process_id(self))

        serializer = KillSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc = dict(obj.definition or {})
        doc["kill_switch"] = bool(serializer.validated_data["enabled"])
        obj.definition = doc
        obj.save()
        return Response(
            {
                "process_id": obj.process_id,
                "kill_switch": bool(doc.get("kill_switch", False)),
            }
        )
