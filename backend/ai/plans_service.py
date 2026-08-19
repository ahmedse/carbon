"""
Agentic Task Orchestration — plan lifecycle service (Sprint 23 W3-A).

Wraps the already-built engine machinery (SkillAwarePlanner decompose →
ReActLoop execution → durable Run/RunStep ledger) behind a user-initiated,
reviewable task product:

    brief → pending_approval plan (reviewable) → approve → SSE streamed run
    → per-step consent (confirm/decline) → durable audit ledger.

Design contracts (TASKS.md W3-A — backend):

  * NO changes under ``backend/ai/engine/`` — this module only *calls* the
    engine's public seams (planner, ReActLoop, CarbonHostExecutor, store).
  * Reuses the existing ``Run`` / ``RunStep`` Django models
    (``ai.models.core``) — no new migrations
    (gate: ``makemigrations --check --dry-run`` stays clean).
  * The approved plan is the executed plan: ``run_plan`` rebuilds the ``Plan``
    from ``plan_json`` and drives ReActLoop with ``resume_run_id=plan_id`` so
    the engine reuses the plan's Run row and RunStep rows — never a
    duplicate ledger row.
  * Consent: plan-level approve (RULE_21) + step-level confirm/decline
    reusing ``CarbonHostExecutor.confirm_execution`` / ``.decline_execution``
    (the same seam as the workspace ``tool-executions/confirm|decline``
    endpoints).
  * Outcome copy only (RULE_23): frame types and statuses are product terms
    (``step_start`` / ``step_result`` / ``step_confirm`` / ``done`` …), never
    engine class names.
"""

from __future__ import annotations

import json
import logging
import queue
import threading

from django.utils import timezone

logger = logging.getLogger("carbon.ai.plans_service")

# Engine instance namespace (mirrors the chat/action paths).
PLAN_INSTANCE_ID = "carbon"

# Run statuses this service owns (superset of the engine's status set).
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# RunStep statuses (engine set: pending|running|awaiting_approval|
# completed|failed|skipped).
STEP_PENDING = "pending"
STEP_AWAITING_APPROVAL = "awaiting_approval"
STEP_COMPLETED = "completed"
STEP_FAILED = "failed"
STEP_SKIPPED = "skipped"

# Statuses from which a plan may (re)enter execution.
_RUNNABLE_STATUSES = {STATUS_APPROVED, STATUS_PAUSED}


class PlanNotAccessibleError(Exception):
    """Raised when the plan does not belong to the requesting user."""


class PlanNotRunnableError(Exception):
    """Raised when a plan cannot be executed in its current state."""


class PlanStepError(Exception):
    """Raised for step-level consent errors (missing/not pending/not owned)."""


def _run_async(coro):
    """Bridge an async engine call into the sync Django view context.

    Mirrors ``ai.engine_runtime._run_async`` — the engine is async, so we
    bridge with ``asyncio.run`` (or a worker thread when a loop is already
    running, e.g. inside pytest-asyncio).
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class PlansService:
    """Plan lifecycle: create → review → approve → run → consent → ledger."""

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_owned_run(user, plan_id):
        """Fetch a plan row scoped to the requesting user (CBAC)."""
        from ai.models.core import Run

        try:
            run = Run.objects.get(id=plan_id, host_user_id=str(user.pk))
        except Run.DoesNotExist:
            raise PlanNotAccessibleError(f"Plan {plan_id} not found.")
        return run

    @staticmethod
    def _get_owned_step(run, step_id):
        from ai.models.core import RunStep

        try:
            step = RunStep.objects.get(
                run_id=run.id, step_index=int(step_id)
            )
        except (RunStep.DoesNotExist, ValueError, TypeError):
            raise PlanStepError(f"Step {step_id} not found on plan {run.id}.")
        return step

    @staticmethod
    def _serialize_run(run, steps=None):
        """Product-facing plan payload (RULE_23 — outcome terms only)."""
        from ai.models.core import RunStep

        plan_json = run.plan_json or {}
        if steps is None:
            steps = list(
                RunStep.objects.filter(run_id=run.id).order_by("step_index")
            )
        return {
            "id": run.id,
            "status": run.status,
            "brief": run.user_message,
            "pattern": plan_json.get("pattern", "custom"),
            "source": plan_json.get("source", "single_step"),
            "skill_name": plan_json.get("skill_name"),
            "synthesis_instruction": plan_json.get("synthesis_instruction"),
            "conversation_id": run.conversation_id,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "steps": [
                {
                    "step_id": s.step_index,
                    "intent": s.intent,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args_json or {},
                    "depends_on": s.depends_on_json or [],
                    "status": s.status,
                    "draft_text": s.draft_text,
                    "critic_verdict": s.critic_verdict,
                    "error": s.error,
                }
                for s in steps
            ],
        }

    @staticmethod
    def _rebuild_plan(run):
        """Rebuild the engine ``Plan`` dataclass from the persisted plan_json.

        The approved plan is the executed plan — no re-decomposition at run
        time (review contract).
        """
        from ai.engine.cognition.plan.planner import Plan, PlanStep

        plan_json = run.plan_json or {}
        steps = [
            PlanStep(
                step_id=int(s.get("step_id", 0)),
                intent=s.get("intent", ""),
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args") or {},
                skill_name=s.get("skill_name"),
                depends_on=s.get("depends_on") or [],
                is_mutation=bool(s.get("is_mutation", False)),
                dry_run_supported=bool(s.get("dry_run_supported", False)),
            )
            for s in plan_json.get("steps", [])
        ]
        return Plan(
            pattern=plan_json.get("pattern", "custom"),
            steps=steps,
            synthesis_instruction=plan_json.get("synthesis_instruction", ""),
            source=plan_json.get("source", "custom"),
            skill_name=plan_json.get("skill_name"),
            needs_confirmation=bool(plan_json.get("needs_confirmation", False)),
        )

    # ── Create / read ─────────────────────────────────────────────────────

    def create_plan(self, user, brief: str, conversation_id: str = "") -> dict:
        """Decompose a brief into a reviewable plan (pending_approval).

        Planning only — NO execution (RULE_21: review before mutation).
        The engine planner runs on its own store session via a worker thread;
        the resulting Plan is persisted as the Run row's ``plan_json`` plus
        one RunStep row per step.
        """
        from ai.models.core import Run, RunStep, generate_uuid
        from ai.engine.core.config import get_settings
        from ai.engine.core.database import get_session_factory
        from ai.engine.cognition.plan.planner import SkillAwarePlanner
        from ai.engine.skills.registry import SkillRegistry

        brief = (brief or "").strip()
        if not brief:
            raise ValueError("brief is required.")
        if len(brief) > 4000:
            raise ValueError("brief is too long (max 4000 characters).")

        settings = get_settings()
        user_pk = str(user.pk)

        async def _decompose():
            factory = get_session_factory(PLAN_INSTANCE_ID)
            async with factory() as db:
                registry = SkillRegistry(db)
                planner = SkillAwarePlanner(model=settings.LLM_MODEL)
                plan = await planner.decompose(
                    utterance=brief,
                    skill_registry=registry,
                    instance_id=PLAN_INSTANCE_ID,
                    user_id=user_pk,
                )
            return plan

        plan = _run_async(_decompose())

        run_id = generate_uuid()
        run = Run(
            id=run_id,
            instance_id=PLAN_INSTANCE_ID,
            conversation_id=conversation_id or "",
            host_user_id=user_pk,
            user_message=brief,
            status=STATUS_PENDING_APPROVAL,
            plan_json=json.loads(json.dumps(plan.__dict__, default=str)),
        )
        run.save()

        for step in plan.steps:
            RunStep.objects.create(
                run_id=run_id,
                step_index=step.step_id,
                intent=step.intent,
                tool_name=step.tool_name,
                tool_args_json=step.tool_args or {},
                depends_on_json=step.depends_on or [],
                status=STEP_PENDING,
            )

        logger.info(
            "Plan created id=%s user=%s steps=%d source=%s",
            run_id, user_pk, len(plan.steps), plan.source,
        )
        return self.get_plan(user, run_id)

    def get_plan(self, user, plan_id: str) -> dict:
        """Fetch a plan + its steps (owner-scoped)."""
        run = self._get_owned_run(user, plan_id)
        from ai.models.core import RunStep

        steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
        return self._serialize_run(run, steps=steps)

    def list_plans(self, user, limit: int = 50) -> dict:
        """List the requesting user's plans, newest first."""
        from ai.models.core import Run

        limit = max(1, min(int(limit or 50), 100))
        runs = list(
            Run.objects.filter(
                host_user_id=str(user.pk), instance_id=PLAN_INSTANCE_ID
            ).order_by("-created_at")[:limit]
        )
        return {
            "plans": [self._serialize_run(run) for run in runs],
            "count": len(runs),
        }

    # ── Consent: plan-level approve ───────────────────────────────────────

    def approve_plan(self, user, plan_id: str) -> dict:
        """Approve a pending_approval plan for execution (RULE_21 gate).

        Returns the plan payload; execution itself happens on ``run``.
        """
        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PENDING_APPROVAL:
            raise PlanNotRunnableError(
                f"Only pending plans can be approved (status: {run.status})."
            )
        run.status = STATUS_APPROVED
        run.save(update_fields=["status", "updated_at"])
        logger.info("Plan approved id=%s user=%s", plan_id, str(user.pk))
        return self.get_plan(user, plan_id)

    def decline_plan(self, user, plan_id: str) -> dict:
        """Decline a pending_approval plan — nothing is executed."""
        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PENDING_APPROVAL:
            raise PlanNotRunnableError(
                f"Only pending plans can be declined (status: {run.status})."
            )
        run.status = STATUS_CANCELLED
        run.save(update_fields=["status", "updated_at"])
        from ai.models.core import RunStep

        RunStep.objects.filter(run_id=run.id, status=STEP_PENDING).update(
            status=STEP_SKIPPED
        )
        return self.get_plan(user, plan_id)

    # ── Execution: SSE streamed run ───────────────────────────────────────

    def run_plan_stream(self, user, plan_id: str):
        """Run an approved/paused plan, streaming SSE frames.

        Frame protocol (W3-A)::

            {"type": "plan_start", "plan": {...}}
            {"type": "step_start", "plan_id", "step_id", "intent"}
            {"type": "step_result", "plan_id", "step_id", "status", ...}
            {"type": "step_confirm", "plan_id", "step_id", "message"}   (consent)
            {"type": "step_end", "plan_id", "step_id", "status"}
            {"type": "done", "plan_id", "status": completed|paused|stopped|failed,
             "final_response"}
            {"type": "error", "error": ...}

        The engine ReActLoop runs to completion (or pauses at a consent gate)
        on a worker thread; frames are produced afterwards from the durable
        Run/RunStep rows — never mid-Loop internals.
        """
        q: queue.Queue = queue.Queue()

        def _collect():
            try:
                for frame in self._run_plan_frames_sync(user, plan_id):
                    q.put(frame)
            except Exception as exc:  # noqa: BLE001 - fail-visible contract
                logger.exception("plan run failed plan=%s", plan_id)
                q.put({"type": "error", "error": f"Plan run failed: {exc}"})
            finally:
                q.put(None)

        threading.Thread(target=_collect, daemon=True).start()

        while True:
            frame = q.get()
            if frame is None:
                break
            yield frame

    def _run_plan_frames_sync(self, user, plan_id: str):
        """Sync wrapper yielding frames from the async engine run.

        ``asyncio.run`` cannot drive an async *generator* directly, so the
        async generator is drained inside a collector coroutine first.
        """
        async def _collect():
            frames = []
            async for frame in self._run_plan_frames(user, plan_id):
                frames.append(frame)
            return frames

        yield from _run_async(_collect())

    async def _run_plan_frames(self, user, plan_id: str):
        """Async generator — one run of the ReAct loop over the plan."""
        from asgiref.sync import sync_to_async

        from ai.models.core import RunStep
        from ai.engine.core.database import get_session_factory
        from ai.engine.cognition.plan.loop import ReActLoop
        from ai.engine.cognition.turn.draft import DraftWitness
        from ai.engine.cognition.turn.critic import CriticWitness
        from ai.engine.llm.prompts import build_chat_prompt
        from ai.engine_runtime import (
            _build_chat_user_info,
            _carbon_instance_config,
        )
        from ai.host_executor import CarbonHostExecutor

        # Django ORM is sync-only — inside this async generator every ORM
        # touchpoint runs through thread-sensitive sync_to_async (same
        # thread, same DB connection).
        run = await sync_to_async(self._get_owned_run)(user, plan_id)
        if run.status not in _RUNNABLE_STATUSES:
            yield {
                "type": "error",
                "error": (
                    f"Plan is not runnable (status: {run.status}). "
                    "Approve it first, or confirm/decline the pending step "
                    "to resume a paused plan."
                ),
            }
            return

        user_pk = str(user.pk)
        plan = self._rebuild_plan(run)
        instance_config = _carbon_instance_config(user_pk)
        user_info = _build_chat_user_info(user_pk)
        conversation_id = run.conversation_id or f"plan-{run.id}"

        # Arm the engine resume path: a paused-status run reuses the plan's
        # own Run row + RunStep rows (no duplicate ledger).
        run.status = STATUS_PAUSED
        await sync_to_async(run.save)(update_fields=["status", "updated_at"])

        yield {
            "type": "plan_start",
            "plan_id": run.id,
            "status": run.status,
            "plan": {
                "brief": run.user_message,
                "pattern": plan.pattern,
                "source": plan.source,
                "skill_name": plan.skill_name,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "intent": s.intent,
                        "tool_name": s.tool_name,
                        "depends_on": s.depends_on,
                    }
                    for s in plan.steps
                ],
            },
        }

        config = instance_config or {}
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            executor = CarbonHostExecutor(
                db=db,
                instance_config=instance_config,
                user_token=f"inproc:carbon:{user_pk}",
                host_user_id=user_pk,
            )
            system_prompt = await build_chat_prompt(
                instance_name=config.get("display_name", "Carbon"),
                system_description=config.get("description", ""),
                user_info=user_info,
                persona=config.get("persona"),
                api_catalog=config.get("api_catalog"),
                navigation_routes=config.get("navigation_routes"),
                domain_topics=config.get("domain_topics"),
                instance_config=config,
                conversation_id=conversation_id,
                instance_id=PLAN_INSTANCE_ID,
            )
            loop = ReActLoop(
                draft_witness=DraftWitness(executor=executor),
                critic_witness=CriticWitness(),
                db=db,
            )
            result = await loop.run(
                plan=plan,
                instance_id=PLAN_INSTANCE_ID,
                conversation_id=conversation_id,
                user_message=run.user_message,
                system_prompt=system_prompt,
                instance_config=instance_config,
                user_info=user_info,
                host_user_id=user_pk,
                resume_run_id=run.id,
            )

        # Re-read the durable row the loop finalized.
        await sync_to_async(run.refresh_from_db)()
        steps = await sync_to_async(
            lambda: list(
                RunStep.objects.filter(run_id=run.id).order_by("step_index")
            )
        )()
        paused_step = next(
            (s for s in steps if s.status == STEP_AWAITING_APPROVAL), None
        )

        for step in steps:
            if step.status in (STEP_SKIPPED,):
                continue
            yield {
                "type": "step_start",
                "plan_id": run.id,
                "step_id": step.step_index,
                "intent": step.intent,
            }
            if step.status == STEP_AWAITING_APPROVAL and paused_step is not None:
                yield {
                    "type": "step_confirm",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "intent": step.intent,
                    "message": (
                        "This step changes your data — review and confirm it "
                        "to continue, or decline to skip it."
                    ),
                }
            else:
                yield {
                    "type": "step_result",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "intent": step.intent,
                    "status": step.status,
                    "verdict": step.critic_verdict,
                    "draft_text": step.draft_text,
                    "tool_output": step.tool_output_json,
                    "error": step.error,
                }
                yield {
                    "type": "step_end",
                    "plan_id": run.id,
                    "step_id": step.step_index,
                    "status": step.status,
                }

        final_status = (
            STATUS_PAUSED if paused_step is not None else run.status
        )
        yield {
            "type": "done",
            "plan_id": run.id,
            "status": final_status,
            "final_response": run.final_response,
        }

    # ── Consent: step-level confirm / decline ─────────────────────────────

    def confirm_step(self, user, plan_id: str, step_id) -> dict:
        """Confirm a paused consent step — executes the staged mutation.

        Mirrors the workspace ``tool-executions/confirm`` seam: the staged
        host mutation runs in-process as the requesting user via
        ``CarbonHostExecutor.confirm_execution``; the step is then marked
        completed so the next ``run`` resumes past it.
        """
        from asgiref.sync import async_to_sync

        from ai.engine_runtime import _carbon_instance_config
        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PAUSED:
            raise PlanNotRunnableError(
                f"Plan is not paused (status: {run.status})."
            )
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_AWAITING_APPROVAL:
            raise PlanStepError(
                f"Step {step.step_index} is not awaiting approval "
                f"(status: {step.status})."
            )

        tool_output = step.tool_output_json or {}
        raw = tool_output.get("result", "")
        parsed = {}
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        execution_id = (
            (parsed or {}).get("execution_id")
            or tool_output.get("execution_id")
        )
        if not execution_id:
            raise PlanStepError(
                f"Step {step.step_index} has no staged execution to confirm."
            )

        user_pk = str(user.pk)
        instance_config = _carbon_instance_config(user_pk)
        factory = get_session_factory(PLAN_INSTANCE_ID)

        async def _confirm():
            async with factory() as db:
                executor = CarbonHostExecutor(
                    db=db,
                    instance_config=instance_config,
                    user_token=f"inproc:carbon:{user_pk}",
                    host_user_id=user_pk,
                )
                return await executor.confirm_execution(
                    execution_id, expected_host_user_id=user_pk
                )

        try:
            async_to_sync(_confirm)()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            logger.warning(
                "Plan step confirm failed plan=%s step=%s: %s",
                plan_id, step.step_index, exc, exc_info=True,
            )
            raise PlanStepError(f"Confirmation failed: {exc}")

        step.status = STEP_COMPLETED
        step.save(update_fields=["status", "updated_at"])
        logger.info(
            "Plan step confirmed plan=%s step=%s user=%s",
            plan_id, step.step_index, user_pk,
        )
        return {"status": "confirmed", "plan_id": plan_id, "step_id": step.step_index}

    def decline_step(self, user, plan_id: str, step_id) -> dict:
        """Decline a paused consent step — nothing is written.

        The staged mutation is discarded via
        ``CarbonHostExecutor.decline_execution``; the step is marked skipped
        so the next ``run`` resumes past it.
        """
        from asgiref.sync import async_to_sync

        from ai.engine_runtime import _carbon_instance_config
        from ai.engine.core.database import get_session_factory
        from ai.host_executor import CarbonHostExecutor

        run = self._get_owned_run(user, plan_id)
        if run.status != STATUS_PAUSED:
            raise PlanNotRunnableError(
                f"Plan is not paused (status: {run.status})."
            )
        step = self._get_owned_step(run, step_id)
        if step.status != STEP_AWAITING_APPROVAL:
            raise PlanStepError(
                f"Step {step.step_index} is not awaiting approval "
                f"(status: {step.status})."
            )

        tool_output = step.tool_output_json or {}
        raw = tool_output.get("result", "")
        parsed = {}
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        execution_id = (
            (parsed or {}).get("execution_id")
            or tool_output.get("execution_id")
        )
        if not execution_id:
            # Nothing staged — treat as a plain decline and skip the step.
            step.status = STEP_SKIPPED
            step.save(update_fields=["status", "updated_at"])
            return {
                "status": "declined",
                "plan_id": plan_id,
                "step_id": step.step_index,
            }

        user_pk = str(user.pk)
        instance_config = _carbon_instance_config(user_pk)
        factory = get_session_factory(PLAN_INSTANCE_ID)

        async def _decline():
            async with factory() as db:
                executor = CarbonHostExecutor(
                    db=db,
                    instance_config=instance_config,
                    user_token=f"inproc:carbon:{user_pk}",
                    host_user_id=user_pk,
                )
                await executor.decline_execution(
                    execution_id, expected_host_user_id=user_pk
                )

        try:
            async_to_sync(_decline)()
        except Exception as exc:  # noqa: BLE001 - fail-visible with detail
            logger.warning(
                "Plan step decline failed plan=%s step=%s: %s",
                plan_id, step.step_index, exc, exc_info=True,
            )
            raise PlanStepError(f"Decline failed: {exc}")

        step.status = STEP_SKIPPED
        step.save(update_fields=["status", "updated_at"])
        logger.info(
            "Plan step declined plan=%s step=%s user=%s",
            plan_id, step.step_index, user_pk,
        )
        return {"status": "declined", "plan_id": plan_id, "step_id": step.step_index}

    # ── Stop / audit ──────────────────────────────────────────────────────

    def stop_plan(self, user, plan_id: str) -> dict:
        """Request cancellation of a plan run (idempotent)."""
        run = self._get_owned_run(user, plan_id)
        if run.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
            return self.get_plan(user, plan_id)

        from ai.models.core import RunStep

        run.status = STATUS_CANCELLED
        run.completed_at = run.completed_at or timezone.now()
        run.save(update_fields=["status", "completed_at", "updated_at"])
        RunStep.objects.filter(run_id=run.id, status=STEP_PENDING).update(
            status=STEP_SKIPPED
        )
        logger.info("Plan stopped id=%s user=%s", plan_id, str(user.pk))
        return self.get_plan(user, plan_id)

    def get_ledger(self, user, plan_id: str) -> dict:
        """Audit ledger for a plan: steps, confirmations, replans, latency,
        tokens, provenance, actor."""
        from ai.models.core import RunStep

        run = self._get_owned_run(user, plan_id)
        steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
        plan_json = run.plan_json or {}

        actor_name = str(user)
        try:
            from django.contrib.auth import get_user_model

            owner = get_user_model().objects.get(pk=run.host_user_id)
            actor_name = getattr(owner, "display_name", "") or (
                owner.get_full_name() or owner.username
            )
        except Exception:  # noqa: BLE001 - best-effort actor resolution
            pass

        confirmations = [
            {
                "step_id": s.step_index,
                "intent": s.intent,
                "status": s.status,
            }
            for s in steps
            if s.status in (STEP_AWAITING_APPROVAL, STEP_COMPLETED)
            and s.confirmation_token is not None
        ]
        # Fallback: any step that ever reached the consent gate carries a
        # confirmation token after a pause.
        if not confirmations:
            confirmations = [
                {
                    "step_id": s.step_index,
                    "intent": s.intent,
                    "status": s.status,
                }
                for s in steps
                if s.confirmation_token
            ]

        return {
            "plan_id": run.id,
            "brief": run.user_message,
            "status": run.status,
            "actor": {
                "user_id": run.host_user_id,
                "display_name": actor_name,
            },
            "provenance": {
                "pattern": plan_json.get("pattern", "custom"),
                "source": plan_json.get("source", "single_step"),
                "skill_name": plan_json.get("skill_name"),
                "needs_confirmation": bool(
                    plan_json.get("needs_confirmation", False)
                ),
                "created_at": run.created_at.isoformat()
                if run.created_at
                else None,
                "completed_at": run.completed_at.isoformat()
                if run.completed_at
                else None,
            },
            "usage": {
                "total_latency_ms": run.total_latency_ms,
                "total_llm_calls": run.total_llm_calls,
                "total_tokens": run.total_tokens or 0,
            },
            "steps": [
                {
                    "step_id": s.step_index,
                    "intent": s.intent,
                    "tool_name": s.tool_name,
                    "status": s.status,
                    "critic_verdict": s.critic_verdict,
                    "latency_ms": s.latency_ms,
                    "error": s.error,
                    "confirmed": s.status == STEP_COMPLETED
                    and s.confirmation_token is not None,
                    "skipped": s.status == STEP_SKIPPED,
                }
                for s in steps
            ],
            "confirmations": confirmations,
            "replans": sum(
                1 for s in steps if (s.critic_verdict or "") == "veto"
            ),
            "final_response": run.final_response,
        }
