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

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import AdminOrSuperuserOnly
from ai.engine_runtime import get_task, list_modules
from ai.intelligence import CarbonIntelligence

logger = logging.getLogger("carbon.ai.ops_api")


class PulseHealthView(APIView):
    """GET /health/ — engine health plus advertised modules."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

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

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

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

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request, task_id):
        return Response(get_task(task_id))


# ── Domain App Manifest API ───────────────────────────────────────────────
# GET /carbon-api/ai/apps/            → all registered domain manifests
# GET /carbon-api/ai/apps/{app_id}/  → single domain manifest
#
# Used by the frontend to discover:
#   - Which task types each domain app supports
#   - Which entry-point buttons to render on domain pages
#   - Which starter chips to show in the AI workspace empty state
#
# Authentication: IsAuthenticated (non-admin users need to see their app's
# capabilities). No capability guard required — manifests contain no secrets.


class DomainAppManifestListView(APIView):
    """GET /apps/ — list manifests for all registered domain apps."""

    def get(self, request):
        from ai.domain_protocol import all_manifests
        return Response({"apps": all_manifests(), "count": len(all_manifests())})


class DomainAppManifestDetailView(APIView):
    """GET /apps/{app_identifier}/ — manifest for a single domain app."""

    def get(self, request, app_identifier):
        from ai.domain_protocol import get_manifest, has_domain
        if not has_domain(app_identifier):
            return Response(
                {"detail": f"Domain '{app_identifier}' is not registered."},
                status=404,
            )
        return Response(get_manifest(app_identifier))
