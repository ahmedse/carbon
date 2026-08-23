"""
ReActLoop — Iterates a Plan step-by-step with critic gating + re-plan on failure.

PR-20: Executes each PlanStep through draft → critic → execute → observe,
with mutation confirmation gates, dry-run previews, and up to 2 replans.
"""
import asyncio
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

def _phase_name(plan, phase_id: int) -> str:
    """Human label for a phase id — falls back to a neutral name."""
    for p in getattr(plan, "phases", []) or []:
        if p.phase_id == phase_id and p.name:
            return p.name
    return f"Phase {phase_id + 1}"


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
            confirmation_token: legacy single token (deprecated). On resume the
                token is resolved PER STEP from each ``awaiting_approval``
                RunStep's own ``confirmation_token`` (see ``resume_tokens``) —
                a single shared token must never flow into every mutation step.
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
        # Per-step confirmation tokens (P1.3): each ``awaiting_approval`` step
        # carries its OWN token; on resume that token is handed to THAT step
        # only. A single shared token must never flow into every mutation step
        # (RULE_21 — a confirmed step's token would otherwise let later
        # mutation steps skip their own consent gate).
        resume_tokens: dict[int, str] = {}

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
                    if s.status == "awaiting_approval" and s.confirmation_token:
                        resume_tokens[s.step_index] = s.confirmation_token
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
        # Filter out already-completed/skipped steps for resumed runs — the
        # consent confirm/decline path marks a step ``completed``/``skipped``
        # in Django before the run resumes, and the loop must not re-execute
        # it (which would otherwise re-trigger the consent gate).
        remaining = [
            s for s in plan.steps if s.step_id not in completed_ids
        ]

        # ── Phase bookkeeping (workflow stages) ───────────────────────────
        # plan.phases gives each step a stage. Phases run in order (phase i
        # steps wait for all earlier phases); within a "sequential" phase the
        # steps run in listed order, within a "parallel" phase they run
        # concurrently (still subject to depends_on). Steps not listed in any
        # phase are treated as an implicit trailing phase so nothing stalls.
        _step_phase: dict[int, int] = {}
        _phase_steps: dict[int, list[int]] = {}
        for _p in getattr(plan, "phases", []) or []:
            _phase_steps.setdefault(_p.phase_id, [])
            for _sid in _p.step_ids or []:
                _step_phase[_sid] = _p.phase_id
                _phase_steps[_p.phase_id].append(_sid)
        _phase_strategy: dict[int, str] = {
            _p.phase_id: (_p.strategy if _p.strategy in ("sequential", "parallel") else "sequential")
            for _p in (getattr(plan, "phases", []) or [])
        }
        # Unlisted steps → implicit trailing phase (id = max+1)
        _unlisted = [s.step_id for s in plan.steps if s.step_id not in _step_phase]
        if _unlisted:
            _implicit_phase = (max(_phase_steps) + 1) if _phase_steps else 0
            _phase_steps[_implicit_phase] = _unlisted
            _phase_strategy[_implicit_phase] = "sequential"
            for _sid in _unlisted:
                _step_phase[_sid] = _implicit_phase
        _phase_ids_ordered = sorted(_phase_steps.keys())
        # step_id → index within its phase (for sequential ordering)
        _step_seq_index: dict[int, int] = {}
        for _pid, _sids in _phase_steps.items():
            for _idx, _sid in enumerate(_sids):
                _step_seq_index[_sid] = _idx

        _started_phases: set[int] = set()

        def _step_is_phase_ready(step_id: int, done: set[int]) -> bool:
            """Phase barrier: earlier phases complete first; sequential
            phases run their steps in listed order; parallel phases only
            require depends_on (checked by the caller's topo pass)."""
            pid = _step_phase.get(step_id)
            if pid is None:
                return True
            pid_idx = _phase_ids_ordered.index(pid)
            for _earlier_pid in _phase_ids_ordered[:pid_idx]:
                if not all(s in done for s in _phase_steps[_earlier_pid]):
                    return False
            if _phase_strategy.get(pid) == "sequential":
                _idx = _step_seq_index.get(step_id, 0)
                _phase_ids = _phase_steps[pid]
                for _prior in _phase_ids[:_idx]:
                    if _prior not in done:
                        return False
            return True

        while remaining:
            ready, remaining = self._partition_ready(remaining, completed_ids)
            # Phase barrier filter — sequential phases must not jump ahead.
            # Steps blocked by an earlier phase stay in the pool (they are
            # pushed back into ``remaining``) so they run once their phase is
            # unblocked — never silently dropped.
            _blocked: list[PlanStep] = []
            _filtered: list[PlanStep] = []
            for _s in ready:
                if _step_is_phase_ready(_s.step_id, completed_ids):
                    _filtered.append(_s)
                else:
                    _blocked.append(_s)
            ready = _filtered
            remaining = _blocked + remaining
            if not ready:
                # Circular dependency or phase barrier blocking — surface as
                # sequentially-run remaining so execution never stalls.
                if remaining:
                    logger.warning(
                        "ReActLoop: phase barrier/circular deps block ready set; "
                        "running remaining sequentially"
                    )
                    ready, remaining = remaining[:1], remaining[1:]
                else:
                    break

            # Phase 1 — broadcast started for every ready step (preserves event order)
            for step in ready:
                _pid = _step_phase.get(step.step_id)
                if _pid is not None and _pid not in _started_phases:
                    _started_phases.add(_pid)
                    await _get_broadcast()(instance_id, "run.phase.started", {
                        "run_id": run_id,
                        "phase_id": _pid,
                        "name": _phase_name(plan, _pid),
                        "strategy": _phase_strategy.get(_pid, "sequential"),
                        "step_ids": _phase_steps.get(_pid, []),
                    })
                await _get_broadcast()(instance_id, "run.step.started", {
                    "run_id": run_id,
                    "step_index": step.step_id,
                    "intent": step.intent,
                })

            # Phase 2 — execute in parallel (sequential fast-path when len==1)
            async def _run_one(step):
                _t0 = time.monotonic()
                _res = await self._execute_step(
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
                    confirmation_token=resume_tokens.get(step.step_id),
                    step_contexts=step_contexts,
                    agent_role=step.agent_role,
                    plan_source=plan.source,
                )
                return step, _res, (time.monotonic() - _t0) * 1000

            if len(ready) == 1:
                executed = [await _run_one(ready[0])]
            else:
                executed = await asyncio.gather(*[_run_one(s) for s in ready])

            # Phase 3 — fold back IN ORDER (same post-step logic as today)
            stopped_for_pause = False
            for step, result, step_latency in executed:
                step_results.append(result)
                total_llm_calls += 1  # each step involves at least one LLM call

                # ── Step event based on result ────────────────────────
                # Any error (critic veto OR lifted tool error) fails the step;
                # only genuinely successful steps broadcast completed.
                if result.error:
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
                    # W6-F: halt the ENTIRE run at the consent gate — no
                    # later step may execute (the earlier `break` only exited
                    # the fold-back `for`, letting the outer `while remaining:`
                    # fallback run later steps and `_finalize_run` clobber the
                    # paused status to failed/completed, which blocked
                    # confirm_step's `status == paused` guard).
                    stopped_for_pause = True
                    break

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

                if step.is_mutation and not dry_run and not resume_tokens.get(step.step_id):
                    confirmations_required += 1

                completed_ids.add(step.step_id)
                if result.draft_text:
                    step_contexts[step.step_id] = result.draft_text

                # ── Phase completed? (all steps in the phase are done) ──
                # Runs AFTER completed_ids.update so single-step phases fire.
                _pid = _step_phase.get(step.step_id)
                if _pid is not None and _pid in _started_phases:
                    _phase_done = all(
                        s in completed_ids for s in _phase_steps[_pid]
                    )
                    if _phase_done:
                        await _get_broadcast()(instance_id, "run.phase.completed", {
                            "run_id": run_id,
                            "phase_id": _pid,
                            "name": _phase_name(plan, _pid),
                            "strategy": _phase_strategy.get(_pid, "sequential"),
                            "step_ids": _phase_steps.get(_pid, []),
                        })

            if stopped_for_pause:
                break  # stop the entire loop (outer while)

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
        agent_role: str | None = None,
        plan_source: str = "",
    ) -> StepResult:
        """Execute one plan step: draft → critic → execute → observe."""

        # Build step-prompt with dependents' context
        enriched_prompt = self._build_step_prompt(
            step, user_message, system_prompt, step_contexts,
        )

        # Tool-aware drafting: expose the step's tool set (or the curated
        # single-step allow-set) so the LLM can emit real tool_calls, and
        # append the anti-fabrication grounding rules (mirrors runner.py:run).
        from ai.engine.agent.tools import get_tool_definitions

        step_tools: list[dict] | None = None
        if step.tool_name:
            step_tools = [
                d for d in get_tool_definitions()
                if d.get("function", {}).get("name") == step.tool_name
            ] or None
        elif plan_source == "single_step":
            # Single-step passthrough: mirror runner.py's curated allow-set so
            # a plain imperative request still dispatches a tool.
            _allow = {"create_dq_rule", "search_knowledge", "get_entity_details",
                      "list_my_capabilities", "plan_task"}
            step_tools = [
                d for d in get_tool_definitions()
                if d.get("function", {}).get("name") in _allow
            ] or None
        else:
            # Multi-step REASONING step (no tool): pure LLM reasoning from the
            # prior step results (depends_on) — comparison, synthesis,
            # analysis are the model's job, NOT a skill or a tool call.
            step_tools = None

        if step_tools:
            system_prompt = (
                f"{system_prompt}\n\n"
                "GROUNDING RULES — follow them exactly:\n"
                "- You have tools available. Use them to do real work instead "
                "of guessing. When a tool matches the user's request, call it "
                "right away — do not answer in prose instead of using it, and "
                "do not say you cannot run/execute tasks.\n"
                "- When the user asks you to plan, orchestrate, or run a task "
                "(e.g. 'run agent planner', 'plan a data quality audit'), call "
                "plan_task IMMEDIATELY with their request as the brief — do "
                "not ask for more details first.\n"
                "- NEVER claim an action succeeded (e.g. 'rule created') unless "
                "a tool result confirms it.\n"
                "- The create_dq_rule tool only STAGES a proposal — it returns "
                "a confirmation execution. Nothing is written until the user "
                "confirms. Tell the user a confirmation button appeared; do "
                "NOT say the rule was created.\n"
                "- The plan_task tool DRAFTS a plan and returns a plan id in "
                "pending_approval; it does not execute anything. After calling "
                "it, tell the user the plan id and that it awaits approval in "
                "the Tasks panel. Never claim a task ran or completed.\n"
                "- If a tool errors, report the error plainly.\n"
                "- When the user asks what you can do, use the capability-list "
                "tool so the app can attach the matching page links as small "
                "buttons under your reply."
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
            tools=step_tools,
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
            # ── Consent gate (RULE_21) ─────────────────────────────────────
            # A mutation step vetoed for lack of a confirmation token must
            # PAUSE for user consent — never veto→replan: _replan_step
            # rebuilds the step and re-executes it, and without this gate the
            # replanned mutation ran WITHOUT consent (sprint-18 bypass: the
            # critic vetoed, the replan stripped is_mutation, and the export
            # files were written). Convert the veto into a consent pause —
            # run()'s existing ``if result.paused:`` branch persists the step
            # as awaiting_approval, pauses the Run, broadcasts run.paused and
            # stops. On resume the step re-executes WITH the token and the
            # critic passes.
            if (
                step.is_mutation
                and "mutation_not_confirmed" in critic.flags
                and not confirmation_token
                and not dry_run
            ):
                from uuid import uuid4
                result.paused = True
                result.confirmation_token = str(uuid4())
                result.executed = False
                result.error = None
                result.critic_verdict = "pass"
                logger.info(
                    "ReActLoop: consent gate hit step=%d tool=%s token=%s "
                    "(mutation requires confirmation)",
                    step.step_id, step.tool_name or "?",
                    result.confirmation_token[:8],
                )
                return result

            result.error = critic.veto_reason or "Step vetoed by critic"
            return result

        # Execute (only if not vetoed)
        if not dry_run:
            # W6-D: record the dispatching step so export-style plugins can
            # attribute artifacts to THIS step (multi-step / parallel runs).
            # Contextvars flow onto the sync_to_async worker thread via
            # asgiref, and are cleared so sibling steps never bleed.
            from ai.plans_service import set_current_step_index
            set_current_step_index(step.step_id)
            try:
                execution = await ex.execute(
                    text=draft.text,
                    tool_calls=draft.tool_calls,
                    stream_callback=stream_callback,
                    progress_callback=progress_callback,
                    agent_role=agent_role or step.agent_role,
                    is_worker=(step.agent_role not in ("orchestrator", "", None)),
                )
            finally:
                set_current_step_index(None)
            result.executed = True
            result.tool_output = execution.completed_tools[0] if execution.completed_tools else None

            # ── Tool-error propagation ────────────────────────────────────
            # Tool-level failures ride inside result.tool_output (dict with an
            # "error" key); without this lift, failed steps were persisted as
            # "completed" and the run could finish "completed" with silent
            # failures. Promote tool errors to step errors so _persist_run_step
            # marks the step failed and _finalize_run fails the run honestly.
            if result.tool_output and isinstance(result.tool_output, dict):
                _tool_err = result.tool_output.get("error")
                if _tool_err:
                    result.error = str(_tool_err)

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
        if step.instructions:
            # W6-E F-28: service-owned steering metadata (edited while the
            # plan is paused) — the resume honors the edit by feeding it into
            # the step prompt.
            parts.append(f"Step instructions: {step.instructions}")
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
            # Keep is_mutation on retry — stripping it let replanned mutation
            # steps re-execute WITHOUT user consent (sprint-18 bypass, RULE_21
            # violation). With the consent gate in _execute_step, a mutation
            # without a token pauses for confirmation instead of executing;
            # preserving the flag guarantees a mutation can never run
            # unconfirmed, no matter how many times it is replanned.
            is_mutation=failed_step.is_mutation,
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
