"""
Durable execution REST API (Phase W3-E).

Endpoints (mounted at ``{api_prefix}/ai/runs/`` — see ``config/urls.py``):

    GET  /carbon-api/ai/runs/{run_id}/timeline/   ordered event log for a run
    POST /carbon-api/ai/runs/{run_id}/resume/     crash-safe resume (reconcile + re-enter)
    POST /carbon-api/ai/runs/{run_id}/replay/     consent-gated replay staging (RULE_21)

All reads are owner-scoped (CBAC via ``Run.host_user_id`` — the same pattern
as ``ai.plans_api``); writes are explicit and user-initiated. Replay requires
an explicit ``{"confirm": true}`` body — it stages the replay and never
auto-starts execution.

No engine internals are touched — everything delegates to
:mod:`ai.durable_service` (thin view layer only).
"""

from __future__ import annotations

import logging

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai.durable_service import DurableExecutionService, PlanConsentError
from ai.plans_service import PlanNotAccessibleError, PlanNotRunnableError

logger = logging.getLogger("carbon.ai.durable_api")


class ReplayConsentSerializer(serializers.Serializer):
    """POST /runs/{id}/replay/ — explicit RULE_21 consent gate."""

    confirm = serializers.BooleanField(required=True)


class RunViewSet(viewsets.GenericViewSet):
    """Durable execution surface for plan runs (timeline / resume / replay)."""

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service: DurableExecutionService | None = None

    @property
    def service(self) -> DurableExecutionService:
        if self._service is None:
            self._service = DurableExecutionService()
        return self._service

    @staticmethod
    def _unavailable(exc: Exception) -> Response:
        """Fail-visible envelope (design §2) — never a bare 500."""
        logger.exception("durable endpoint failed")
        return Response(
            {"error": "durable_unavailable", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @action(detail=True, methods=["get"], url_path="timeline",
            url_name="run-timeline")
    def timeline(self, request, pk=None):
        """Ordered event log for one run (read-only)."""
        try:
            return Response(self.service.timeline(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            return self._unavailable(exc)

    @action(detail=True, methods=["post"], url_path="resume",
            url_name="run-resume")
    def resume(self, request, pk=None):
        """Crash-safe resume — reconcile interrupted steps, then re-enter."""
        try:
            return Response(self.service.resume_run(request.user, pk))
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanNotRunnableError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            return self._unavailable(exc)

    @action(detail=True, methods=["post"], url_path="replay",
            url_name="run-replay")
    def replay(self, request, pk=None):
        """Stage a deterministic replay — RULE_21 consent gate.

        The body must carry ``{"confirm": true}``; the replay is staged only
        (step reset + ``replaying`` marker) and never auto-starts execution.
        """
        serializer = ReplayConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(
                self.service.replay_run(
                    request.user, pk,
                    confirm=serializer.validated_data["confirm"],
                )
            )
        except PlanNotAccessibleError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_404_NOT_FOUND
            )
        except (PlanNotRunnableError, PlanConsentError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:  # noqa: BLE001 - fail-visible contract
            return self._unavailable(exc)
