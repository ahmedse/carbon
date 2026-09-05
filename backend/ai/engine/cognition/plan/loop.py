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
from ai.engine.core.resolution import payload_status
from ai.store import first

from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.turn.witnesses import CriticVerdict, DraftResult, RetrievalResult
from ai.engine.llm.router import model_for_profile

logger = logging.getLogger("pulse.cognition.plan.loop")

# Lazy import — resolved at first emit
_broadcast_run = None


def _get_broadcast():
    global _broadcast_run
    if _broadcast_run is None:
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
    return _broadcast_run


def _tool_requires_confirmation(tool_name: str) -> bool:
    """True when a registered plugin gates its write behind confirmation.

    Lazy import avoids a circular dependency; a lookup failure is treated as
    read-only (fail-open for the guard).
    """
    try:
        from ai.engine.agent.plugins import is_confirmation_tool
        return is_confirmation_tool(tool_name)
    except Exception:  # noqa: BLE001 - guard must never raise into the run
        return False


# Pulse v2 Phase 5: read-only tools the loop may auto-chain for multi-hop
# reasoning. Mutation/planning tools are deliberately excluded — an automatic
# follow-up must never write state or trigger a consent gate without the user.
_ALLOWED_FOLLOWUP_TOOLS = frozenset({
    "web_research",
    "get_entity_details",
    "search_knowledge",
    "call_host_api",
})


# ── Dataclasses ────────────────────────────────────────────────────────────────

def _phase_name(plan, phase_id: int) -> str:
    """Human label for a phase id — falls back to a neutral name."""
    for p in getattr(plan, "phases", []) or []:
        if p.phase_id == phase_id and p.name:
            return p.name
    return f"Phase {phase_id + 1}"


@dataclass
class ObservationResult:
    """Pulse v2 Phase 5 — structured observation of a step's tool result.

    ``answer`` is the grounded final answer (or an interim one); when the
    model concludes it needs another read-only tool, ``needs_followup`` is
    True and ``followup_tool``/``followup_args`` name the next step.
    """
    answer: str | None = None
    needs_followup: bool = False
    followup_tool: str | None = None
    followup_args: dict | None = None


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
    # Pulse v2 Phase 5: read-only follow-up requested by the observation.
    followup: ObservationResult | None = None


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
        flight_director=None,     # FlightDirector — additive in-loop supervisor
    ):
        self.draft_witness = draft_witness
        self.critic_witness = critic_witness
        self.executor = executor
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.db = db
        self.flight_director = flight_director

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
        flight_director=None,     # FlightDirector — additive in-loop supervisor
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

        # Flight Director (additive): instance attr wins; per-run kwarg overrides.
        fd = flight_director if flight_director is not None else self.flight_director

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

        # Pulse v2 Phase 5: multi-hop follow-up budget + next-step id counter.
        followup_steps_used = 0
        _next_step_id = max((s.step_id for s in plan.steps), default=-1) + 1
        try:
            from ai.engine.core.config import get_settings
            _max_followup_steps = int(get_settings().PULSE_LOOP_MAX_STEPS)
        except Exception:  # noqa: BLE001 - settings read must never break the run
            _max_followup_steps = 6

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
                    flight_director=fd,
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

                # ── Pulse v2 Phase 5: inject a read-only follow-up step ────
                # When the observation concluded more data is needed and named
                # an allowed read-only tool, append a new step so the loop
                # fetches it automatically (multi-hop) — no new user message.
                if self._should_inject_followup(
                    result, followup_steps_used, _max_followup_steps
                ):
                    followup_steps_used += 1
                    _fu = result.followup
                    _fid = _next_step_id
                    _next_step_id += 1
                    _followup_step = PlanStep(
                        step_id=_fid,
                        intent=f"Fetch {_fu.followup_tool} to complete the answer",
                        tool_name=_fu.followup_tool,
                        tool_args=_fu.followup_args or {},
                        is_mutation=False,
                        depends_on=[step.step_id],
                        agent_role="orchestrator",
                    )
                    plan.steps.append(_followup_step)
                    remaining.append(_followup_step)
                    logger.info(
                        "ReActLoop: multi-hop follow-up step=%d tool=%s (%d/%d)",
                        _fid, _fu.followup_tool, followup_steps_used, _max_followup_steps,
                    )

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
        flight_director=None,   # FlightDirector — additive in-loop supervisor
    ) -> StepResult:
        """Execute one plan step: draft → critic → execute → observe."""

        # Build step-prompt with dependents' context
        enriched_prompt = self._build_step_prompt(
            step, user_message, system_prompt, step_contexts,
        )

        # ── Flight Director: prepare_step (additive, never fails the run) ─
        attempts = 0
        prep = None
        if flight_director is not None:
            try:
                prep = await flight_director.prepare_step(
                    step, flight_director.ledger, attempts=attempts,
                )
            except Exception:  # noqa: BLE001 - supervision must never fail the run
                logger.exception(
                    "FlightDirector.prepare_step failed step=%d", step.step_id,
                )
                prep = None
            if prep is not None:
                _guidance = []
                if prep.corrected_tool_args:
                    _guidance.append(
                        "Corrected tool arguments (use these exact ids): "
                        + json.dumps(prep.corrected_tool_args)
                    )
                if prep.extra_instructions:
                    _guidance.append(prep.extra_instructions)
                if _guidance:
                    enriched_prompt = (
                        enriched_prompt + "\n\nFLIGHT DIRECTOR:\n" + "\n".join(_guidance)
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
        _draft_kwargs = dict(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=enriched_prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            tools=step_tools,
        )
        if prep is not None and prep.model_override:
            _draft_kwargs["model"] = prep.model_override
        draft = await dw.draft(**_draft_kwargs)

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

            # ── Fix 3: mutation-tool output validation ─────────────────────
            # A confirmation-gated tool (create_dq_rule, learn_fact, …) MUST
            # return either a ``requires_confirmation`` proposal or an
            # ``error``. A null/empty/malformed output is a silent failure —
            # mark the step failed instead of "completed" (phantom-success
            # guard). Without this, a hallucinated create_dq_rule that staged
            # nothing was persisted "completed" and the run read "completed".
            if not result.error and not result.paused:
                _mto = result.tool_output or {}
                _mto_name = _mto.get("tool_name", "")
                if _tool_requires_confirmation(_mto_name):
                    _mraw = _mto.get("result", "")
                    try:
                        _mparsed = (
                            json.loads(_mraw) if isinstance(_mraw, str) else _mraw
                        )
                    except (json.JSONDecodeError, TypeError):
                        _mparsed = None
                    _is_null = _mparsed is None or (
                        isinstance(_mparsed, dict) and not _mparsed
                    )
                    _missing_keys = (
                        isinstance(_mparsed, dict)
                        and "requires_confirmation" not in _mparsed
                        and "error" not in _mparsed
                    )
                    if _is_null:
                        result.error = (
                            f"{_mto_name} returned no output "
                            f"(expected a confirmation response)"
                        )
                        result.critic_verdict = "veto"
                        if "null_output" not in result.critic_flags:
                            result.critic_flags.append("null_output")
                    elif _missing_keys:
                        result.error = (
                            f"{_mto_name} returned neither a confirmation nor "
                            f"an error — nothing was staged"
                        )
                        result.critic_verdict = "veto"
                        if "missing_confirmation_response" not in result.critic_flags:
                            result.critic_flags.append("missing_confirmation_response")

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

            # ── Pulse v2 Phase 1: observe — synthesize a grounded answer from a
            #    successfully executed tool result (draft→critic→execute→observe).
            #    Phase 5: the observation may also request a read-only follow-up.
            if result.tool_output and not result.error and not result.paused:
                _prior = ""
                if step.depends_on:
                    _deps = [
                        step_contexts[d] for d in step.depends_on
                        if step_contexts.get(d)
                    ]
                    _prior = "\n\n".join(_deps)
                _obs = await self._observe(
                    step=step, tool_output=result.tool_output, user_message=user_message,
                    system_prompt=system_prompt, conversation_history=conversation_history,
                    instance_config=instance_config, user_info=user_info, dw=dw,
                    prior_context=_prior,
                    model=model_for_profile("investigate") if _prior else None,
                )
                if _obs:
                    if _obs.answer:
                        result.draft_text = _obs.answer
                    if _obs.needs_followup and _obs.followup_tool:
                        result.followup = _obs

            # ── Flight Director: on_step_completed + bounded fidelity re-run ─
            # Additive supervisor. Read-only/idempotent steps may be re-run
            # ONCE when the worker's declared tool calls outnumber what actually
            # executed. Mutation steps are NEVER auto re-run (RULE_21) — those
            # escalate for human review instead.
            if flight_director is not None:
                try:
                    verdict = flight_director.on_step_completed(
                        step, draft, execution, result,
                        flight_director.ledger, attempts=attempts,
                    )
                except Exception:  # noqa: BLE001 - supervision never fails the run
                    logger.exception(
                        "FlightDirector.on_step_completed failed step=%d", step.step_id,
                    )
                    verdict = None

                if (
                    verdict is not None
                    and verdict.requests_rerun
                    and attempts == 0
                    and not step.is_mutation
                ):
                    attempts += 1
                    _retry_prompt = enriched_prompt
                    if verdict.extra_instructions:
                        _retry_prompt = (
                            enriched_prompt + "\n\n" + verdict.extra_instructions
                        )
                    logger.info(
                        "FlightDirector: fidelity re-run step=%d (%s)",
                        step.step_id, verdict.repair_kind,
                    )
                    try:
                        _draft2 = await dw.draft(
                            instance_id=instance_id,
                            conversation_id=conversation_id,
                            user_message=_retry_prompt,
                            system_prompt=system_prompt,
                            conversation_history=conversation_history,
                            instance_config=instance_config,
                            user_info=user_info,
                            tools=step_tools,
                            model=flight_director.escalation_model(),
                        )
                        _critic2 = await cw.review(
                            draft=_draft2,
                            retrieval=retrieval_stub,
                            is_mutation=step.is_mutation,
                            dry_run=dry_run,
                            confirmation_token=confirmation_token,
                        )
                        if _critic2.verdict != "veto":
                            set_current_step_index(step.step_id)
                            try:
                                _execution2 = await ex.execute(
                                    text=_draft2.text,
                                    tool_calls=_draft2.tool_calls,
                                    stream_callback=stream_callback,
                                    progress_callback=progress_callback,
                                    agent_role=agent_role or step.agent_role,
                                    is_worker=(step.agent_role not in ("orchestrator", "", None)),
                                )
                            finally:
                                set_current_step_index(None)
                            result.executed = True
                            result.draft_text = _draft2.text
                            result.tool_output = (
                                _execution2.completed_tools[0]
                                if _execution2.completed_tools else None
                            )
                            if (
                                result.tool_output
                                and isinstance(result.tool_output, dict)
                                and result.tool_output.get("error")
                            ):
                                result.error = str(result.tool_output["error"])
                            try:
                                flight_director.on_step_completed(
                                    step, _draft2, _execution2, result,
                                    flight_director.ledger, attempts=attempts,
                                )
                            except Exception:  # noqa: BLE001
                                logger.exception(
                                    "FlightDirector.on_step_completed (re-run) failed step=%d",
                                    step.step_id,
                                )
                    except Exception:  # noqa: BLE001 - re-run failure must not crash the run
                        logger.exception(
                            "FlightDirector fidelity re-run failed step=%d", step.step_id,
                        )

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

    async def _observe(
        self,
        *,
        step: PlanStep,
        tool_output,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        dw,
        prior_context: str = "",
        model: str | None = None,
    ) -> ObservationResult | None:
        """Pulse v2 Phase 1+5 — observe a tool result and decide next action.

        After a step's tool executes successfully, ask the draft witness for a
        grounded answer. Phase 5: the model may instead (or also) request ONE
        more read-only tool call to complete a multi-hop answer. Confirmation
        proposals (the consent gate owns them) and ``no_match`` payloads (the
        escalation/clarification path owns them) are never synthesized.
        """
        result_raw = tool_output.get("result") if isinstance(tool_output, dict) else tool_output

        # Confirmation proposal → never synthesize; the consent gate owns this.
        _parsed = result_raw
        if isinstance(_parsed, str):
            try:
                _parsed = json.loads(_parsed)
            except (TypeError, ValueError):
                _parsed = None
        if isinstance(_parsed, dict) and _parsed.get("requires_confirmation"):
            return None

        # no_match → never synthesize; escalation/clarification owns this.
        if payload_status(result_raw) == "no_match":
            return None

        tool_name = tool_output.get("tool_name", "tool") if isinstance(tool_output, dict) else "tool"
        result_text = result_raw if isinstance(result_raw, str) else json.dumps(
            result_raw, ensure_ascii=False, default=str,
        )
        result_text = result_text[:4000]

        prior_block = ""
        if prior_context and prior_context.strip():
            prior_block = f"\n\nPrior step results:\n{prior_context.strip()}\n"

        observation_prompt = (
            f"TOOL RESULT from {tool_name}:\n{result_text}\n"
            f"{prior_block}"
            f"Original question: {user_message}\n\n"
            "Decide whether the tool result above (plus any prior results) "
            "fully answers the original question, or whether you need ONE more "
            "tool call to complete it.\n"
            "Reply with ONLY a JSON object — no prose, no markdown fences:\n"
            '{"answer": "final or interim answer text", "needs_followup": false, '
            '"followup_tool": null, "followup_args": null}\n'
            "Rules:\n"
            "- If it fully answers the question, set needs_followup=false and "
            "write the final grounded answer in answer.\n"
            "- If you need another tool, set needs_followup=true, write a short "
            "interim answer (may be empty), set followup_tool to one of: "
            + ", ".join(sorted(_ALLOWED_FOLLOWUP_TOOLS))
            + ", and set followup_args to that tool's arguments.\n"
            "- Ground your answer ONLY in the given results — never invent data."
        )

        obs_draft = await dw.draft(
            instance_id="",
            conversation_id="",
            user_message=observation_prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            tools=None,
            model=model,
        )

        text = (obs_draft.text or "").strip()
        if not text:
            return None

        # Phase 5: parse the structured JSON decision when the model complied.
        try:
            _decision = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            _decision = None
        if isinstance(_decision, dict):
            answer = (_decision.get("answer") or "").strip() or None
            needs_followup = bool(_decision.get("needs_followup"))
            followup_tool = (_decision.get("followup_tool") or "").strip() or None
            followup_args = _decision.get("followup_args")
            followup_args = followup_args if isinstance(followup_args, dict) else None
            if answer or needs_followup:
                return ObservationResult(
                    answer=answer,
                    needs_followup=needs_followup,
                    followup_tool=followup_tool,
                    followup_args=followup_args,
                )

        # Fallback (Phase 1 behavior): plain prose = a grounded final answer.
        if len(text) > 20:
            return ObservationResult(answer=text, needs_followup=False)
        return None

    def _should_inject_followup(
        self,
        result: StepResult | None,
        followup_steps_used: int,
        max_steps: int,
    ) -> bool:
        """Pulse v2 Phase 5 guard — decide whether a follow-up may be injected.

        Bounds the number of auto-chained read-only steps (``max_steps``) and
        rejects anything outside the allow-list (mutations and planning tools
        included). Kept as a method so the budget/allow-list logic is testable
        without a full ReActLoop run.
        """
        return bool(
            result
            and result.followup
            and result.followup.needs_followup
            and result.followup.followup_tool in _ALLOWED_FOLLOWUP_TOOLS
            and followup_steps_used < max_steps
        )

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
