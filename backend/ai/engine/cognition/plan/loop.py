"""
ReActLoop — Iterates a Plan step-by-step with critic gating + re-plan on failure.

PR-20: Executes each PlanStep through draft → critic → execute → observe,
with mutation confirmation gates, dry-run previews, and up to 2 replans.
"""
import json
import logging
import time
from dataclasses import asdict, dataclass, field

from ai.engine.core.clock import utcnow
from ai.store import first

from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.turn.witnesses import CriticVerdict, DraftResult, RetrievalResult

logger = logging.getLogger("pulse.cognition.plan.loop")

# Lazy import — resolved at first emit
_broadcast_run = None


def _get_broadcast():
    global _broadcast_run
    if _broadcast_run is None:
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
    return _broadcast_run


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    """Outcome of executing one PlanStep."""
    step_id: int
    intent: str
    draft_text: str = ""
    critic_verdict: str = ""         # "pass" | "pass_with_flag" | "rewrite" | "veto"
    critic_flags: list[str] = field(default_factory=list)
    executed: bool = False
    tool_output: dict | None = None
    error: str | None = None
    dry_run_preview: dict | None = None
    # P1.3: consent pause
    paused: bool = False
    confirmation_token: str | None = None


@dataclass
class ReActResult:
    """Aggregate result of a full ReAct loop execution."""
    plan: Plan
    step_results: list[StepResult]
    final_response: str
    succeeded: bool
    replans_used: int = 0
    confirmations_required: int = 0


# ── ReAct Loop ─────────────────────────────────────────────────────────────────

class ReActLoop:
    """Execute a Plan step-by-step with draft→critic→execute→observe."""

    MAX_REPLANS = 2

    def __init__(
        self,
        draft_witness=None,       # DraftWitness
        critic_witness=None,      # CriticWitness
        executor=None,            # ExecuteWitness
        llm_client=None,
        knowledge_store=None,
        memory_manager=None,
        db=None,                  # Store session for durable run persistence
    ):
        self.draft_witness = draft_witness
        self.critic_witness = critic_witness
        self.executor = executor
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.db = db

    async def run(
        self,
        plan: Plan,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        instance_config: dict | None = None,
        user_info: dict | None = None,
        retrieval: RetrievalResult | None = None,
        progress_callback=None,
        stream_callback=None,
        dry_run: bool = False,
        confirmation_token: str | None = None,
        db=None,                  # Store session for durable run persistence (P1.1)
        host_user_id: str | None = None,
        resume_run_id: str | None = None,  # P1.3: resume from a paused run
    ) -> ReActResult:
        """Execute the plan through the ReAct loop.

        Args:
            plan: The decomposed plan to execute
            instance_id: pulse instance
            conversation_id: current conversation
            user_message: original user message
            system_prompt: built system prompt
            conversation_history: prior turns
            instance_config: instance-level config
            user_info: host user metadata
            retrieval: S2 retrieval result for context
            progress_callback: optional progress reporter
            stream_callback: optional streaming output
            dry_run: if True, skip real mutations — preview only
            confirmation_token: user-confirmed token for mutation steps
            db: optional Store session for durable Run/RunStep persistence
            host_user_id: optional host user for tenancy
            resume_run_id: P1.3 — if set, resume an existing paused run
                from the first pending step

        Returns:
            ReActResult with step results and final synthesis
        """
        from ai.engine.cognition.turn.draft import DraftWitness
        from ai.engine.cognition.turn.critic import CriticWitness
        from ai.engine.cognition.turn.execute import ExecuteWitness

        dw = self.draft_witness or DraftWitness(
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
        )
        cw = self.critic_witness or CriticWitness()
        ex = self.executor or ExecuteWitness()

        # Use self.db or passed db
        _db = db or self.db

        step_results: list[StepResult] = []
        replans_used = 0
        confirmations_required = 0
        step_contexts: dict[int, str] = {}  # step_id → output text for dependents
        total_llm_calls = 0
        t0 = time.monotonic()

        # ── P1.1 / P1.3: Persist or resume Run row ────────────────────────
        from ai.engine.core.models import Run, RunStep, generate_uuid

        completed_ids: set[int] = set()

        if resume_run_id:
            run_id = resume_run_id
        else:
            run_id = generate_uuid()

        if _db is not None:
            if resume_run_id:
                # ── P1.3: Resume existing paused run ──────────────────
                run_row = first(await _db.select(Run, ("id", run_id)))
                if run_row is None:
                    raise ValueError(f"Run {run_id} not found for resume")
                if run_row.status != "paused":
                    raise ValueError(
                        f"Cannot resume run {run_id} with status '{run_row.status}'"
                    )
                run_row.status = "running"
                run_row.updated_at = utcnow()
                await _db.commit()

                # Build completed_ids from existing completed/skipped steps
                existing_steps = await _db.select(RunStep, ("run_id", run_id))
                existing_steps.sort(key=lambda s: s.step_index)
                for s in existing_steps:
                    if s.status in ("completed", "skipped"):
                        completed_ids.add(s.step_index)
                        if s.draft_text:
                            step_contexts[s.step_index] = s.draft_text
                    # Also add prior step_results for synthesis
                    if s.status in ("completed", "skipped", "awaiting_approval"):
                        step_results.append(StepResult(
                            step_id=s.step_index,
                            intent=s.intent,
                            draft_text=s.draft_text or "",
                            critic_verdict=s.critic_verdict or "pass",
                            critic_flags=json.loads(s.critic_flags_json) if s.critic_flags_json else [],
                            executed=s.status == "completed",
                            tool_output=json.loads(s.tool_output_json) if s.tool_output_json else None,
                            error=s.error,
                        ))
                logger.debug(
                    "ReActLoop: resumed run id=%s, completed_ids=%s",
                    run_id, completed_ids,
                )
            else:
                # ── New run ───────────────────────────────────────────
                run_row = Run(
                    id=run_id,
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    host_user_id=host_user_id,
                    user_message=user_message,
                    status="running",
                    plan_json=json.dumps(asdict(plan)),
                )
                _db.add(run_row)
                await _db.commit()
                logger.debug("ReActLoop: persisted Run row id=%s", run_id)

        # ── Emit run-level events (always, regardless of DB) ──────────
        if resume_run_id:
            await _get_broadcast()(instance_id, "run.resumed", {
                "run_id": run_id,
                "completed_step_ids": sorted(completed_ids),
            })
        else:
            await _get_broadcast()(instance_id, "run.started", {
                "run_id": run_id,
                "conversation_id": conversation_id,
                "host_user_id": host_user_id,
                "user_message": user_message,
                "plan_steps": len(plan.steps),
            })

        # ── Topological sort: respect depends_on ──────────────────────────
        remaining = list(plan.steps)
        # Filter out already-completed steps for resumed runs

        while remaining:
            ready, remaining = self._partition_ready(remaining, completed_ids)
            if not ready:
                # Circular dependency — execute remaining sequentially
                logger.warning("ReActLoop: possible circular dependency; executing remaining sequentially")
                ready = remaining
                remaining = []

            for step in ready:
                step_t0 = time.monotonic()
                await _get_broadcast()(instance_id, "run.step.started", {
                    "run_id": run_id,
                    "step_index": step.step_id,
                    "intent": step.intent,
                })
                result = await self._execute_step(
                    step=step,
                    dw=dw,
                    cw=cw,
                    ex=ex,
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    instance_config=instance_config,
                    user_info=user_info,
                    retrieval=retrieval,
                    progress_callback=progress_callback,
                    stream_callback=stream_callback,
                    dry_run=dry_run,
                    confirmation_token=confirmation_token,
                    step_contexts=step_contexts,
                )
                step_latency = (time.monotonic() - step_t0) * 1000
                step_results.append(result)
                total_llm_calls += 1  # each step involves at least one LLM call

                # ── Step event based on result ────────────────────────
                if result.error and result.critic_verdict == "veto":
                    await _get_broadcast()(instance_id, "run.step.failed", {
                        "run_id": run_id,
                        "step_index": step.step_id,
                        "intent": step.intent,
                        "error": result.error,
                        "latency_ms": step_latency,
                    })
                else:
                    await _get_broadcast()(instance_id, "run.step.completed", {
                        "run_id": run_id,
                        "step_index": step.step_id,
                        "intent": step.intent,
                        "verdict": result.critic_verdict,
                        "latency_ms": step_latency,
                    })

                # ── P1.3: Pause on consent gate ───────────────────────
                if result.paused:
                    confirmations_required += 1
                    await _get_broadcast()(instance_id, "run.paused", {
                        "run_id": run_id,
                        "step_index": step.step_id,
                        "intent": step.intent,
                        "confirmation_token": result.confirmation_token,
                    })
                    if _db is not None and run_id is not None:
                        # Persist the paused step
                        await self._persist_run_step(
                            _db=_db,
                            run_id=run_id,
                            step=step,
                            result=result,
                            step_latency_ms=step_latency,
                        )
                        # Update Run status to paused
                        await self._pause_run(_db, run_id)
                    break  # stop the entire loop

                # ── P1.1: Persist RunStep row ──────────────────────────
                if _db is not None and run_id is not None:
                    await self._persist_run_step(
                        _db=_db,
                        run_id=run_id,
                        step=step,
                        result=result,
                        step_latency_ms=step_latency,
                    )

                if result.critic_verdict == "veto":
                    if replans_used < self.MAX_REPLANS:
                        logger.info(
                            "ReActLoop: step %d vetoed, replanning (%d/%d)",
                            step.step_id, replans_used + 1, self.MAX_REPLANS,
                        )
                        replans_used += 1
                        # Replan: rebuild remaining steps via single-step fallback
                        replan_steps = self._replan_step(step, result)
                        remaining = replan_steps + remaining
                        break  # restart from replanned steps
                    else:
                        logger.warning(
                            "ReActLoop: max replans (%d) reached for step %d; surface failure",
                            self.MAX_REPLANS, step.step_id,
                        )
                        # Continue to final synthesis — failure surfaced honestly

                if step.is_mutation and not dry_run and not confirmation_token:
                    confirmations_required += 1

                completed_ids.add(step.step_id)
                if result.draft_text:
                    step_contexts[step.step_id] = result.draft_text

        # ── Check for pause (consent gate hit) ────────────────────────────
        is_paused = bool(step_results and step_results[-1].paused)

        if is_paused:
            # Don't synthesize — return the confirmation prompt
            last = step_results[-1]
            final_response = _extract_confirmation_message(last.tool_output)
            succeeded = False
        else:
            # ── Synthesise final response ─────────────────────────────────
            final_response = await self._synthesise(
                plan, step_results, user_message, system_prompt, step_contexts,
                instance_id=instance_id,
            )
            succeeded = all(
                r.critic_verdict in ("pass", "pass_with_flag") and not r.error
                for r in step_results
            )

        # ── P1.1: Update Run row with final status ────────────────────────
        if _db is not None and run_id is not None:
            total_latency = (time.monotonic() - t0) * 1000
            if is_paused:
                # Run already set to paused in the loop — just update latency
                from ai.engine.core.models import Run
                row = first(await _db.select(Run, ("id", run_id)))
                if row:
                    row.total_llm_calls = total_llm_calls
                    row.total_latency_ms = total_latency
                    row.updated_at = utcnow()
                    await _db.commit()
            else:
                await self._finalize_run(
                    _db=_db,
                    run_id=run_id,
                    succeeded=succeeded,
                    final_response=final_response,
                    total_latency_ms=total_latency,
                    total_llm_calls=total_llm_calls,
                    step_results=step_results,
                )

        if not is_paused:
            _total_latency = (time.monotonic() - t0) * 1000
            await _get_broadcast()(instance_id, "run.completed" if succeeded else "run.failed", {
                "run_id": run_id,
                "total_latency_ms": _total_latency,
                "total_llm_calls": total_llm_calls,
                "steps_completed": len([r for r in step_results if r.critic_verdict in ("pass", "pass_with_flag")]),
                "steps_failed": len([r for r in step_results if r.error or r.critic_verdict == "veto"]),
            })

        return ReActResult(
            plan=plan,
            step_results=step_results,
            final_response=final_response,
            succeeded=succeeded,
            replans_used=replans_used,
            confirmations_required=confirmations_required,
        )

    # ── Step execution ─────────────────────────────────────────────────────

    async def _execute_step(
        self,
        step: PlanStep,
        dw,         # DraftWitness
        cw,         # CriticWitness
        ex,         # ExecuteWitness
        instance_id: str,
        conversation_id: str,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        retrieval: RetrievalResult | None,
        progress_callback,
        stream_callback,
        dry_run: bool,
        confirmation_token: str | None,
        step_contexts: dict[int, str],
    ) -> StepResult:
        """Execute one plan step: draft → critic → execute → observe."""

        # Build step-prompt with dependents' context
        enriched_prompt = self._build_step_prompt(
            step, user_message, system_prompt, step_contexts,
        )

        # Draft
        draft = await dw.draft(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=enriched_prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
        )

        # Critic
        retrieval_stub = retrieval or RetrievalResult()
        critic = await cw.review(
            draft=draft,
            retrieval=retrieval_stub,
            is_mutation=step.is_mutation,
            dry_run=dry_run,
            confirmation_token=confirmation_token,
        )

        result = StepResult(
            step_id=step.step_id,
            intent=step.intent,
            draft_text=draft.text,
            critic_verdict=critic.verdict,
            critic_flags=critic.flags.copy(),
        )

        if critic.verdict == "veto":
            result.error = critic.veto_reason or "Step vetoed by critic"
            return result

        # Execute (only if not vetoed)
        if not dry_run:
            execution = await ex.execute(
                draft.text, stream_callback, progress_callback,
            )
            result.executed = True
            result.tool_output = execution.completed_tools[0] if execution.completed_tools else None

            # ── P1.3: Consent gate — pause if tool requires confirmation ──
            if result.tool_output:
                _to = result.tool_output
                _raw = _to.get("result", "")
                try:
                    _parsed = json.loads(_raw) if isinstance(_raw, str) else _raw
                except (json.JSONDecodeError, TypeError):
                    _parsed = {}
                if isinstance(_parsed, dict) and _parsed.get("requires_confirmation"):
                    from uuid import uuid4
                    result.paused = True
                    result.confirmation_token = str(uuid4())
                    result.executed = False
                    result.error = None
                    logger.info(
                        "ReActLoop: consent gate hit step=%d tool=%s token=%s",
                        step.step_id, _to.get("tool_name", "?"), result.confirmation_token[:8],
                    )
                    return result
        elif step.dry_run_supported or step.is_mutation:
            # Dry-run preview: no actual execution
            result.executed = False
            result.dry_run_preview = {
                "step_id": step.step_id,
                "intent": step.intent,
                "tool_name": step.tool_name,
                "tool_args": step.tool_args,
                "preview": f"[DRY RUN] Would execute: {step.intent}",
            }

        return result

    def _build_step_prompt(
        self, step: PlanStep, user_message: str, system_prompt: str,
        step_contexts: dict[int, str],
    ) -> str:
        """Construct the prompt for this specific step, including prior results."""
        parts = [f"Original user request: {user_message}"]
        parts.append(f"Current step: {step.intent}")
        if step.tool_name:
            parts.append(f"Use tool: {step.tool_name} with args: {step.tool_args}")

        if step.depends_on:
            deps_text = []
            for dep_id in step.depends_on:
                if dep_id in step_contexts:
                    deps_text.append(f"Result from step {dep_id}: {step_contexts[dep_id]}")
            if deps_text:
                parts.append("Prior step results:\n" + "\n".join(deps_text))

        return "\n\n".join(parts)

    # ── Topological helpers ────────────────────────────────────────────────

    @staticmethod
    def _partition_ready(
        steps: list[PlanStep], completed_ids: set[int],
    ) -> tuple[list[PlanStep], list[PlanStep]]:
        """Split steps into ready (all deps met) and remaining."""
        ready = []
        remaining = []
        for s in steps:
            if set(s.depends_on).issubset(completed_ids):
                ready.append(s)
            else:
                remaining.append(s)
        return ready, remaining

    def _replan_step(self, failed_step: PlanStep, failed_result: StepResult) -> list[PlanStep]:
        """Create replacement steps after a veto — simple: retry as single step."""
        logger.info(
            "ReActLoop: replanning step %d after veto: %s",
            failed_step.step_id, failed_result.error,
        )
        return [PlanStep(
            step_id=failed_step.step_id,
            intent=f"Retry: {failed_step.intent} (previous attempt failed: {failed_result.error})",
            tool_name=failed_step.tool_name,
            tool_args=failed_step.tool_args,
            depends_on=failed_step.depends_on,
            is_mutation=False,  # strip mutation on retry — safer
        )]

    # ── P1.1: Durable run persistence helpers ─────────────────────────────

    async def _persist_run_step(
        self,
        _db,
        run_id: str,
        step: PlanStep,
        result: StepResult,
        step_latency_ms: float,
    ) -> None:
        """Insert or update a RunStep row for the given step result."""
        from ai.engine.core.models import RunStep, generate_uuid

        # Determine step status from critic verdict or pause
        if result.paused:
            step_status = "awaiting_approval"
        elif result.critic_verdict == "veto":
            step_status = "failed"
        elif result.error:
            step_status = "failed"
        else:
            step_status = "completed" if result.executed else "completed"

        # Check if a row already exists for this run+step (resume path)
        existing = first(await _db.select(
            RunStep,
            ("run_id", run_id),
            ("step_index", step.step_id),
        ))

        if existing:
            # Update existing row (resume path)
            existing.status = step_status
            existing.draft_text = result.draft_text or existing.draft_text
            existing.critic_verdict = result.critic_verdict or existing.critic_verdict
            existing.critic_flags_json = (
                json.dumps(result.critic_flags) if result.critic_flags
                else existing.critic_flags_json
            )
            existing.tool_output_json = (
                json.dumps(result.tool_output) if result.tool_output
                else existing.tool_output_json
            )
            existing.error = result.error
            existing.latency_ms = step_latency_ms
            if result.confirmation_token:
                existing.confirmation_token = result.confirmation_token
            existing.updated_at = utcnow()
            await _db.commit()
            logger.debug(
                "ReActLoop: updated RunStep row run_id=%s step=%d status=%s",
                run_id, step.step_id, step_status,
            )
        else:
            # Insert new row
            run_step = RunStep(
                id=generate_uuid(),
                run_id=run_id,
                step_index=step.step_id,
                intent=step.intent,
                tool_name=step.tool_name,
                tool_args_json=json.dumps(step.tool_args) if step.tool_args else None,
                depends_on_json=json.dumps(step.depends_on) if step.depends_on else None,
                status=step_status,
                draft_text=result.draft_text or None,
                critic_verdict=result.critic_verdict or None,
                critic_flags_json=json.dumps(result.critic_flags) if result.critic_flags else None,
                tool_output_json=json.dumps(result.tool_output) if result.tool_output else None,
                error=result.error,
                latency_ms=step_latency_ms,
                confirmation_token=result.confirmation_token,
            )
            _db.add(run_step)
            await _db.commit()
            logger.debug(
                "ReActLoop: persisted RunStep row run_id=%s step=%d status=%s",
                run_id, step.step_id, step_status,
            )

    async def _pause_run(self, _db, run_id: str) -> None:
        """Set Run status to 'paused'."""
        from ai.engine.core.models import Run
        row = first(await _db.select(Run, ("id", run_id)))
        if row:
            row.status = "paused"
            row.updated_at = utcnow()
            await _db.commit()
            logger.info("ReActLoop: paused Run id=%s", run_id)

    async def _finalize_run(
        self,
        _db,
        run_id: str,
        succeeded: bool,
        final_response: str,
        total_latency_ms: float,
        total_llm_calls: int,
        step_results: list[StepResult],
    ) -> None:
        """Update the Run row with final status and summary."""
        from ai.engine.core.models import Run

        run_row = first(await _db.select(Run, ("id", run_id)))
        if run_row is None:
            logger.warning("ReActLoop: Run row id=%s not found for finalization", run_id)
            return

        run_row.status = "completed" if succeeded else "failed"
        run_row.final_response = final_response[:2000] if final_response else None
        run_row.total_llm_calls = total_llm_calls
        run_row.total_latency_ms = total_latency_ms
        run_row.completed_at = utcnow()
        await _db.commit()
        logger.debug("ReActLoop: finalized Run row id=%s status=%s", run_id, run_row.status)

    # ── Synthesis ──────────────────────────────────────────────────────────

    async def _synthesise(
        self,
        plan: Plan,
        step_results: list[StepResult],
        user_message: str,
        system_prompt: str,
        step_contexts: dict[int, str],
        instance_id: str = "",
    ) -> str:
        """Combine step results into a final response using the plan's synthesis_instruction."""
        if len(step_results) == 1 and plan.source == "single_step":
            return step_results[0].draft_text or ""

        # Build a synthesis prompt
        parts = [f"User asked: {user_message}"]
        parts.append(f"Plan: {plan.pattern} — {plan.synthesis_instruction}")
        parts.append("Step results:")
        for r in step_results:
            status = "✓" if r.critic_verdict in ("pass", "pass_with_flag") else "✗"
            parts.append(f"  [{status}] Step {r.step_id}: {r.intent}")
            if r.draft_text:
                parts.append(f"    Output: {r.draft_text[:500]}")
            if r.error:
                parts.append(f"    Error: {r.error}")

        # If we have an LLM, use it for synthesis; otherwise concatenate
        if self.llm_client is not None and self.model:
            return await self._llm_synthesise("\n".join(parts), system_prompt, instance_id=instance_id)
        else:
            # Simple concatenation fallback
            texts = [r.draft_text for r in step_results if r.draft_text]
            if not texts:
                return "I wasn't able to complete the requested plan. Some steps encountered errors."
            return "\n\n".join(texts)

    @property
    def model(self) -> str:
        """Get the model name from config — used by _llm_synthesise."""
        from ai.engine.core.config import get_settings
        return get_settings().LLM_MODEL

    async def _llm_synthesise(self, synthesis_prompt: str, system_prompt: str, instance_id: str = "") -> str:
        """Use LLM to synthesise step results."""
        try:
            from ai.engine.llm.router import route_chat
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"plan-synthesise-{instance_id or 'unknown'}",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": synthesis_prompt},
                ],
                temperature=0.3,
            )
            return router_result["content"] or ""
        except Exception as e:
            logger.warning("LLM synthesis failed: %s", e)
            return synthesis_prompt


# ── P1.3: Helpers ────────────────────────────────────────────────────────────

def _extract_confirmation_message(tool_output: dict | None) -> str:
    """Extract the confirmation prompt from a tool result that requires approval."""
    if not tool_output:
        return "I need your approval before I can proceed."
    raw = tool_output.get("result", "")
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return "I need your approval before I can proceed."
    if isinstance(parsed, dict):
        return parsed.get("confirmation_message") or parsed.get("message") or "I need your approval before I can proceed."
    return "I need your approval before I can proceed."
