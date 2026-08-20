"""
Unified Agent Catalog REST API (Phase W3-D).

Endpoints (mounted at ``{api_prefix}/ai/catalog/`` — see ``config/urls.py``):

    GET    /carbon-api/ai/catalog/                list agent roles (+ declared edges + skills)
    POST   /carbon-api/ai/catalog/                register an agent (staff only, RULE_21)
    GET    /carbon-api/ai/catalog/{id}/           one agent (metadata + edges + skills + last admission)
    PATCH  /carbon-api/ai/catalog/{id}/           update an agent in place (staff only)
    DELETE /carbon-api/ai/catalog/{id}/           soft-delete an agent (staff only)
    GET    /carbon-api/ai/catalog/topology/       declared handoff graph (ADR-001)
    GET    /carbon-api/ai/catalog/skills/         skill catalog + admission status
    GET    /carbon-api/ai/catalog/index/          federated index (DB agents + plugin discovery)

    Literal ``agents/`` aliases match the W3-D spec paths:
    ``/carbon-api/ai/catalog/agents/`` and ``/carbon-api/ai/catalog/agents/{id}/``.

Reads: authenticated only.  Writes: staff/admin only (``IsAuthenticated`` +
``request.user.is_staff`` — RULE_21: registering/removing an agent is an
explicit admin act, not a user-initiated consent flow).

No engine internals are touched — everything delegates to
:mod:`ai.catalog_service`.
"""

from __future__ import annotations

import logging

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.catalog_service import AgentNotFoundError, CatalogService

logger = logging.getLogger("carbon.ai.catalog_api")


def _agent_role_choices():
    from ai.engine.core.models import AGENT_ROLES

    return sorted(AGENT_ROLES)


def _role_error(role: str) -> str:
    return f"Unknown agent role {role!r}; must be one of {_agent_role_choices()}."


class AgentCreateSerializer(serializers.Serializer):
    """POST /catalog/ — register (or upsert by instance+name) an agent role."""

    name = serializers.CharField(required=True, allow_blank=False, max_length=200)
    role = serializers.ChoiceField(choices=_agent_role_choices())
    tool_set = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    playbook_blocks = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    model_override = serializers.CharField(
        required=False, allow_blank=True, default=None
    )
    max_turns = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=3
    )


class AgentUpdateSerializer(serializers.Serializer):
    """PATCH /catalog/{id}/ — all fields optional (PATCH semantics).

    ``name`` is intentionally absent: it is the engine upsert key
    (``register_agent`` keys on instance_id + name), so renames would silently
    create a second agent.  Rename = delete + create (both staff-gated).
    """

    role = serializers.ChoiceField(choices=_agent_role_choices(), required=False)
    tool_set = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    playbook_blocks = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    model_override = serializers.CharField(
        required=False, allow_blank=True, default=None
    )
    max_turns = serializers.IntegerField(
        required=False, min_value=1, max_value=100
    )


class CatalogViewSet(viewsets.GenericViewSet):
    """Unified agent catalog — reads for any user, writes for staff only."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service: CatalogService | None = None

    @property
    def service(self) -> CatalogService:
        if self._service is None:
            self._service = CatalogService()
        return self._service

    @staticmethod
    def _admin_gate(request):
        """RULE_21: catalog writes are an explicit staff/admin act."""
        if not request.user.is_staff:
            return Response(
                {
                    "error": "admin_required",
                    "detail": "Catalog writes require a staff account.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @staticmethod
    def _validate_role(role: str):
        from ai.engine.core.models import AGENT_ROLES

        if role not in AGENT_ROLES:
            return Response(
                {"error": "invalid_role", "detail": _role_error(role)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @staticmethod
    def _unavailable(exc: Exception) -> Response:
        """Fail-visible error envelope (design §2) — never a bare 500."""
        logger.exception("catalog endpoint failed")
        return Response(
            {"error": "catalog_unavailable", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # ── Agents ───────────────────────────────────────────────────────────

    def list(self, request):
        """List agent roles; optional ``?role=`` filter."""
        role = request.query_params.get("role")
        if role is not None:
            gate = self._validate_role(role)
            if gate is not None:
                return gate
        try:
            return Response(self.service.list_agents(role=role))
        except Exception as exc:
            return self._unavailable(exc)

    def retrieve(self, request, pk=None):
        """One agent: metadata + incoming/outgoing handoffs + admitted skills
        + last admission log."""
        try:
            return Response(self.service.get_agent(pk))
        except AgentNotFoundError:
            return Response(
                {"error": "agent_not_found", "detail": f"Agent {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            return self._unavailable(exc)

    def create(self, request):
        """Register an agent role (staff only — RULE_21)."""
        gate = self._admin_gate(request)
        if gate is not None:
            return gate
        serializer = AgentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            agent = self.service.register_agent(**serializer.validated_data)
            return Response(agent, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response(
                {"error": "invalid_agent", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return self._unavailable(exc)

    def partial_update(self, request, pk=None):
        """Update an agent in place (staff only — RULE_21)."""
        gate = self._admin_gate(request)
        if gate is not None:
            return gate
        serializer = AgentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            agent = self.service.update_agent(pk, **serializer.validated_data)
            return Response(agent)
        except AgentNotFoundError:
            return Response(
                {"error": "agent_not_found", "detail": f"Agent {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response(
                {"error": "invalid_agent", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return self._unavailable(exc)

    def destroy(self, request, pk=None):
        """Soft-delete an agent (staff only — RULE_21)."""
        gate = self._admin_gate(request)
        if gate is not None:
            return gate
        try:
            return Response(self.service.remove_agent(pk))
        except AgentNotFoundError:
            return Response(
                {"error": "agent_not_found", "detail": f"Agent {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            return self._unavailable(exc)

    # ── Catalog surfaces ─────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="topology")
    def topology(self, request):
        """Declared handoff graph (ADR-001): ``{nodes, edges}``."""
        try:
            return Response(self.service.topology())
        except Exception as exc:
            return self._unavailable(exc)

    @action(detail=False, methods=["get"], url_path="skills")
    def skills(self, request):
        """Skill catalog + each skill's admission status."""
        try:
            return Response(self.service.list_skills())
        except Exception as exc:
            return self._unavailable(exc)

    @action(detail=False, methods=["get"], url_path="index")
    def federated_index(self, request):
        """Federated index: DB agents (source of truth) + plugin discovery."""
        role = request.query_params.get("role")
        if role is not None:
            gate = self._validate_role(role)
            if gate is not None:
                return gate
        try:
            return Response(self.service.federated_index(role=role))
        except Exception as exc:
            return self._unavailable(exc)
