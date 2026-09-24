"""TurnPipelineRunner — orchestrates the six-witness pipeline for one turn.

BE-01-5: Spine is the default path. Runs S1→S2→S3→S4→S5→S6 sequentially,
writing one TurnLedgerRow per stage. PulseAgent.think() has been deleted.
"""
import logging
import time
import uuid
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.cognition.turn.runner_helpers import (
    _audience_persona,
    _finalize_meter,
    _scoped_api_catalog,
    _scoped_navigation_routes,
    _signal,
)
from ai.engine.cognition.turn.runner_render import _DELIVERY_INJECTION
from ai.engine.cognition.turn.runner_surfaces import SoftSurfacesMixin
from ai.engine.cognition.turn.runner_util import (  # noqa: F401 — re-export for adapters
    _CHAT_STATIC_TOOLS,
    _ECF_CHAT_TOOLS,
    _chat_tool_allowlist,
    _completed_tools_from_react,
    _fanout_skip_reason,
    _filter_draft_tools,
    _is_capability_query,
    _is_declared_in_scope,
    _is_text_transform_request,
)
from ai.engine.cognition.turn.runner_render import (  # noqa: F401 — re-export; bodies moved (L7 runner cut)
    _cell_display,
    _clarify_no_matches,
    _is_distribution_ask,
    _normalize_weather_location,
    _normalize_weather_question,
    _render_tool_charts,
    _render_tool_results_for_synthesis,
    _render_tool_tables,
    _salary_band_buckets,
    _synthesize_tool_results,
    _wants_visual,
)
from ai.engine.cognition.turn.witnesses import TurnLedger

logger = logging.getLogger("pulse.cognition.turn.runner")

# Lazy import — avoids circular dependency with notifier
broadcast_run_event = None


class TurnPipelineRunner(SoftSurfacesMixin):
    """Runs the six-witness pipeline for every turn — the only codepath.

    BE-01-5: PulseAgent.think() has been deleted.
    """

    def __init__(
        self,
        llm_client=None,
        knowledge_store=None,
        memory_manager=None,
        executor=None,
        db=None,              # Store session for S6 ledger writes
        weather_extractor=None,
        envelope_synthesizer=None,
        domain_context_assembler=None,
    ):
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.executor = executor
        self.db = db
        self.weather_extractor = weather_extractor
        self.envelope_synthesizer = envelope_synthesizer
        self.domain_context_assembler = domain_context_assembler
        self._draft_tools: list[dict] | None = None
        if executor is not None:
            try:
                from ai.engine.agent.tools import get_tool_definitions

                allow = _chat_tool_allowlist()
                cfg = getattr(executor, "instance_config", None)
                self._draft_tools = [
                    d for d in get_tool_definitions(cfg)
                    if d.get("function", {}).get("name") in allow
                ]
            except Exception:  # noqa: BLE001 - tools are best-effort, never fatal
                logger.warning("Could not load draft tool definitions", exc_info=True)
                self._draft_tools = None

    def _is_weather_query(self, text: str) -> bool:
        """Host-provided weather detector; ``False`` when not injected (fail-soft)."""
        if self.weather_extractor is None:
            return False
        fn = getattr(self.weather_extractor, "is_weather_query", None)
        if fn is None:
            return False
        try:
            return bool(fn(text))
        except Exception:  # noqa: BLE001 - detector must never crash a turn
            return False

    async def run(self, *args, **kwargs) -> tuple:
        """Execute one turn under a turn-scoped LLM call meter."""
        import inspect

        from ai.engine.llm.call_meter import meter_scope

        turn_args = inspect.signature(self._run_metered).bind_partial(
            *args, **kwargs,
        ).arguments
        state_ctx = await self._load_conversation_state(turn_args)
        with meter_scope() as meter:
            response, ledger = await self._run_metered(
                *args, meter=meter, state_ctx=state_ctx, **kwargs,
            )
        await self._save_conversation_state(state_ctx, turn_args, response, ledger)
        return response, ledger

    async def _load_conversation_state(self, turn_args: dict):
        from ai.engine.cognition.state_store import (
            ConversationState,
            ConversationStateStore,
            TurnStateContext,
            seed_working_memory,
        )

        conversation_id = turn_args.get("conversation_id") or ""
        try:
            state = await ConversationStateStore(self.db).load(
                turn_args.get("instance_id") or "",
                conversation_id,
                turn_args.get("host_user_id"),
                scope=turn_args.get("scope"),
            )
        except Exception:  # noqa: BLE001 — state must never block a turn
            logger.warning(
                "ConversationState load failed conv=%s", conversation_id[:8],
                exc_info=True,
            )
            state = ConversationState()
        try:
            from ai.engine.memory.working import get_working_memory

            seed_working_memory(get_working_memory(), conversation_id, state)
        except Exception:  # noqa: BLE001
            logger.debug("working-memory seed skipped", exc_info=True)
        return TurnStateContext(state=state)

    async def _save_conversation_state(self, state_ctx, turn_args: dict, response, ledger) -> None:
        from ai.engine.cognition.state_store import (
            ConversationStateStore,
            update_state_from_turn,
        )

        conversation_id = turn_args.get("conversation_id") or ""
        try:
            from ai.engine.memory.working import get_working_memory

            execution = getattr(ledger, "execution", None)
            draft = getattr(ledger, "draft", None)
            state = update_state_from_turn(
                state_ctx.state,
                decision=ledger.turn_decision,
                user_message=turn_args.get("user_message") or "",
                response_text=getattr(response, "text", "") or "",
                fired_gates=[
                    s.get("gate") for s in (ledger.decision_signals or []) if s.get("fired")
                ],
                intent=state_ctx.intent,
                completed_tools=getattr(execution, "completed_tools", None),
                draft_tool_calls=getattr(draft, "tool_calls", None),
                focus_stack=get_working_memory().get_focus_stack(conversation_id),
                scope=turn_args.get("scope"),
                arbiter_shadow=getattr(ledger, "arbiter_shadow", None),
                open_question=getattr(response, "open_question", None),
            )
            try:
                ledger.active_plans = list(state.active_plans or [])
            except Exception:  # noqa: BLE001
                ledger.active_plans = []
            ledger.state_saved = await ConversationStateStore(self.db).save(
                turn_args.get("instance_id") or "",
                conversation_id,
                turn_args.get("host_user_id"),
                state,
            )
            ledger.state_size = state.size()
        except Exception:  # noqa: BLE001 — state must never fail a turn
            logger.warning(
                "ConversationState save failed conv=%s", conversation_id[:8],
                exc_info=True,
            )

    async def _run_metered(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None = None,
        process_mode: str = "ask",
        page_context: str = "",
        conversation_history: list[dict] | None = None,
        instance_config: dict | None = None,
        user_info: dict | None = None,
        progress_callback=None,
        stream_callback=None,
        model: str | None = None,
        temperature: float | None = None,
        knowledge_items: list | None = None,
        scope: dict | None = None,
        process_state: dict | None = None,
        *,
        meter=None,
        state_ctx=None,
    ) -> tuple:
        """Execute one turn. Returns (AgentResponse, TurnLedger)."""
        from ai.engine.cognition.turn.executor import StagedExit
        from ai.engine.cognition.turn.router import TurnRouter

        settings = get_settings()
        original_user_message = user_message
        state = getattr(state_ctx, "state", None) if state_ctx is not None else None
        turn_route = TurnRouter().decide(
            message=user_message,
            process_mode=process_mode,
            state=state,
            history=conversation_history,
            last_results=getattr(state, "last_results", None) if state is not None else None,
        )
        user_message = turn_route.message

        excluded_tools = set((instance_config or {}).get("excluded_tools") or [])
        if excluded_tools and self._draft_tools is not None:
            self._draft_tools = [
                d for d in self._draft_tools
                if d.get("function", {}).get("name") not in excluded_tools
            ]

        turn_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        t0 = time.monotonic()

        ledger = TurnLedger(
            turn_id=turn_id,
            instance_id=instance_id,
            host_user_id=host_user_id,
            conversation_id=conversation_id,
            user_message=original_user_message,
            created_at=created_at,
            decision_committed=turn_route.committed,
            route_kind=turn_route.kind.value,
            process_mode=turn_route.mode.value,
        )
        staged: list[StagedExit] = []

        from ai.engine.agent.budget import BudgetTracker

        budget = None
        if self.db is not None:
            budget = BudgetTracker(
                run_id=turn_id,
                total_budget=settings.RUN_TOKEN_BUDGET_DEFAULT,
                db_session=self.db,
            )

        logger.info(f"[{turn_id[:8]}] Pipeline start  user={host_user_id}'")

        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        await _broadcast_run(instance_id, "run.started", {
            "run_id": turn_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "user_message": user_message,
        })

        from ai.engine.cognition.turn.runner_metered_state import MeteredTurnState
        from ai.engine.cognition.turn.runner_pre_s1 import run_pre_s1_gates
        from ai.engine.cognition.turn.runner_s1 import run_s1_intent
        from ai.engine.cognition.turn.runner_s2_plan import run_s2_and_plan_gates
        from ai.engine.cognition.turn.runner_s3_s5 import run_s3_through_s5
        from ai.engine.cognition.turn.runner_s6 import run_s6_finalize

        # Resolve *where this turn runs* exactly once, from the router's parsed
        # dial. Every stage and guardrail reads this value; nothing downstream
        # re-derives it from prose or defaults to Chat on its own.
        from ai.engine.agent.surface import Surface

        surface = Surface.resolve(
            process_mode=turn_route.mode.value,
            user_message=original_user_message,
        )

        st = MeteredTurnState(user_message=user_message)
        _stage_kw = dict(
            instance_id=instance_id,
            conversation_id=conversation_id,
            host_user_id=host_user_id,
            process_mode=process_mode,
            surface=surface,
            page_context=page_context,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            progress_callback=progress_callback,
            stream_callback=stream_callback,
            model=model,
            temperature=temperature,
            knowledge_items=knowledge_items,
            scope=scope,
            process_state=process_state,
            meter=meter,
            state_ctx=state_ctx,
            budget=budget,
            turn_id=turn_id,
            t0=t0,
            ledger=ledger,
            staged=staged,
            settings=settings,
            turn_route=turn_route,
            original_user_message=original_user_message,
            state=state,
            _broadcast_run=_broadcast_run,
        )

        early = await run_pre_s1_gates(self, st, **_stage_kw)
        if early is not None:
            return early

        early = await run_s1_intent(self, st, **_stage_kw)
        if early is not None:
            return early

        early = await run_s2_and_plan_gates(self, st, **_stage_kw)
        if early is not None:
            return early

        await run_s3_through_s5(self, st, **_stage_kw)
        return await run_s6_finalize(self, st, **_stage_kw)

    async def _write_ledger_row(
        self, turn_id, instance_id, conversation_id, host_user_id,
        stage, stage_index, payload, latency_ms,
        tokens_used=None, model_used=None, verdict=None, flags=None,
    ):
        """Write one row to turn_ledger via the LedgerWitness."""
        from ai.engine.cognition.turn.ledger import LedgerWitness

        ledger_witness = LedgerWitness()
        await ledger_witness.record_stage(
            db=self.db,
            turn_id=turn_id,
            instance_id=instance_id,
            conversation_id=conversation_id,
            host_user_id=host_user_id,
            stage=stage,
            stage_index=stage_index,
            payload=payload,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            model_used=model_used,
            verdict=verdict,
            flags=flags,
        )

