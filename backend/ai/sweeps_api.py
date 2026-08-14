"""Phase D — read-only sweep-status API for the cognition scheduler.

GET /carbon-api/ai/pulse/sweeps/

Reports the durable per-task ``CognitionSweepRun`` ledger (one row per task
name, upserted by ``loop._tracked``) plus the in-process loop status under a
``"live"`` key (honestly empty in the web process, where the scheduler is not
running).

Read-only by structure: a single GET-only ``APIView`` with ``IsAuthenticated``.
No mutation surface, no model viewset.
"""

import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.permissions import AdminOrSuperuserOnly

logger = logging.getLogger("carbon.ai.sweeps_api")


class SweepsStatusView(APIView):
    """GET sweeps/ — durable sweep-run ledger + live loop status."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        from ai.engine.cognition.loop import get_loop_status
        from ai.models.core import CognitionSweepRun

        live = {}
        try:
            live = get_loop_status()
        except Exception as exc:  # noqa: BLE001 — never 500 the console
            logger.warning("loop status unavailable: %s", exc)

        # Latest row per task_name (defensive: the loop upserts one row per
        # task, but tolerate any historical duplicates by keeping the newest).
        latest: dict[str, "CognitionSweepRun"] = {}
        for row in scope_ai_queryset(
            CognitionSweepRun.objects, request.user
        ).order_by("task_name", "-last_run"):
            latest.setdefault(row.task_name, row)

        tasks = [
            {
                "task_name": row.task_name,
                "last_run": row.last_run.isoformat() if row.last_run else None,
                "last_status": row.last_status,
                "last_duration_ms": row.last_duration_ms,
                "run_count": row.run_count,
                "last_error": row.last_error,
            }
            for row in latest.values()
        ]

        return Response(
            {
                "scheduler_running": bool(live.get("scheduler_running", False)),
                "tasks": tasks,
                "live": live,
            }
        )
