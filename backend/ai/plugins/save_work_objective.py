"""Plugin: save_work_objective — persist a durable investigation objective."""
from __future__ import annotations

import logging

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.save_work_objective")


class SaveWorkObjective(ToolPlugin):
    name = "save_work_objective"
    description = (
        "Save the current investigation objective so the user can resume it later. "
        "Use this when the user says 'save this', 'come back to this', 'continue tomorrow', "
        "or similar. Record what has been found so far and what remains to be done."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short title for the objective (max 100 chars)."},
            "description": {"type": "string", "description": "Full description of what the user wants to achieve."},
            "progress_so_far": {"type": "string", "description": "Summary of what has already been found or completed."},
            "remaining_work": {"type": "string", "description": "What still needs to be done to complete the objective."},
            "acceptance_criteria": {"type": "string", "description": "How to know when the objective is complete.", "default": ""},
        },
        "required": ["title", "description", "progress_so_far", "remaining_work"],
    }
    requires_confirmation = False
    chat_visible = True

    async def execute(self, args: dict, *, ctx) -> dict:
        from asgiref.sync import sync_to_async

        from ai.models.core import WorkObjective

        title = (args.get("title") or "").strip()[:100]
        description = (args.get("description") or "").strip()
        progress = (args.get("progress_so_far") or "").strip()
        remaining = (args.get("remaining_work") or "").strip()
        criteria = (args.get("acceptance_criteria") or "").strip()

        if not title or not description:
            return {"status": "error", "error": "title and description are required"}

        if not ctx.host_user_id or not ctx.instance_id:
            return {"status": "error", "error": "No authenticated user — cannot save objective"}

        summary = (
            f"**Found so far:** {progress}\n\n**Still to do:** {remaining}"
            if progress else remaining
        )

        obj = await sync_to_async(WorkObjective.objects.create, thread_sensitive=True)(
            instance_id=ctx.instance_id,
            host_user_id=ctx.host_user_id,
            conversation_id=ctx.conversation_id or "",
            title=title,
            description=description,
            acceptance_criteria=criteria,
            status="open",
            latest_summary=summary,
            evidence_json=[],
        )

        logger.info("WorkObjective created id=%s user=%s title=%r", obj.id, ctx.host_user_id, title)

        return {
            "status": "saved",
            "objective_id": obj.id,
            "title": title,
            "message": (
                f"Objective saved — you can ask me 'where did we get to on {title}?' "
                "in any future conversation to resume."
            ),
        }
