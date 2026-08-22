"""``edit_plan`` / ``approve_plan`` — chat-native plan iteration + settle gate.

Completes the agentic orchestration lifecycle **inside the chat**, so Pulse can
run the full loop the user expects without bouncing to the Tasks panel for the
*planning* half:

    discuss → decompose → propose → (edit_plan) → "settled?" → (approve_plan)

The W3-A plans layer (``ai.plans_service.PlansService``) still owns every
state transition — these plugins are thin chat bridges (same status as
``plan_task``, RULE_20/RULE_21 compliant):

  * **``edit_plan``** — apply the user's chat feedback to the draft: a revised
    brief and/or ``step_deltas`` (add / remove / update steps).  Editing NEVER
    auto-approves: a non-pending plan drops back to ``pending_approval`` and
    the reply carries the step diff so the user can review the change
    (RULE_21).
  * **``approve_plan``** — the explicit "we're settled, convert it to a real
    task" gate.  Moves a pending plan → ``approved`` (the RULE_21 plan-level
    consent), then surfaces the Tasks panel for the actual run (which is a
    *separate*, explicit user action — execution never happens from chat).

Both resolve ``plan_id`` against the user's most recent plan when omitted, so
the agent can say "update the plan" / "go" without re-quoting the id.

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: nothing from domain apps; plan writes go
    through ``ai.plans_service.PlansService`` (host-side glue).
  * **RULE_21** — ``edit_plan`` is non-executing (draft mutation only,
    ``requires_confirmation=False``); ``approve_plan`` is the consent gate
    itself and still never executes steps.
  * **RULE_23** — outcome copy in product terms (plan, steps, status, diff).
"""
from __future__ import annotations

import logging
from typing import Any

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.plan_lifecycle")

_PLAN_ID_HINT = (
    "The plan id (optional — defaults to your most recent plan when omitted)."
)


async def _resolve_owner(ctx) -> Any | None:
    """Return the Django user for the chat session, or None."""
    if not ctx.host_user_id:
        return None
    from asgiref.sync import sync_to_async
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        return await sync_to_async(User.objects.get, thread_sensitive=True)(
            pk=ctx.host_user_id
        )
    except (User.DoesNotExist, ValueError):
        return None


async def _run_service(fn, *args):
    """Run a sync service call off the event loop.

    thread_sensitive=False (the thread pool) is deliberate: the plans service
    re-enters the async engine internally (``_run_async`` → the engine's own
    ``sync_to_async(thread_sensitive=True)`` DB calls). Nesting both on the
    single main-thread executor deadlocks ("Single thread executor already
    being used"). The regular pool avoids that and keeps the ORM writes off
    the event loop (no ``SynchronousOnlyOperation``).
    """
    from asgiref.sync import sync_to_async

    return await sync_to_async(fn, thread_sensitive=False)(*args)


async def _resolve_plan_id(service, user, plan_id: str | None) -> str:
    """Use the supplied plan id, else the user's most recent pending plan."""
    from ai.plans_service import STATUS_PENDING_APPROVAL

    if plan_id and plan_id.strip():
        return plan_id.strip()
    result = await _run_service(service.list_plans, user, 20)
    plans = result.get("plans") or []
    for p in plans:
        if p.get("status") == STATUS_PENDING_APPROVAL:
            return p.get("id", "")
    # Fall back to the most recent plan regardless of status.
    if plans:
        return plans[0].get("id", "")
    raise ValueError(
        "No plan found to act on — ask me to plan the task first (e.g. "
        "'plan the carbon standards study'), or give me a plan id."
    )


class EditPlan(ToolPlugin):
    name = "edit_plan"
    description = (
        "Revise an existing plan based on the user's chat feedback. Use it "
        "when the user wants to change the plan (add / remove / reword steps, "
        "or rewrite the brief) after you proposed it. Editing never executes "
        "or auto-approves — it returns the revised plan (with a diff of what "
        "changed) so you can re-present it and ask if it is settled."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "plan_id": {"type": "string", "description": _PLAN_ID_HINT},
            "brief": {
                "type": "string",
                "description": "Optional replacement task brief.",
            },
            "step_deltas": {
                "type": "array",
                "description": (
                    "Optional ordered edits: "
                    '{"action":"add","intent":"...","tool_name":"...",'
                    '"tool_args":{...},"depends_on":[...]}, '
                    '{"action":"remove","step_id":N}, or '
                    '{"action":"update","step_id":N,"intent":"...",...}.'
                ),
                "items": {"type": "object"},
            },
        },
    }
    requires_confirmation = False
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        user = await _resolve_owner(ctx)
        if user is None:
            return {"error": "No authenticated session — planning is unavailable."}

        brief = (args.get("brief") or "").strip() or None
        step_deltas = args.get("step_deltas")
        if not brief and not step_deltas:
            return {
                "error": (
                    "Tell me what to change — provide a new brief and/or "
                    "step_deltas (add / remove / update steps)."
                ),
            }

        from ai.plans_service import PlansService

        service = PlansService()
        try:
            plan_id = await _resolve_plan_id(service, user, args.get("plan_id"))
            result = await _run_service(
                service.edit_plan,
                user,
                plan_id,
                brief,
                step_deltas,
            )
        except ValueError as exc:
            return {"error": str(exc)}

        diff = result.get("diff") or {}
        steps = [
            {"step_id": s.get("step_id"), "intent": s.get("intent")}
            for s in (result.get("steps") or [])
        ]
        return {
            "requires_confirmation": False,
            "action": "plan_edited",
            "plan_id": result.get("id", ""),
            "status": result.get("status"),
            "replan_gate": result.get("replan_gate", False),
            "diff": diff,
            "steps": steps,
            "message": (
                f"Plan updated: {len(steps)} steps "
                f"(added {len(diff.get('added', []))}, "
                f"removed {len(diff.get('removed', []))}, "
                f"changed {len(diff.get('changed', []))}). "
                "Re-present the steps and confirm with the user before approving."
            ),
        }


class ApprovePlan(ToolPlugin):
    name = "approve_plan"
    description = (
        "Approve the settled plan and convert it into a real runnable task. "
        "Use it ONLY after the user has confirmed the plan is settled (e.g. "
        "they said 'yes', 'go', 'looks good'). Approval does NOT execute "
        "steps — it readies the plan so the user can run it (with per-step "
        "observation and an audit ledger) from the Tasks panel."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "plan_id": {"type": "string", "description": _PLAN_ID_HINT},
        },
    }
    requires_confirmation = False
    capability: str | None = None
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        user = await _resolve_owner(ctx)
        if user is None:
            return {"error": "No authenticated session — approval is unavailable."}

        from ai.plans_service import (
            PlanNotRunnableError,
            PlansService,
        )

        service = PlansService()
        try:
            plan_id = await _resolve_plan_id(service, user, args.get("plan_id"))
            result = await _run_service(service.approve_plan, user, plan_id)
        except (ValueError, PlanNotRunnableError) as exc:
            return {"error": str(exc)}

        steps = [
            {"step_id": s.get("step_id"), "intent": s.get("intent")}
            for s in (result.get("steps") or [])
        ]
        return {
            "requires_confirmation": False,
            "action": "plan_approved",
            "plan_id": result.get("id", ""),
            "status": result.get("status"),
            "steps": steps,
            "message": (
                f"Plan approved with {len(steps)} steps — it is now a real, "
                "runnable task. Open the Tasks panel to run it; each step is "
                "observed and recorded in the audit ledger."
            ),
        }
