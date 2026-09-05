"""Plugin: get_work_objectives — retrieve saved objectives so Pulse can resume them."""
from __future__ import annotations

import logging

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.get_work_objectives")


class GetWorkObjectives(ToolPlugin):
    name = "get_work_objectives"
    description = (
        "Retrieve the user's saved work objectives. Use when the user asks "
        "'where did we get to?', 'what were we working on?', 'resume my investigation', "
        "or similar. Returns a list of open objectives with their current status."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "status_filter": {
                "type": "string",
                "enum": ["open", "in_progress", "waiting_for_user", "all"],
                "default": "open",
                "description": "Filter by status. Use 'all' to see completed objectives too.",
            },
        },
        "required": [],
    }
    requires_confirmation = False
    chat_visible = True

    async def execute(self, args: dict, *, ctx) -> dict:
        from asgiref.sync import sync_to_async

        from ai.models.core import WorkObjective

        status_filter = args.get("status_filter", "open") or "open"

        if not ctx.host_user_id or not ctx.instance_id:
            return {"status": "error", "error": "No authenticated user"}

        qs = WorkObjective.objects.filter(
            instance_id=ctx.instance_id,
            host_user_id=ctx.host_user_id,
        )
        if status_filter != "all":
            statuses = (
                ["open", "in_progress", "waiting_for_user"]
                if status_filter == "open" else [status_filter]
            )
            qs = qs.filter(status__in=statuses)

        rows = await sync_to_async(list, thread_sensitive=True)(
            qs.order_by("-updated_at")[:10].values(
                "id", "title", "description", "status", "latest_summary",
                "pending_question", "updated_at", "created_at",
            )
        )

        items = [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "status": r["status"],
                "summary": r["latest_summary"],
                "pending_question": r["pending_question"],
                "last_updated": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ]

        if not items:
            return {
                "status": "no_match",
                "hint": "No saved objectives found. Ask me to 'save this investigation' to create one.",
            }

        return {"status": "resolved", "objectives": items, "count": len(items)}
