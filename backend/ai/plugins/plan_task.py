"""``plan_task`` — turn a task brief into a reviewable plan (chat bridge).

The W3-A plans layer (``ai.plans_service.PlansService`` → ``/carbon-api/ai/plans/``)
owns the plan lifecycle: brief → pending_approval plan → approve → SSE streamed
run → per-step consent → durable audit ledger.  This plugin exposes that
capability to the **workspace chat agent** as one named tool, so

    "plan this task: audit the emissions uploads for completeness"

produces a REAL plan (decomposed steps + plan id + status) instead of prose
fallback — the missing last mile between the Tasks panel and the chat.

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: this module imports nothing from
    ``dq``/``catalog``/``mdm``/``emissions``/``accounts``/``core``.  The plan
    write goes through ``ai.plans_service.PlansService`` (host-side glue, same
    status as ``ai.host_executor`` / ``ai.access_manifest``), which is the only
    module touching the engine planner and the ``Run``/``RunStep`` models.
  * **RULE_21** — planning is NON-mutating: ``requires_confirmation=False``,
    nothing executes here.  The created plan lands in ``pending_approval`` and
    the RULE_21 gate is the plan-approval step itself (approve + run stay in
    the Tasks panel — chat never auto-executes).
  * **RULE_23** — outcome copy: the result speaks in product terms (plan,
    steps, ``pending_approval``, "review and approve in the Tasks panel"),
    never engine class names (no "ReActLoop", no "Run row").
"""
from __future__ import annotations

import logging
from typing import Any

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.plan_task")


class PlanTask(ToolPlugin):
    name = "plan_task"
    description = (
        "Turn a task brief into a reviewable execution plan. "
        "Use it when the user asks you to plan, orchestrate, or run a task, "
        "e.g. 'plan the monthly data quality audit' or 'set up a task to "
        "compare emissions quarters'. The plan is drafted for review — it is "
        "NOT executed. The user approves and runs it from the Tasks panel."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": "The task to plan, in the user's own words.",
            },
        },
        "required": ["brief"],
    }
    requires_confirmation = False
    # Planning is available to any authenticated chat user; the created plan
    # is owner-scoped and nothing executes without approval (RULE_21).
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        brief = (args.get("brief") or "").strip()

        if not ctx.host_user_id:
            return {
                "requires_confirmation": False,
                "error": "No authenticated session — planning is unavailable.",
            }
        if not brief:
            return {
                "requires_confirmation": False,
                "error": (
                    "A task brief is required — tell me what you want planned, "
                    "for example: 'plan the monthly data quality audit'."
                ),
            }

        from asgiref.sync import sync_to_async
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = await sync_to_async(
                User.objects.get, thread_sensitive=True
            )(pk=ctx.host_user_id)
        except (User.DoesNotExist, ValueError):
            # ValueError: non-numeric pk (Django field-cast) — same graceful
            # path as a missing user; planning just can't resolve the owner.
            return {
                "requires_confirmation": False,
                "error": "Session user not found — planning is unavailable.",
            }

        # W3-A create_plan: decompose via SkillAwarePlanner (worker-threaded
        # engine session) then persist a pending_approval Run + RunStep rows.
        # Same sync service the plans API views call — owner-scoped, CBAC.
        from ai.plans_service import PlansService

        service = PlansService()
        try:
            # NOTE: thread_sensitive=False (the thread pool, NOT the single
            # main-thread executor) is required here. create_plan internally
            # re-enters the async engine via _run_async, whose own DB calls use
            # sync_to_async(thread_sensitive=True). Nesting both on the same
            # single-thread executor deadlocks ("Single thread executor already
            # being used") and silently collapses the plan to one step.
            plan = await sync_to_async(service.create_plan, thread_sensitive=False)(
                user, brief, conversation_id=ctx.conversation_id or ""
            )
        except ValueError as exc:
            # Empty/too-long brief — service-level validation copy.
            return {
                "requires_confirmation": False,
                "error": str(exc),
            }

        steps = [
            {
                "step_id": s.get("step_id"),
                "intent": s.get("intent"),
                "tool_name": s.get("tool_name") or "reason",
            }
            for s in (plan.get("steps") or [])
        ]
        plan_id = plan.get("id") or ""
        short_id = plan_id[:8]
        return {
            "requires_confirmation": False,
            "action": "plan_created",
            "plan_id": plan_id,
            "status": plan.get("status", "pending_approval"),
            "pattern": plan.get("pattern", "custom"),
            "brief": plan.get("brief", brief),
            "steps": steps,
            "message": (
                f"Plan {short_id} drafted with {len(steps)} steps "
                f"(status: {plan.get('status')}). Nothing has executed — "
                "review and approve it in the Tasks panel."
            ),
        }
