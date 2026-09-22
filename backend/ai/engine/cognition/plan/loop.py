"""
ReActLoop — Iterates a Plan step-by-step with critic gating + re-plan on failure.

PR-20: Executes each PlanStep through draft → critic → execute → observe,
with mutation confirmation gates, dry-run previews, and up to 2 replans.
"""
import asyncio
import inspect
import json
import logging
import time
from dataclasses import asdict, dataclass, field

from ai.engine.core.clock import utcnow
from ai.engine.core.resolution import payload_status
from ai.engine.core.query import first

from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.turn.witnesses import CriticVerdict, DraftResult, RetrievalResult
from ai.engine.llm.router import model_for_profile

logger = logging.getLogger("pulse.cognition.plan.loop")

_step_index_context = None


def _coerce_json_field(value, *, default=None):
    """Accept dict/list already decoded by Django JSONField, or a JSON string.

    Resume used to call ``json.loads`` unconditionally — DjangoStore returns
    native dicts, which raised ``TypeError: the JSON object must be str,
    bytes or bytearray, not dict`` and aborted the whole plan mid-run.
    """
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def set_step_index_context(fn) -> None:
    """Inject the host step-index contextvar setter (plans_service.set_current_step_index)."""
    global _step_index_context
    _step_index_context = fn


# Lazy import — resolved at first emit
_broadcast_run = None


def _get_broadcast():
    global _broadcast_run
    if _broadcast_run is None:
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
    return _broadcast_run


def _tool_requires_confirmation(tool_name: str) -> bool:
    """True when a registered plugin gates its write behind confirmation.

    Lazy import avoids a circular dependency; a lookup failure is now treated
    as confirmation-required (deny-by-default / fail-closed) so an unregistered
    or unavailable plugin registry can never silently downgrade a mutation to
    read-only.
    """
    requires_confirmation = True  # fail-closed default
    try:
        from ai.engine.agent.plugins import is_confirmation_tool
        requires_confirmation = is_confirmation_tool(tool_name)
    except Exception:  # noqa: BLE001 - guard must never raise into the run
        logger.warning(
            "confirmation-tool registry unavailable; treating %s as "
            "confirmation-required (fail-closed)",
            tool_name,
        )
    return requires_confirmation


def _hollow_tool_message(tool_output: dict | None) -> str | None:
    """Return an error message when a tool 'succeeded' with zero usable evidence.

    Empty ``web_research`` used to persist as Finished — operator saw green
    with 'No results were returned'. That is a hollow success; fail closed.
    """
    if not isinstance(tool_output, dict):
        return None
    name = (tool_output.get("tool_name") or "").strip()
    raw = tool_output.get("result")
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = None
    if not isinstance(parsed, dict):
        return None
    if name == "web_research" or "web_research" in name:
        results = parsed.get("results")
        if isinstance(results, list) and len(results) == 0:
            return (
                parsed.get("error")
                or parsed.get("message")
                or "Web research returned no results."
            )
        if parsed.get("status") == "no_match" and not results:
            return parsed.get("error") or "Web research returned no results."
    return None


def _strip_markdown_fence(text: str) -> str:
    """Return inner body when ``text`` is a single ```…``` fence; else stripped text."""
    raw = (text or "").strip()
    if not raw.startswith("```"):
        return raw
    lines = raw.splitlines()
    if len(lines) < 2:
        return raw
    # Drop opening fence (``` or ```json) and optional closing fence.
    body = lines[1:]
    if body and body[-1].strip().startswith("```"):
        body = body[:-1]
    return "\n".join(body).strip()


# Pulse v2 Phase 5: read-only tools the loop may auto-chain for multi-hop
# reasoning. Mutation/planning tools are deliberately excluded — an automatic
# follow-up must never write state or trigger a consent gate without the user.
# ``call_host_api`` is allowed only for GET (see ``_followup_is_readonly``).
_ALLOWED_FOLLOWUP_TOOLS = frozenset({
    "web_research",
    "get_entity_details",
    "search_knowledge",
    "call_host_api",
})

# Hard cap on auto-injected follow-ups per run (independent of PULSE_LOOP_MAX_STEPS).
# Live QA: uncapped chaining produced 3× "Fetch call_host_api" consent spam.
_MAX_AUTO_FOLLOWUPS = 2


def _followup_is_readonly(tool_name: str | None, tool_args: dict | None) -> bool:
    """True when an allow-listed follow-up cannot trigger RULE_21 consent."""
    if not tool_name:
        return False
    if tool_name != "call_host_api":
        return True
    args = tool_args or {}
    method = str(args.get("method") or "GET").upper()
    return method in ("GET", "HEAD", "OPTIONS")


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
    # Token usage from the draft LLM call (Monitor / ledger).
    tokens_used: int = 0


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
        workflow_graph=None,      # ADR-0034 WorkflowGraph | dict | None
        workflow_context: dict | None = None,
        on_workflow_choice=None,  # (node_id, chosen_edge|None, evaluations) -> None
        on_heal_proposed=None,    # (observe_node_id, HealProposal) -> None | awaitable
        on_compensation_queued=None,  # (failed_step_id, comp_step_id, node_id) -> ...
        on_wait_fired=None,       # (node_id, WaitDecision, duration_ms, until) -> ...
        max_heals: int | None = None,
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
            workflow_graph: optional ADR-0034 graph; when set, step eligibility
                is driven by ``advance_and_ready_tasks`` (choice / parallel)
            workflow_context: mutable guard-eval context (status, last verdict, …)
            on_workflow_choice: optional callback for journaling choice decisions
            on_heal_proposed: optional callback for journaling observe heals
            max_heals: override DEFAULT_MAX_HEALS for observe self-heal

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
        # S-PROC-01 / S-TRACE-01: the ReAct loop's ExecuteWitness must carry the
        # host executor (for ``call_host_api`` / ``search_knowledge`` grounding)
        # and the knowledge store. Previously it was built bare — the loop could
        # not reach the host executor or the knowledge backend at all.
        # Also thread instance_id / conversation into hook_ctx_defaults so
        # invoke_skill / call_host_api receive instance context (otherwise
        # invoke_skill fails with "No instance context").
        _host_executor = getattr(dw, "executor", None)
        _hook_defaults = {
            "instance_id": instance_id or "",
            "conversation_id": conversation_id or "",
            "host_user_id": host_user_id,
            "instance_config": instance_config,
            "user_message": user_message or "",
            # ADR-0046: ReAct / plan loops are agentic — may stage mutations.
            "surface": "plan",
        }
        if self.executor is not None:
            ex = self.executor
            # Merge turn context onto a pre-built witness that lacked it.
            merged = dict(getattr(ex, "hook_ctx_defaults", None) or {})
            for k, v in _hook_defaults.items():
                if v is not None and not merged.get(k):
                    merged[k] = v
            ex.hook_ctx_defaults = merged
            if not getattr(ex, "instance_id", None) and instance_id:
                ex.instance_id = instance_id
        else:
            ex = ExecuteWitness(
                executor=_host_executor,
                knowledge_store=self.knowledge_store,
                instance_id=instance_id or "",
                hook_ctx_defaults=_hook_defaults,
            )

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
                            critic_flags=_coerce_json_field(
                                s.critic_flags_json, default=[],
                            ) or [],
                            executed=s.status == "completed",
                            tool_output=_coerce_json_field(
                                s.tool_output_json, default=None,
                            ),
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

        # ADR-0034: optional workflow graph drives choice / parallel eligibility.
        _wf_graph = None
        if workflow_graph is not None:
            try:
                from ai.engine.workflow.graph import WorkflowGraph
                if isinstance(workflow_graph, WorkflowGraph):
                    _wf_graph = workflow_graph
                elif isinstance(workflow_graph, dict):
                    _wf_graph = WorkflowGraph.from_dict(workflow_graph)
            except Exception:  # noqa: BLE001 — never block a run on bad graph
                logger.exception("ReActLoop: failed to load workflow_graph; using depends_on")
                _wf_graph = None
        _wf_ctx: dict = workflow_context if workflow_context is not None else {}
        _wf_gateways: set[str] = set()
        _wf_skipped_nodes: set[str] = set()
        _wf_journaled: set[str] = set()
        _wf_choice_batch: list[tuple] = []
        _gap_step_ids: set[int] = set()
        _heals_used = 0
        _wf_loop_iters: dict[str, int] = {}
        _wf_map_iters: dict[str, int] = {}
        _wf_wait_started: dict[str, float] = {}
        try:
            from ai.engine.workflow.heal import DEFAULT_MAX_HEALS as _DEFAULT_MAX_HEALS
            _max_heals = int(max_heals) if max_heals is not None else _DEFAULT_MAX_HEALS
        except Exception:  # noqa: BLE001
            _max_heals = 1

        def _requeue_body_steps(body_ids: list[int]) -> None:
            nonlocal remaining
            _plan_by = {s.step_id: s for s in plan.steps}
            for _bsid in body_ids:
                completed_ids.discard(_bsid)
                _bs = _plan_by.get(_bsid)
                if _bs is None:
                    continue
                remaining = [s for s in remaining if s.step_id != _bsid]
                remaining.insert(0, _bs)

        def _on_choice(node_id, chosen, evaluations):
            if node_id in _wf_journaled:
                return
            _wf_journaled.add(node_id)
            _wf_choice_batch.append((node_id, chosen, evaluations))

        async def _flush_choice_journal():
            if not _wf_choice_batch or on_workflow_choice is None:
                _wf_choice_batch.clear()
                return
            for node_id, chosen, evaluations in _wf_choice_batch:
                try:
                    maybe = on_workflow_choice(node_id, chosen, evaluations)
                    if inspect.isawaitable(maybe):
                        await maybe
                except Exception:  # noqa: BLE001 — journaling must not halt the run
                    logger.exception(
                        "ReActLoop: on_workflow_choice failed node=%s", node_id,
                    )
            _wf_choice_batch.clear()

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

        stopped_for_cancel = False
        total_tokens = 0
        while remaining:
            # Operator Stop (cancel_plan) must halt the in-memory loop. Without
            # this poll, ReAct keeps executing and _finalize_run clobbers
            # ``cancelled`` → ``completed`` (live QA: Stop → Completed 6/7).
            if _db is not None and run_id is not None:
                if await self._run_is_cancelled(_db, run_id):
                    stopped_for_cancel = True
                    logger.info("ReActLoop: cancel observed mid-run id=%s", run_id)
                    break
            # ADR-0034: when a workflow graph is present, it owns eligibility
            # (choice / parallel / auto gateways). Otherwise classic depends_on.
            if _wf_graph is not None:
                from ai.engine.workflow.driver import (
                    advance_and_ready_tasks,
                    incoming,
                    node_for_step,
                    step_id_for_node,
                )
                from ai.engine.workflow.loops import (
                    body_step_ids,
                    evaluate_loop,
                    evaluate_map,
                )

                # Seed completed graph ids for loop/map gateway checks.
                _completed_graph = set(_wf_gateways) | set(_wf_skipped_nodes)
                for _sid in completed_ids:
                    _n = node_for_step(_wf_graph, _sid)
                    if _n is not None:
                        _completed_graph.add(_n.id)

                # Map fan-out: one body pass per collection item.
                for _mn in _wf_graph.nodes:
                    if _mn.node_type != "map" or _mn.id in _wf_gateways:
                        continue
                    if _mn.id in _wf_skipped_nodes:
                        continue
                    _preds = incoming(_wf_graph, _mn.id)
                    if _preds and not all(
                        e.source in _completed_graph for e in _preds
                    ):
                        continue
                    _body_done = True
                    if _wf_map_iters.get(_mn.id, 0) > 0:
                        for _bsid in body_step_ids(_wf_graph, _mn):
                            if _bsid not in completed_ids:
                                _body_done = False
                                break
                    if not _body_done:
                        continue
                    _action, _body, _wf_map_iters, _item = evaluate_map(
                        _wf_graph, _mn, _wf_ctx, _wf_map_iters,
                    )
                    if _action == "body" and _body:
                        _wf_ctx["map_item"] = _item
                        _wf_ctx["map_index"] = int(_wf_map_iters.get(_mn.id, 1)) - 1
                        _wf_ctx["map_node"] = _mn.id
                        _requeue_body_steps(_body)
                        await _get_broadcast()(instance_id, "run.map.iter", {
                            "run_id": run_id,
                            "map_node": _mn.id,
                            "map_index": _wf_ctx["map_index"],
                            "body_step_ids": _body,
                        })
                    else:
                        _wf_gateways.add(_mn.id)
                        _wf_ctx.pop("map_item", None)

                # Bounded while-loops: re-queue body steps while guard holds.
                for _ln in _wf_graph.nodes:
                    if _ln.node_type != "loop" or _ln.id in _wf_gateways:
                        continue
                    if _ln.id in _wf_skipped_nodes:
                        continue
                    _preds = incoming(_wf_graph, _ln.id)
                    if _preds and not all(
                        e.source in _completed_graph for e in _preds
                    ):
                        continue
                    _body_done = True
                    if _wf_loop_iters.get(_ln.id, 0) > 0:
                        for _bsid in body_step_ids(_wf_graph, _ln):
                            if _bsid not in completed_ids:
                                _body_done = False
                                break
                    if not _body_done:
                        continue

                    _wf_ctx["loop_iter"] = _wf_loop_iters.get(_ln.id, 0)
                    _wf_ctx["loop_node"] = _ln.id
                    _action, _body, _wf_loop_iters = evaluate_loop(
                        _wf_graph,
                        _ln,
                        _wf_ctx,
                        _wf_loop_iters,
                        on_loop_iter=lambda nid, n, mx: logger.info(
                            "ReActLoop: loop %s iter %d/%d", nid, n, mx,
                        ),
                    )
                    if _action == "body" and _body:
                        _requeue_body_steps(_body)
                        await _get_broadcast()(instance_id, "run.loop.iter", {
                            "run_id": run_id,
                            "loop_node": _ln.id,
                            "iteration": _wf_loop_iters.get(_ln.id),
                            "max_iterations": _ln.max_iterations,
                            "body_step_ids": _body,
                        })
                    else:
                        _wf_gateways.add(_ln.id)
                        _skip_body = [
                            s for s in remaining
                            if s.step_id in set(body_step_ids(_wf_graph, _ln))
                            and s.step_id not in completed_ids
                        ]
                        if _skip_body:
                            remaining = [
                                s for s in remaining
                                if s.step_id not in {x.step_id for x in _skip_body}
                            ]
                            for _ss in _skip_body:
                                step_results.append(StepResult(
                                    step_id=_ss.step_id,
                                    intent=_ss.intent,
                                    critic_verdict="pass",
                                    executed=False,
                                    error="loop_exited",
                                ))
                                completed_ids.add(_ss.step_id)

                # Wait timers / until-guards (host-driven; not auto-advanced).
                from ai.engine.workflow.wait import (
                    evaluate_wait,
                    wait_duration_ms,
                    wait_until_guard,
                )
                import time as _time

                for _wnode in _wf_graph.nodes:
                    if _wnode.node_type != "wait" or _wnode.id in _wf_gateways:
                        continue
                    if _wnode.id in _wf_skipped_nodes:
                        continue
                    _preds = incoming(_wf_graph, _wnode.id)
                    if _preds and not all(
                        e.source in _completed_graph for e in _preds
                    ):
                        continue
                    _started = _wf_wait_started.setdefault(
                        _wnode.id, _time.monotonic(),
                    )
                    _elapsed_ms = int((_time.monotonic() - _started) * 1000)
                    _decision = evaluate_wait(
                        _wnode, _wf_ctx, elapsed_ms=_elapsed_ms,
                    )
                    if not _decision.satisfied and _decision.sleep_ms > 0:
                        await _get_broadcast()(instance_id, "run.wait.sleep", {
                            "run_id": run_id,
                            "wait_node": _wnode.id,
                            "sleep_ms": _decision.sleep_ms,
                            "elapsed_ms": _elapsed_ms,
                        })
                        # Cap per-tick sleep; re-evaluate next loop turn if longer.
                        _chunk = min(_decision.sleep_ms, 5_000) / 1000.0
                        await asyncio.sleep(_chunk)
                        if _db is not None and run_id is not None:
                            if await self._run_is_cancelled(_db, run_id):
                                stopped_for_cancel = True
                                break
                        _elapsed_ms = int(
                            (_time.monotonic() - _wf_wait_started[_wnode.id]) * 1000
                        )
                        _decision = evaluate_wait(
                            _wnode, _wf_ctx, elapsed_ms=_elapsed_ms,
                        )
                    if not _decision.satisfied:
                        # until-only still pending — leave wait incomplete.
                        continue
                    _wf_gateways.add(_wnode.id)
                    _completed_graph.add(_wnode.id)
                    _wf_wait_started.pop(_wnode.id, None)
                    await _get_broadcast()(instance_id, "run.wait.fired", {
                        "run_id": run_id,
                        "wait_node": _wnode.id,
                        "reason": _decision.reason,
                        "duration_ms": wait_duration_ms(_wnode),
                    })
                    if on_wait_fired is not None:
                        _maybe = on_wait_fired(
                            _wnode.id,
                            _decision,
                            wait_duration_ms(_wnode),
                            wait_until_guard(_wnode),
                        )
                        if inspect.isawaitable(_maybe):
                            await _maybe
                    logger.info(
                        "ReActLoop: wait %s fired reason=%s duration_ms=%s until=%s",
                        _wnode.id,
                        _decision.reason,
                        wait_duration_ms(_wnode),
                        wait_until_guard(_wnode),
                    )

                if stopped_for_cancel:
                    break

                ready_ids, newly_skipped, _wf_gateways, _wf_skipped_nodes = (
                    advance_and_ready_tasks(
                        _wf_graph,
                        completed_ids,
                        _wf_ctx,
                        completed_gateways=_wf_gateways,
                        skipped_graph_ids=_wf_skipped_nodes,
                        on_choice=_on_choice,
                    )
                )
                await _flush_choice_journal()
                if newly_skipped:
                    skip_steps = [
                        s for s in remaining if s.step_id in newly_skipped
                    ]
                    remaining = [
                        s for s in remaining if s.step_id not in newly_skipped
                    ]
                    for _ss in skip_steps:
                        step_results.append(StepResult(
                            step_id=_ss.step_id,
                            intent=_ss.intent,
                            critic_verdict="pass",
                            executed=False,
                            error=None,
                        ))
                        completed_ids.add(_ss.step_id)
                        if _db is not None and run_id is not None:
                            await self._persist_skipped_step(
                                _db, run_id, _ss, reason="unchosen_branch",
                            )
                        await _get_broadcast()(instance_id, "run.step.skipped", {
                            "run_id": run_id,
                            "step_index": _ss.step_id,
                            "intent": _ss.intent,
                            "reason": "unchosen_branch",
                        })
                # Runtime follow-ups / heal inserts are not in the compiled
                # workflow_graph. Promote them when depends_on are met so the
                # graph path cannot leave Pending orphans under Completed.
                _graph_sids: set[int] = set()
                for _gn in _wf_graph.nodes:
                    _gsid = step_id_for_node(_gn)
                    if _gsid is not None:
                        _graph_sids.add(_gsid)
                _ready_set = set(ready_ids)
                for _s in remaining:
                    if _s.step_id in _ready_set or _s.step_id in newly_skipped:
                        continue
                    if _s.step_id in _graph_sids:
                        continue
                    if all(d in completed_ids for d in (_s.depends_on or [])):
                        ready_ids.append(_s.step_id)
                        _ready_set.add(_s.step_id)
                ready_id_set = set(ready_ids)
                by_remaining = {s.step_id: s for s in remaining}
                ready = [
                    by_remaining[sid] for sid in ready_ids if sid in by_remaining
                ]
                remaining = [
                    s for s in remaining if s.step_id not in ready_id_set
                ]
            else:
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
                # With a workflow graph, do NOT force-run remaining (would
                # execute unchosen XOR branches); exit cleanly instead —
                # unless a wait timer is still pending (re-enter outer loop).
                if remaining and _wf_graph is None:
                    logger.warning(
                        "ReActLoop: phase barrier/circular deps block ready set; "
                        "running remaining sequentially"
                    )
                    ready, remaining = remaining[:1], remaining[1:]
                elif remaining and _wf_graph is not None:
                    if _wf_wait_started:
                        # Timer / until still open — keep looping (sleep already
                        # happened in the wait handler above).
                        continue
                    logger.warning(
                        "ReActLoop: workflow graph has no ready tasks with %d "
                        "remaining; stopping (not force-running)",
                        len(remaining),
                    )
                    break
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
                _retry_policy = None
                _timeout_ms = None
                if _wf_graph is not None:
                    from ai.engine.workflow.driver import node_for_step
                    _wn = node_for_step(_wf_graph, step.step_id)
                    if _wn is not None:
                        _retry_policy = _wn.retry
                        _timeout_ms = _wn.timeout_ms
                _exec_coro = self._execute_step(
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
                    host_user_id=host_user_id,
                    retry_policy=_retry_policy,
                    prior_results=list(step_results),
                )
                # Hard-cancel: race step I/O against operator Stop (cancel_plan).
                _task = asyncio.create_task(_exec_coro)

                async def _poll_cancel():
                    while not _task.done():
                        if _db is not None and run_id is not None:
                            if await self._run_is_cancelled(_db, run_id):
                                return True
                        await asyncio.sleep(0.25)
                    return False

                _watcher = asyncio.create_task(_poll_cancel())
                _waiters = {_task, _watcher}
                _timeout_s = (
                    float(_timeout_ms) / 1000.0
                    if _timeout_ms and int(_timeout_ms) > 0
                    else None
                )
                try:
                    _done, _pending = await asyncio.wait(
                        _waiters,
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=_timeout_s,
                    )
                    if _task in _done:
                        _watcher.cancel()
                        try:
                            await _watcher
                        except asyncio.CancelledError:
                            pass
                        try:
                            _res = _task.result()
                        except asyncio.CancelledError:
                            _res = StepResult(
                                step_id=step.step_id,
                                intent=step.intent,
                                critic_verdict="veto",
                                executed=False,
                                error="[cancelled] operator stop",
                            )
                    elif _watcher in _done and _watcher.result():
                        _task.cancel()
                        try:
                            await _task
                        except asyncio.CancelledError:
                            pass
                        _res = StepResult(
                            step_id=step.step_id,
                            intent=step.intent,
                            critic_verdict="veto",
                            executed=False,
                            error="[cancelled] operator stop",
                        )
                    else:
                        # Overall step timeout
                        _task.cancel()
                        _watcher.cancel()
                        try:
                            await _task
                        except asyncio.CancelledError:
                            pass
                        try:
                            await _watcher
                        except asyncio.CancelledError:
                            pass
                        _res = StepResult(
                            step_id=step.step_id,
                            intent=step.intent,
                            critic_verdict="veto",
                            executed=False,
                            error=f"[timeout] exceeded timeout_ms={_timeout_ms}",
                        )
                except Exception:
                    _task.cancel()
                    _watcher.cancel()
                    raise
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
                total_tokens += int(getattr(result, "tokens_used", 0) or 0)

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

                # ── W-4 catch / W-5 observe heal (before persist) ─────
                # Exhausted veto or hard tool error may route to catch.next.
                # Mark the error ``[caught]`` so reconcile can emit
                # ``completed_with_gaps`` instead of hard-failed.
                _catch_healed = False
                _mid_veto_replan = (
                    result.critic_verdict == "veto"
                    and replans_used < self.MAX_REPLANS
                )
                if (
                    _wf_graph is not None
                    and not result.paused
                    and not _mid_veto_replan
                    and (result.error or result.critic_verdict == "veto")
                ):
                    from ai.engine.workflow.compensate import compensation_step_id
                    from ai.engine.workflow.driver import (
                        node_for_step,
                        resolve_catch,
                        step_id_for_node,
                    )
                    from ai.engine.workflow.heal import propose_heal
                    from ai.engine.workflow.retry import classify_error

                    _node = node_for_step(_wf_graph, step.step_id)
                    _err_class = classify_error(
                        result.error or f"critic:{result.critic_verdict}"
                    )
                    _catch_id = resolve_catch(_node, _err_class)
                    if _catch_id:
                        _raw_err = result.error or f"critic:{result.critic_verdict}"
                        if not str(_raw_err).startswith("[caught]"):
                            result.error = f"[caught] {_raw_err}"
                        _gap_step_ids.add(step.step_id)
                        _by = {n.id: n for n in _wf_graph.nodes}
                        _catch_node = _by.get(_catch_id)
                        if (
                            _catch_node is not None
                            and _catch_node.node_type == "observe"
                            and _heals_used < _max_heals
                        ):
                            _proposal = propose_heal(
                                goal=user_message or plan.synthesis_instruction or "",
                                failed_step=step,
                                failed_error=result.error,
                                remaining_steps=remaining,
                                next_step_id=_next_step_id,
                            )
                            _heals_used += 1
                            _wf_gateways.add(_catch_id)
                            _next_step_id = max(
                                _next_step_id,
                                max(
                                    (s.step_id for s in _proposal.new_steps),
                                    default=_next_step_id - 1,
                                ) + 1,
                            )
                            remaining = list(_proposal.new_steps)
                            _existing_ids = {s.step_id for s in plan.steps}
                            for _ns in _proposal.new_steps:
                                if _ns.step_id not in _existing_ids:
                                    plan.steps.append(_ns)
                                    _existing_ids.add(_ns.step_id)
                            if on_heal_proposed is not None:
                                try:
                                    _maybe = on_heal_proposed(
                                        _catch_id, _proposal,
                                    )
                                    if inspect.isawaitable(_maybe):
                                        await _maybe
                                except Exception:  # noqa: BLE001
                                    logger.exception(
                                        "ReActLoop: on_heal_proposed failed node=%s",
                                        _catch_id,
                                    )
                            await _get_broadcast()(instance_id, "run.heal.proposed", {
                                "run_id": run_id,
                                "observe_node": _catch_id,
                                "failed_step": step.step_id,
                                "summary": _proposal.summary,
                                "gap_step_ids": list(_proposal.gap_step_ids),
                            })
                            _catch_healed = True
                            logger.info(
                                "ReActLoop: observe heal after step %d → %d new steps",
                                step.step_id, len(_proposal.new_steps),
                            )
                        elif _catch_node is not None and _catch_node.node_type == "task":
                            # Catch → fallback/compensate task (RULE_21 if mutation).
                            _csid = step_id_for_node(_catch_node)
                            if _csid is not None:
                                _requeue_body_steps([_csid])
                                _plan_by = {s.step_id: s for s in plan.steps}
                                _cs = _plan_by.get(_csid)
                                if _cs is not None and (
                                    _catch_node.is_mutation or _node and _node.compensation
                                ):
                                    _cs.is_mutation = True
                                await _get_broadcast()(
                                    instance_id, "run.catch.routed", {
                                        "run_id": run_id,
                                        "failed_step": step.step_id,
                                        "catch_node": _catch_id,
                                        "catch_step_id": _csid,
                                        "error_class": _err_class,
                                    },
                                )
                                _catch_healed = True

                    # Saga: node.compensation queues a reversal step (consent-gated).
                    if not _catch_healed and _node is not None and _node.compensation:
                        _comp_sid = compensation_step_id(_wf_graph, _node)
                        if _comp_sid is not None:
                            if result.error and not str(result.error).startswith("[caught]"):
                                result.error = f"[caught] {result.error}"
                            _gap_step_ids.add(step.step_id)
                            _requeue_body_steps([_comp_sid])
                            _plan_by = {s.step_id: s for s in plan.steps}
                            _cs = _plan_by.get(_comp_sid)
                            if _cs is not None:
                                _cs.is_mutation = True  # RULE_21 — never auto-write
                            await _get_broadcast()(
                                instance_id, "run.compensation.queued", {
                                    "run_id": run_id,
                                    "failed_step": step.step_id,
                                    "compensation_step_id": _comp_sid,
                                    "compensation_node": _node.compensation,
                                },
                            )
                            if on_compensation_queued is not None:
                                try:
                                    _maybe = on_compensation_queued(
                                        step.step_id, _comp_sid, _node.compensation,
                                    )
                                    if inspect.isawaitable(_maybe):
                                        await _maybe
                                except Exception:  # noqa: BLE001
                                    logger.exception(
                                        "ReActLoop: on_compensation_queued failed",
                                    )
                            _catch_healed = True
                            logger.info(
                                "ReActLoop: compensation queued step %d after failure of %d",
                                _comp_sid, step.step_id,
                            )

                # ── P1.1: Persist RunStep row ──────────────────────────
                if _db is not None and run_id is not None:
                    await self._persist_run_step(
                        _db=_db,
                        run_id=run_id,
                        step=step,
                        result=result,
                        step_latency_ms=step_latency,
                    )

                if result.critic_verdict == "veto" and not _catch_healed:
                    if result.error and "[cancelled]" in str(result.error):
                        stopped_for_cancel = True
                        break
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

                # ADR-0034: refresh guard context for subsequent choice nodes.
                if _wf_graph is not None:
                    _ok = (
                        not result.error
                        and result.critic_verdict != "veto"
                        and not result.paused
                    )
                    # Caught failures still set status=failed for guards, but
                    # the run continues via the heal / catch path.
                    _wf_ctx["status"] = "ok" if _ok else "failed"
                    _wf_ctx["last_step_id"] = step.step_id
                    _wf_ctx["last_verdict"] = result.critic_verdict or ""
                    _wf_ctx["caught"] = bool(
                        result.error and str(result.error).startswith("[caught]")
                    )
                    _wf_ctx[f"step_{step.step_id}"] = {
                        "status": _wf_ctx["status"],
                        "verdict": result.critic_verdict or "",
                        "error": result.error,
                        "caught": _wf_ctx["caught"],
                    }

                if _catch_healed:
                    # Repaired remainder uses classic depends_on (new recovery
                    # steps are not in the original workflow_graph).
                    _wf_graph = None
                    break

                # ── Pulse v2 Phase 5: inject a read-only follow-up step ────
                # When the observation concluded more data is needed and named
                # an allowed read-only tool, append a new step so the loop
                # fetches it automatically (multi-hop) — no new user message.
                if self._should_inject_followup(
                    result, followup_steps_used, _max_followup_steps
                ):
                    _fu = result.followup
                    _sig = self._followup_signature(
                        _fu.followup_tool, _fu.followup_args,
                    )
                    _dup = any(
                        self._followup_signature(s.tool_name, s.tool_args) == _sig
                        for s in list(remaining) + list(plan.steps)
                        if getattr(s, "tool_name", None)
                    )
                    if _dup:
                        logger.info(
                            "ReActLoop: coalesce duplicate follow-up tool=%s",
                            _fu.followup_tool,
                        )
                    else:
                        followup_steps_used += 1
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

            if stopped_for_pause or stopped_for_cancel:
                break  # stop the entire loop (outer while)

        # ── Check for pause (consent gate hit) / operator cancel ──────────
        is_paused = bool(step_results and step_results[-1].paused)
        is_cancelled = stopped_for_cancel
        if not is_cancelled and _db is not None and run_id is not None:
            is_cancelled = await self._run_is_cancelled(_db, run_id)

        # Truthful Done: never leave Pending steps under a Completed run.
        # Skip anything still queued (stuck deps, orphan follow-ups, barrier).
        if remaining and not is_paused and not is_cancelled:
            for _ss in list(remaining):
                step_results.append(StepResult(
                    step_id=_ss.step_id,
                    intent=_ss.intent,
                    critic_verdict="pass",
                    executed=False,
                    error=None,
                ))
                completed_ids.add(_ss.step_id)
                if _db is not None and run_id is not None:
                    await self._persist_skipped_step(
                        _db, run_id, _ss, reason="unrun_at_finalize",
                    )
                await _get_broadcast()(instance_id, "run.step.skipped", {
                    "run_id": run_id,
                    "step_index": _ss.step_id,
                    "intent": _ss.intent,
                    "reason": "unrun_at_finalize",
                })
            remaining = []

        if is_paused:
            # Don't synthesize — return the confirmation prompt
            last = step_results[-1]
            final_response = _extract_confirmation_message(last.tool_output)
            succeeded = False
            final_status = "paused"
        elif is_cancelled:
            final_response = "Run stopped — remaining steps were not executed."
            succeeded = False
            final_status = "cancelled"
        else:
            # ── Synthesise final response ─────────────────────────────────
            # Confirmed host writes already carry an honest receipt — do NOT
            # re-narrate via LLM (it invents future-tense "I'll submit…" and
            # pastes stale observe JSON from earlier read steps).
            if self._has_confirmed_host_write(step_results):
                final_response = self._fallback_final_response(step_results)
            else:
                final_response = await self._synthesise(
                    plan, step_results, user_message, system_prompt, step_contexts,
                    instance_id=instance_id,
                    gap_step_ids=sorted(_gap_step_ids),
                )
            host_actions_md = self._host_actions_markdown(step_results)
            if host_actions_md:
                final_response = self._merge_host_actions_markdown(
                    final_response, host_actions_md,
                )
            elif not (final_response or "").strip():
                final_response = self._fallback_final_response(step_results)
            ok_results = [
                r for r in step_results
                if r.critic_verdict in ("pass", "pass_with_flag") and not r.error
            ]
            caught = [
                r for r in step_results
                if r.error and str(r.error).startswith("[caught]")
            ]
            hard_fails = [
                r for r in step_results
                if (r.error or r.critic_verdict == "veto")
                and not (r.error and str(r.error).startswith("[caught]"))
            ]
            if ok_results and caught and not hard_fails:
                succeeded = True
                final_status = "completed_with_gaps"
            elif hard_fails:
                succeeded = False
                final_status = "failed"
            elif not step_results:
                # Empty work is NOT success when the durable run still has
                # open steps (the "Completed + 0/N pending" lie). Fail closed.
                open_n = await self._count_open_steps(_db, run_id) if (
                    _db is not None and run_id is not None
                ) else 0
                if open_n > 0:
                    succeeded = False
                    final_status = "failed"
                    final_response = (
                        "Run ended without executing any steps "
                        f"({open_n} still pending). Re-approve to retry."
                    )
                else:
                    succeeded = True
                    final_status = "completed"
            else:
                succeeded = all(
                    r.critic_verdict in ("pass", "pass_with_flag") and not r.error
                    for r in step_results
                )
                final_status = "completed" if succeeded else "failed"

        # ── P1.1: Update Run row with final status ────────────────────────
        if _db is not None and run_id is not None:
            total_latency = round((time.monotonic() - t0) * 1000, 1)
            if is_paused or is_cancelled:
                # Pause/cancel already own the Run status — never clobber via
                # _finalize_run (that path wrote completed/failed and hid Stop).
                from ai.engine.core.models import Run
                row = first(await _db.select(Run, ("id", run_id)))
                if row:
                    row.total_llm_calls = total_llm_calls
                    row.total_latency_ms = total_latency
                    row.total_tokens = (row.total_tokens or 0) + total_tokens
                    if is_cancelled and not final_response:
                        pass
                    elif is_cancelled:
                        row.final_response = (final_response or "")[:2000]
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
                    total_tokens=total_tokens,
                    step_results=step_results,
                    final_status=final_status,
                )

        if not is_paused and not is_cancelled:
            _total_latency = round((time.monotonic() - t0) * 1000, 1)
            _evt = (
                "run.completed"
                if final_status in ("completed", "completed_with_gaps")
                else "run.failed"
            )
            await _get_broadcast()(instance_id, _evt, {
                "run_id": run_id,
                "status": final_status,
                "total_latency_ms": _total_latency,
                "total_llm_calls": total_llm_calls,
                "steps_completed": len([
                    r for r in step_results
                    if r.critic_verdict in ("pass", "pass_with_flag") and not r.error
                ]),
                "steps_failed": len([
                    r for r in step_results
                    if r.error or r.critic_verdict == "veto"
                ]),
                "gap_step_ids": sorted(_gap_step_ids),
            })
        elif is_cancelled:
            await _get_broadcast()(instance_id, "run.cancelled", {
                "run_id": run_id,
                "total_llm_calls": total_llm_calls,
                "steps_completed": len([r for r in step_results if r.critic_verdict in ("pass", "pass_with_flag")]),
            })

        return ReActResult(
            plan=plan,
            step_results=step_results,
            final_response=final_response,
            succeeded=succeeded and not is_cancelled,
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
        host_user_id: str | None = None,
        retry_policy: dict | None = None,
        prior_results: list | None = None,
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
                d for d in get_tool_definitions(instance_config)
                if d.get("function", {}).get("name") == step.tool_name
            ] or None
        elif plan_source == "single_step":
            # Single-step passthrough: mirror runner.py's curated allow-set so
            # a plain imperative request still dispatches a tool.
            _allow = {
                "create_dq_rule",
                "search_knowledge",
                "get_entity_details",
                "call_host_api",
                "list_my_capabilities",
                "plan_task",
                "resolve_entity",
                "aggregate_entity",
            }
            step_tools = [
                d for d in get_tool_definitions(instance_config)
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
            tokens_used=int(getattr(draft, "tokens_used", 0) or 0),
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
                # ── P2-06d: route the consent gate through the command
                # boundary so the consent decision is a boundary outcome
                # (stage-7 refusal), not a loop-local veto→pause. The seam is
                # looked up defensively; when absent (no host executor, e.g.
                # unit-test fakes) the legacy pause logic runs unchanged.
                _host = getattr(ex, "executor", None)
                _seam = getattr(_host, "execute_step_via_boundary", None)
                _requires_consent = True
                if callable(_seam):
                    _consent = await _seam(
                        effect=None,
                        tool_name=step.tool_name or "plan_step",
                        is_mutation=True,
                        confirmation_token=None,
                        instance_id=instance_id,
                        host_user_id=host_user_id,
                        conversation_id=conversation_id,
                    )
                    # The boundary refused the no-token mutation at its consent
                    # stage → still pause exactly as before. A False here is
                    # defensive (should not happen for a no-token mutation):
                    # fall through to the critic-veto path unchanged.
                    _requires_consent = bool(_consent.get("requires_confirmation"))

                if _requires_consent:
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
            # Deterministic export bind: prior structured outputs → content/table/images
            # before export_document runs (RULE_20 pure helper).
            from ai.engine.cognition.plan.export_bind import apply_bind_to_tool_calls

            _deps = set(step.depends_on or [])
            _priors = list(prior_results or [])
            if _deps:
                _priors = [r for r in _priors if getattr(r, "step_id", None) in _deps] or _priors
            _title_fb = (
                (step.tool_args or {}).get("title")
                or (step.intent or "Agent report")[:80]
            )
            _bound_calls = apply_bind_to_tool_calls(
                draft.tool_calls,
                _priors,
                step_tool_name=step.tool_name,
                step_tool_args=step.tool_args,
                title_fallback=str(_title_fb),
            )

            # W6-D: record the dispatching step so export-style plugins can
            # attribute artifacts to THIS step (multi-step / parallel runs).
            # Contextvars flow onto the sync_to_async worker thread via
            # asgiref, and are cleared so sibling steps never bleed.
            if _step_index_context is not None:
                _step_index_context(step.step_id)
            try:
                execution = await ex.execute(
                    text=draft.text,
                    tool_calls=_bound_calls,
                    stream_callback=stream_callback,
                    progress_callback=progress_callback,
                    agent_role=agent_role or step.agent_role,
                    is_worker=(step.agent_role not in ("orchestrator", "", None)),
                )
            finally:
                if _step_index_context is not None:
                    _step_index_context(None)
            result.executed = True
            result.tool_output = execution.completed_tools[0] if execution.completed_tools else None

            # ── No-op mutation guard (RULE_21 honesty) ────────────────────
            # A mutation step that produced no tool result wrote nothing:
            # the model narrated the effect ("submitted", "please confirm")
            # instead of calling the tool. Drafted prose is not an effect, so
            # the step fails visibly rather than reporting "done" on a plan
            # whose whole purpose was the write.
            if step.is_mutation and result.tool_output is None and not result.error:
                result.error = (
                    "No tool call was made, so nothing was written. "
                    "Re-run this step to apply the change."
                )
                logger.warning(
                    "ReActLoop: mutation step %d completed without a tool call "
                    "(tool=%s) — surfaced as failure",
                    step.step_id, step.tool_name or "?",
                )

            # ── Tool-error propagation + bounded retry (W-4 policy) ───────
            # Per-node ``retry`` from the workflow graph wins; otherwise the
            # default transient policy applies. Mutations are never auto-retried
            # (RULE_21).
            from ai.engine.workflow.retry import (
                backoff_seconds,
                normalize_retry_policy,
                should_retry,
            )

            _policy = normalize_retry_policy(retry_policy)
            _tool_attempt = 0
            if result.tool_output and isinstance(result.tool_output, dict):
                _tool_err = result.tool_output.get("error")
                while (
                    _tool_err
                    and not step.is_mutation
                    and should_retry(_policy, _tool_err, _tool_attempt)
                ):
                    _tool_attempt += 1
                    _delay = backoff_seconds(_policy, _tool_attempt)
                    logger.info(
                        "ReActLoop: retrying step %d tool=%s (attempt %d/%d, wait=%.2fs): %s",
                        step.step_id,
                        step.tool_name or "?",
                        _tool_attempt,
                        int(_policy["max_attempts"]) - 1,
                        _delay,
                        _tool_err,
                    )
                    import asyncio as _asyncio
                    if _delay > 0:
                        await _asyncio.sleep(_delay)
                    try:
                        _retry_exec = await ex.execute(
                            text=draft.text,
                            tool_calls=_bound_calls,
                            stream_callback=stream_callback,
                            progress_callback=progress_callback,
                            agent_role=agent_role or step.agent_role,
                            is_worker=(step.agent_role not in ("orchestrator", "", None)),
                        )
                    except Exception as _re:
                        _tool_err = str(_re)
                        break
                    result.tool_output = (
                        _retry_exec.completed_tools[0]
                        if _retry_exec.completed_tools else None
                    )
                    _tool_err = (
                        result.tool_output.get("error")
                        if result.tool_output and isinstance(result.tool_output, dict)
                        else None
                    )
                if _tool_err:
                    result.error = str(_tool_err)

            # ── Hollow-result honesty (empty research / soft-empty tools) ─
            # Tools that "succeed" with zero evidence must not persist as
            # Finished — that is the same lie as Completed + 0/N pending.
            if not result.error and not result.paused and result.tool_output:
                _hollow = _hollow_tool_message(result.tool_output)
                if _hollow:
                    result.error = _hollow
                    result.critic_verdict = "veto"
                    if "hollow_result" not in result.critic_flags:
                        result.critic_flags.append("hollow_result")
                    logger.info(
                        "ReActLoop: hollow tool result step=%d → failed honestly",
                        step.step_id,
                    )

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
            # If this step already carries a resume confirmation_token (user
            # clicked Approve on the pre-execution critic pause), the staged
            # execution must be confirmed here — do NOT pause again (that
            # loop left the UI stuck on "Needs approval" after Approve).
            if result.tool_output:
                _to = result.tool_output
                _raw = _to.get("result", "")
                try:
                    _parsed = json.loads(_raw) if isinstance(_raw, str) else _raw
                except (json.JSONDecodeError, TypeError):
                    _parsed = {}
                if isinstance(_parsed, dict) and _parsed.get("requires_confirmation"):
                    _exec_id = str(_parsed.get("execution_id") or "").strip()
                    _host = getattr(ex, "executor", None)
                    _confirm_fn = getattr(_host, "confirm_execution", None) if _host else None
                    if confirmation_token and _exec_id and callable(_confirm_fn):
                        try:
                            _committed = await _confirm_fn(
                                _exec_id,
                                expected_host_user_id=host_user_id,
                            )
                            _to = dict(_to)
                            _to["result"] = (
                                _committed
                                if isinstance(_committed, str)
                                else json.dumps(_committed, default=str)
                            )
                            _to["error"] = None
                            _to["confirmed"] = True
                            if isinstance(_committed, dict) and _committed.get("action") == "navigate":
                                _to["action"] = "navigate"
                                _to["route"] = _committed.get("route") or ""
                                _to["label"] = _committed.get("label") or "Open"
                                _to["summary"] = _committed.get("summary") or ""
                            result.tool_output = _to
                            result.executed = True
                            result.paused = False
                            result.error = None
                            result.confirmation_token = confirmation_token
                            # Skip observe — the host receipt is the outcome.
                            # A post-write LLM observe can hang the resume SSE
                            # and leave the step stuck "Running" after a real
                            # write (leave already created; UI never got done).
                            result.draft_text = (
                                (_to.get("summary") or "").strip()
                                or result.draft_text
                                or "Submitted."
                            )
                            logger.info(
                                "ReActLoop: auto-confirmed staged mutation "
                                "step=%d exec=%s (resume token present)",
                                step.step_id, _exec_id[:8],
                            )
                            return result
                        except Exception as _confirm_exc:  # noqa: BLE001
                            # Do NOT pause again — the user already Approved.
                            # Surface the host error (e.g. date overlap) as a
                            # failed step so Approve cannot loop forever.
                            _msg = str(_confirm_exc).strip() or "Confirmation failed"
                            logger.warning(
                                "ReActLoop: auto-confirm failed step=%d exec=%s: %s",
                                step.step_id, _exec_id[:8], _msg,
                            )
                            result.paused = False
                            result.executed = False
                            result.error = _msg
                            result.confirmation_token = confirmation_token
                            result.critic_verdict = "veto"
                            if "auto_confirm_failed" not in result.critic_flags:
                                result.critic_flags.append("auto_confirm_failed")
                            return result
                    else:
                        from uuid import uuid4
                        result.paused = True
                        result.confirmation_token = str(uuid4())
                        result.executed = False
                        result.error = None
                        logger.info(
                            "ReActLoop: consent gate hit step=%d tool=%s token=%s",
                            step.step_id, _to.get("tool_name", "?"),
                            result.confirmation_token[:8],
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
                            if _step_index_context is not None:
                                _step_index_context(step.step_id)
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
                                if _step_index_context is not None:
                                    _step_index_context(None)
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
        # Models often wrap the object in ```json fences — strip before loads
        # so we never persist the raw fence as draft_text / final_response.
        _decision = None
        _candidate = _strip_markdown_fence(text)
        try:
            _decision = json.loads(_candidate)
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
        # Never keep a fenced JSON blob as the operator-facing answer.
        if _candidate != text and _candidate.startswith("{"):
            return None
        if len(text) > 20 and not text.lstrip().startswith("```"):
            return ObservationResult(answer=text, needs_followup=False)
        return None

    @staticmethod
    def _followup_signature(tool_name: str | None, tool_args: dict | None) -> tuple:
        """Stable key for coalescing identical follow-up requests."""
        try:
            args_key = json.dumps(tool_args or {}, sort_keys=True, default=str)
        except (TypeError, ValueError):
            args_key = str(tool_args)
        return (tool_name or "", args_key)

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
        if not (
            result
            and result.followup
            and result.followup.needs_followup
            and result.followup.followup_tool in _ALLOWED_FOLLOWUP_TOOLS
            and followup_steps_used < max_steps
            and followup_steps_used < _MAX_AUTO_FOLLOWUPS
        ):
            return False
        # Never chain off a failed / paused / consent step — that produced the
        # Done-ledger spam of awaiting_approval follow-ups (live QA).
        if result.error or result.paused or result.critic_verdict == "veto":
            return False
        return _followup_is_readonly(
            result.followup.followup_tool,
            result.followup.followup_args,
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

    async def _count_open_steps(self, _db, run_id: str) -> int:
        """Count durable steps that are not terminal (pending/running/awaiting)."""
        from ai.engine.core.models import RunStep

        if _db is None or not run_id:
            return 0
        try:
            rows = await _db.select(RunStep, ("run_id", run_id))
        except Exception:  # noqa: BLE001 — honesty check must never crash finalize
            logger.exception("ReActLoop: open-step count failed run=%s", run_id)
            return 0
        terminal = {"completed", "failed", "skipped"}
        return sum(1 for s in rows if getattr(s, "status", None) not in terminal)

    async def _persist_skipped_step(
        self,
        _db,
        run_id: str,
        step: PlanStep,
        reason: str = "unchosen_branch",
    ) -> None:
        """Persist a RunStep marked skipped (e.g. XOR branch not taken)."""
        from ai.engine.core.models import RunStep, generate_uuid

        existing = first(await _db.select(
            RunStep,
            ("run_id", run_id),
            ("step_index", step.step_id),
        ))
        if existing:
            existing.status = "skipped"
            existing.error = reason
            existing.updated_at = utcnow()
            await _db.commit()
            return
        _db.add(RunStep(
            id=generate_uuid(),
            run_id=run_id,
            step_index=step.step_id,
            intent=step.intent,
            tool_name=step.tool_name,
            tool_args_json=json.dumps(step.tool_args) if step.tool_args else None,
            depends_on_json=json.dumps(step.depends_on) if step.depends_on else None,
            status="skipped",
            error=reason,
        ))
        await _db.commit()

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

    async def _run_is_cancelled(self, _db, run_id: str) -> bool:
        """True when the durable Run was cancelled (operator Stop)."""
        from ai.engine.core.models import Run
        row = first(await _db.select(Run, ("id", run_id)))
        return bool(row and row.status == "cancelled")

    async def _finalize_run(
        self,
        _db,
        run_id: str,
        succeeded: bool,
        final_response: str,
        total_latency_ms: float,
        total_llm_calls: int,
        step_results: list[StepResult],
        total_tokens: int = 0,
        final_status: str | None = None,
    ) -> None:
        """Update the Run row with final status and summary."""
        from ai.engine.core.models import Run

        run_row = first(await _db.select(Run, ("id", run_id)))
        if run_row is None:
            logger.warning("ReActLoop: Run row id=%s not found for finalization", run_id)
            return

        # Never overwrite an operator cancel (or pause) with completed/failed.
        if run_row.status in ("cancelled", "paused"):
            run_row.total_llm_calls = total_llm_calls
            run_row.total_latency_ms = total_latency_ms
            if total_tokens:
                run_row.total_tokens = (run_row.total_tokens or 0) + total_tokens
            run_row.updated_at = utcnow()
            await _db.commit()
            logger.info(
                "ReActLoop: skip finalize status clobber id=%s keep=%s",
                run_id, run_row.status,
            )
            return

        if final_status in ("completed", "completed_with_gaps", "failed"):
            # Never stamp Completed while durable steps are still open.
            if final_status in ("completed", "completed_with_gaps"):
                open_n = await self._count_open_steps(_db, run_id)
                if open_n > 0:
                    logger.error(
                        "ReActLoop: refusing %s with %d open step(s) id=%s",
                        final_status, open_n, run_id,
                    )
                    final_status = "failed"
                    succeeded = False
                    final_response = (
                        "Run ended before steps finished "
                        f"({open_n} still open). Re-approve to retry."
                    )
            run_row.status = final_status
        else:
            run_row.status = "completed" if succeeded else "failed"
            if run_row.status == "completed":
                open_n = await self._count_open_steps(_db, run_id)
                if open_n > 0:
                    run_row.status = "failed"
                    succeeded = False
                    final_response = (
                        "Run ended before steps finished "
                        f"({open_n} still open). Re-approve to retry."
                    )
        run_row.final_response = final_response[:2000] if final_response else None
        run_row.total_llm_calls = total_llm_calls
        run_row.total_latency_ms = total_latency_ms
        if total_tokens:
            run_row.total_tokens = (run_row.total_tokens or 0) + total_tokens
        run_row.completed_at = utcnow()
        await _db.commit()
        logger.debug("ReActLoop: finalized Run row id=%s status=%s", run_id, run_row.status)

    # ── Synthesis ──────────────────────────────────────────────────────────

    @staticmethod
    def _host_actions_markdown(step_results: list[StepResult]) -> str:
        """Collect host navigate receipts for Output (Chat-compatible contract)."""
        from ai.host_receipt import collect_navigate_actions, format_actions_markdown

        outputs = [
            (r.tool_output if isinstance(r.tool_output, dict) else {})
            for r in (step_results or [])
            if not (r.error and not str(r.error).startswith("[caught]"))
        ]
        return format_actions_markdown(collect_navigate_actions(outputs))

    @staticmethod
    def _has_confirmed_host_write(step_results: list[StepResult]) -> bool:
        """True when a step already committed a host mutation with a receipt."""
        for r in step_results or []:
            if r.error and not str(r.error).startswith("[caught]"):
                continue
            out = r.tool_output if isinstance(r.tool_output, dict) else {}
            if out.get("confirmed") and (
                out.get("action") == "navigate" or (out.get("summary") or "").strip()
            ):
                return True
            if out.get("action") == "navigate" and (out.get("route") or "").startswith("/"):
                return True
        return False

    @staticmethod
    def _merge_host_actions_markdown(
        final_response: str | None, host_actions_md: str,
    ) -> str:
        """Append navigate receipts without duplicating summary lines."""
        host = (host_actions_md or "").strip()
        if not host:
            return (final_response or "").strip()[:2000]
        base = (final_response or "").strip()
        if not base:
            return host[:2000]
        # Receipt already present (LLM or fallback copied the summary).
        first_line = host.splitlines()[0].strip() if host else ""
        if first_line and first_line in base:
            # Ensure the deep link exists when only the summary was copied.
            if "](/" not in base and "/my/" not in base:
                link_lines = [
                    ln for ln in host.splitlines()
                    if ln.strip().startswith("[") and "](/" in ln
                ]
                if link_lines:
                    return f"{base}\n\n{link_lines[0]}".strip()[:2000]
            return base[:2000]
        if "/my/" in base or "](/" in base:
            return base[:2000]
        return f"{base}\n\n{host}".strip()[:2000]

    @staticmethod
    def _fallback_final_response(step_results: list[StepResult]) -> str:
        """Operator-facing Answer when LLM synthesis is empty (RULE_23)."""
        from ai.host_receipt import collect_navigate_actions, format_actions_markdown

        outputs = [
            (r.tool_output if isinstance(r.tool_output, dict) else {})
            for r in (step_results or [])
        ]
        actions_md = format_actions_markdown(collect_navigate_actions(outputs))
        leave_submit_done = False
        loan_submit_done = False
        for r in step_results or []:
            if r.error and not str(r.error).startswith("[caught]"):
                continue
            out = r.tool_output if isinstance(r.tool_output, dict) else {}
            layers = [out]
            raw = out.get("result")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    raw = None
            if isinstance(raw, dict):
                layers.append(raw)
                nested = raw.get("data")
                if isinstance(nested, dict):
                    layers.append(nested)
            data = out.get("data") if isinstance(out.get("data"), dict) else {}
            if data:
                layers.append(data)

            api = ""
            args = out.get("tool_args") if isinstance(out.get("tool_args"), dict) else {}
            if isinstance(args, dict):
                api = str(args.get("api_name") or "")

            for layer in layers:
                ctype = str(layer.get("corr_type_code") or "").lower()
                status = str(layer.get("status") or "").lower()
                code = layer.get("status_code")
                try:
                    code_int = int(code) if code is not None else None
                except (TypeError, ValueError):
                    code_int = None
                if api == "submit_my_leave" or ctype == "leave_request":
                    if code_int in (200, 201) or status in (
                        "submitted", "in_review", "approved", "draft",
                    ):
                        leave_submit_done = True
                        break
                if api == "submit_my_loan" or ctype == "loan_request":
                    if code_int in (200, 201) or status in (
                        "submitted", "in_review", "approved", "draft",
                    ):
                        loan_submit_done = True
                        break
                if out.get("confirmed") and ctype == "leave_request":
                    leave_submit_done = True
                    break
                if out.get("confirmed") and ctype == "loan_request":
                    loan_submit_done = True
                    break
            if leave_submit_done or loan_submit_done:
                break
            intent = (r.intent or "").lower()
            if (
                "submit leave" in intent
                and out.get("confirmed")
                and not (r.error and not str(r.error).startswith("[caught]"))
            ):
                leave_submit_done = True
                break
            if (
                "submit loan" in intent
                and out.get("confirmed")
                and not (r.error and not str(r.error).startswith("[caught]"))
            ):
                loan_submit_done = True
                break

        if leave_submit_done:
            head = (
                "Your leave request was submitted. "
                "Your manager reviews it in Team — track status in My Leave."
            )
            if actions_md:
                return f"{head}\n\n{actions_md}".strip()[:2000]
            return head

        if loan_submit_done:
            head = (
                "Your loan request was submitted. "
                "Manager then finance review it in Team — track status in My Requests."
            )
            if actions_md:
                return f"{head}\n\n{actions_md}".strip()[:2000]
            return head

        if actions_md:
            return actions_md

        lines: list[str] = []
        export_names: list[str] = []
        for r in step_results or []:
            intent = (r.intent or f"Step {r.step_id}").strip()
            if r.error and not str(r.error).startswith("[caught]"):
                lines.append(f"- {intent}: did not complete.")
                continue
            lines.append(f"- {intent}: done.")
            out = r.tool_output if isinstance(r.tool_output, dict) else {}
            files = out.get("files") if isinstance(out.get("files"), list) else []
            for f in files:
                if isinstance(f, dict) and f.get("filename"):
                    export_names.append(str(f["filename"]))
            raw = out.get("result")
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    parsed = None
                if isinstance(parsed, dict):
                    for f in parsed.get("files") or []:
                        if isinstance(f, dict) and f.get("filename"):
                            export_names.append(str(f["filename"]))
        head = "The plan finished."
        if export_names:
            uniq = list(dict.fromkeys(export_names))
            head = (
                "The plan finished. Downloadable files are under Artifacts: "
                + ", ".join(uniq[:6])
                + ("…" if len(uniq) > 6 else "")
                + "."
            )
        body = "\n".join(lines[:12])
        return f"{head}\n\n{body}".strip()[:2000]

    async def _synthesise(
        self,
        plan: Plan,
        step_results: list[StepResult],
        user_message: str,
        system_prompt: str,
        step_contexts: dict[int, str],
        instance_id: str = "",
        gap_step_ids: list[int] | None = None,
    ) -> str:
        """Combine step results into a final response using the plan's synthesis_instruction."""
        if len(step_results) == 1 and plan.source == "single_step" and not gap_step_ids:
            return step_results[0].draft_text or ""

        # Build a synthesis prompt
        parts = [f"User asked: {user_message}"]
        parts.append(f"Plan: {plan.pattern} — {plan.synthesis_instruction}")
        parts.append("Step results:")
        for r in step_results:
            caught = bool(r.error and str(r.error).startswith("[caught]"))
            if caught:
                status = "△"
            elif r.critic_verdict in ("pass", "pass_with_flag") and not r.error:
                status = "✓"
            else:
                status = "✗"
            parts.append(f"  [{status}] Step {r.step_id}: {r.intent}")
            if r.draft_text:
                parts.append(f"    Output: {r.draft_text[:500]}")
            if r.error:
                parts.append(f"    Error: {r.error}")

        if gap_step_ids:
            parts.append(
                "Partial completion — gaps at step(s): "
                + ", ".join(str(i) for i in gap_step_ids)
                + ". Report what was delivered and what is missing."
            )

        # If we have an LLM, use it for synthesis; otherwise concatenate
        if self.llm_client is not None and self.model:
            return await self._llm_synthesise("\n".join(parts), system_prompt, instance_id=instance_id)
        else:
            # Simple concatenation fallback
            texts = [r.draft_text for r in step_results if r.draft_text]
            gap_note = ""
            if gap_step_ids:
                gap_note = (
                    "\n\nCompleted with gaps — missing/failed step(s): "
                    + ", ".join(str(i) for i in gap_step_ids) + "."
                )
            if not texts:
                return (
                    "I wasn't able to complete the requested plan. "
                    "Some steps encountered errors."
                    + gap_note
                )
            return "\n\n".join(texts) + gap_note

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
