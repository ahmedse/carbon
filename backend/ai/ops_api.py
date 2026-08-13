"""
AI Pulse Ops API — read-only in-process engine observability surface.

GET  /carbon-api/ai/pulse/health/
GET  /carbon-api/ai/pulse/modules/
GET  /carbon-api/ai/pulse/tasks/{task_id}/

Read-only by structure: every view is a GET-only ``APIView`` (no models
back these endpoints, so no viewset). The engine runs in-process — there
is no HTTP transport to Pulse — and these endpoints advertise its
capabilities and expose task status for the AI admin console.
"""

import logging
from dataclasses import asdict

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.engine_runtime import get_task, list_modules
from ai.intelligence import CarbonIntelligence

logger = logging.getLogger("carbon.ai.ops_api")


class PulseHealthView(APIView):
    """GET /health/ — engine health plus advertised modules."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            status = CarbonIntelligence().health_check()
            return Response(asdict(status))
        except Exception as exc:  # noqa: BLE001 — never 500 the console
            logger.exception("pulse health check failed")
            return Response(
                {
                    "name": "pulse",
                    "version": "unknown",
                    "healthy": False,
                    "modules_available": [],
                    "error": str(exc),
                }
            )


class PulseModulesView(APIView):
    """GET /modules/ — the task types the in-process engine advertises."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = list_modules()
        modules = data.get("modules", [])
        return Response({"modules": modules, "count": len(modules)})


class PulseTaskStatusView(APIView):
    """GET /tasks/{task_id}/ — in-process task status (fail-visible).

    ``engine_runtime.get_task`` never raises: unknown ids return a
    fail-visible ``{status: pulse_unavailable, error: {code: not_found}}``
    envelope, which we pass through unchanged.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        return Response(get_task(task_id))
