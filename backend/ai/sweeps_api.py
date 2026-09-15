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
        from ai.models import PulseHeartbeat
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

        latest_heartbeats: dict[tuple[str, str], "PulseHeartbeat"] = {}
        for row in scope_ai_queryset(
            PulseHeartbeat.objects, request.user
        ).order_by("instance_id", "loop", "-started_at"):
            key = (row.instance_id, row.loop)
            latest_heartbeats.setdefault(key, row)

        heartbeats = [
            {
                "instance_id": row.instance_id,
                "loop": row.loop,
                "status": row.status,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "items_produced": row.items_produced,
                "llm_calls": row.llm_calls,
                "cost_usd": str(row.cost_usd),
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in latest_heartbeats.values()
        ]

        return Response(
            {
                "scheduler_running": bool(live.get("scheduler_running", False)),
                "tasks": tasks,
                "heartbeats": heartbeats,
                "live": live,
            }
        )
