"""Soft surfaces extracted from TurnPipelineRunner (ADR-0049 Q4 / L7).

Keeps legacy soft-gate behaviour; moves weight out of ``runner.py`` so the
harness ``runner_lines`` meter can fall without a behaviour change.
"""
from __future__ import annotations

import logging
import time

from ai.engine.cognition.turn.runner_helpers import (
    _audience_persona,
    _finalize_meter,
    _scoped_api_catalog,
    _scoped_navigation_routes,
    _signal,
    get_settings,
)
from ai.engine.cognition.turn.runner_render import _DELIVERY_INJECTION

logger = logging.getLogger("pulse.cognition.turn.runner_surfaces")


def _navigation_actions(nav) -> list[dict]:
    """Machine-readable navigate actions for a resolved NavigationResolution."""
    return [
        {
            "type": "navigate",
            "route": t.route,
            "label": t.label,
            "summary": f"Open {t.label}",
        }
        for t in nav.targets
    ]


def _navigation_text(nav) -> str:
    """Propose→confirm copy for a resolved navigation (EN/AR)."""
    ar = nav.lang == "ar"
    if nav.action == "navigate":
        label = nav.targets[0].label
        return (
            f"هل تريد فتح **{label}**؟" if ar
            else f"Would you like to open **{label}**?"
        )
    return (
        "عدة أماكن تطابق طلبك — اختر الوجهة المطلوبة:" if ar
        else "A few places match — which would you like to open?"
    )


def _navigation_response(nav, *, total_tokens=0, total_llm_calls=0):
    """Build the propose→confirm AgentResponse for a resolved navigation."""
    from ai.engine.agent.reasoning import AgentResponse
    return AgentResponse(
        text=_navigation_text(nav),
        sources_cited=[],
        tools_used=[],
        confidence=1.0,
        total_tokens=total_tokens,
        llm_calls=total_llm_calls,
        model="",
        response_type="inferred",
        actions=_navigation_actions(nav),
    )


class SoftSurfacesMixin:
    """Mixin: soft / understand / ESS / handoff helpers for TurnPipelineRunner."""

    async def _try_pulse_loop(
        self,
        instance_id,
        conversation_id,
        user_message,
        host_user_id,
        page_context,
        conversation_history,
        instance_config,
        user_info,
        retrieval,
        progress_callback,
        stream_callback,
        turn_id,
        intent_resolution=None,
        state_ctx=None,
    ):
        """Pulse v2 Phase 1: run the adaptive ReAct loop for tool-bearing turns.

        Builds a single-step plan by hand (no SkillAwarePlanner / decompose) and
        hands it to ReActLoop, whose ``_observe`` stage synthesizes a grounded
        answer from the executed tool result. Returns ReActResult or None (None
        means "fall through to single-pass S3→S5").
        """
        try:
            from ai.engine.cognition.plan.planner import Plan, PlanStep, PlanPhase
            from ai.engine.cognition.plan.loop import ReActLoop
            from ai.engine.cognition.turn.draft import DraftWitness
            from ai.engine.cognition.turn.critic import CriticWitness
            from ai.engine.llm.prompts import build_chat_prompt

            # Hand-built single-step plan — the tool wiring in _execute_step
            # keys off plan_source == "single_step".
            from ai.engine.agent.tools import (
                extract_named_coworker_query,
                first_person_profile_ask,
            )

            _profile_bound = bool(
                host_user_id and first_person_profile_ask(user_message)
            )
            _coworker_q = (
                extract_named_coworker_query(user_message)
                if host_user_id and not _profile_bound
                else None
            )
            if _profile_bound:
                _step_tool, _step_args = "call_host_api", {
                    "api_name": "get_my_profile",
                    "explanation": (
                        "First-person identity is the logged-in "
                        "employee record"
                    ),
                }
            elif _coworker_q:
                _step_tool, _step_args = "resolve_entity", {
                    "entity_type": "employee",
                    "query": _coworker_q,
                    "explanation": "Named coworker lookup",
                }
            else:
                _step_tool, _step_args = None, {}
            plan = Plan(
                pattern="single_step",
                steps=[PlanStep(
                    step_id=0,
                    intent=user_message,
                    tool_name=_step_tool,
                    tool_args=_step_args,
                    depends_on=[],
                    is_mutation=False,
                    agent_role="orchestrator",
                )],
                synthesis_instruction="Answer the user directly using any tool results.",
                source="single_step",
                phases=[PlanPhase(
                    phase_id=0,
                    name="main",
                    strategy="sequential",
                    step_ids=[0],
                )],
            )

            # Build system prompt — LLM-synthesized (mirrors _try_multi_step_plan).
            config = instance_config or {}
            system_prompt = await build_chat_prompt(
                instance_name=config.get("display_name", "Unknown System"),
                system_description=config.get("description", ""),
                relevant_knowledge=(
                    retrieval.knowledge_chunks[0]["content"]
                    if retrieval.knowledge_chunks else "No knowledge loaded yet."
                ),
                relevant_memories=(
                    retrieval.memory_chunks[0]["content"]
                    if retrieval.memory_chunks else "No memories available."
                ),
                page_context=page_context or "unknown",
                user_info=user_info,
                persona=_audience_persona(config, user_info),
                api_catalog=_scoped_api_catalog(config, user_info),
                navigation_routes=_scoped_navigation_routes(config, user_info),
                domain_topics=config.get("domain_topics"),
                instance_config={
                    **config,
                    "persona": _audience_persona(config, user_info),
                    "api_catalog": _scoped_api_catalog(config, user_info),
                },
                conversation_id=conversation_id,
                instance_id=instance_id,
            )

            # N7 / SIM-20260919-N7: mirror single-pass S1.5 INTENT injection so
            # Pulse loop Chat does not stop after resolve_entity on named leave.
            if (
                intent_resolution is not None
                and intent_resolution.action == "answer"
                and intent_resolution.candidates
            ):
                from ai.engine.cognition.turn.intent import _endpoint_to_domain_phrase
                _top_cand = intent_resolution.candidates[0]
                _phrases = [
                    _endpoint_to_domain_phrase(c.name)
                    for c in intent_resolution.candidates[:3]
                ]
                _delivery_phrase = _DELIVERY_INJECTION.get(
                    intent_resolution.delivery, _DELIVERY_INJECTION["explain"]
                )
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "INTENT (already recognised): the user is asking about "
                    f"\"{_phrases[0]}\" and wants to {_delivery_phrase}. The "
                    f"intent resolver matched `{_top_cand.name}` with confidence "
                    f"{_top_cand.confidence:.2f}. Call `{_top_cand.name}` via "
                    "call_host_api right away to answer from real data in the "
                    "system — do NOT give a generic or textbook answer, and do "
                    "NOT re-ask what the user means. Synthesise the result into a "
                    "direct answer: do not dump the raw rows, name the material "
                    "facts and cite real values inline, and only render a table "
                    "if the user asked to see everything."
                )

            draft_witness = DraftWitness(
                llm_client=self.llm_client,
                knowledge_store=self.knowledge_store,
                memory_manager=self.memory_manager,
                executor=self.executor,
            )
            critic_witness = CriticWitness()

            loop = ReActLoop(
                draft_witness=draft_witness,
                critic_witness=critic_witness,
                llm_client=self.llm_client,
                knowledge_store=self.knowledge_store,
                memory_manager=self.memory_manager,
                db=self.db,
            )

            react_result = await loop.run(
                plan=plan,
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
                host_user_id=host_user_id,
                conversation_state=(
                    state_ctx.state if state_ctx is not None else None
                ),
            )

            # Only claim the pulse-loop path when a tool actually executed
            # successfully (tool_output is non-empty); otherwise fall back to
            # single-pass S3→S5. NOTE: ``sr.executed`` is True even when the
            # draft selected zero tools (it only records that the execute
            # witness ran), so it is NOT a reliable "tool was used" signal.
            if not any(
                sr.tool_output and not sr.error for sr in react_result.step_results
            ):
                logger.debug(
                    "TurnPipelineRunner: pulse loop ran no successful tool step; "
                    "falling back to single-pass"
                )
                return None

            return react_result
        except Exception:  # noqa: BLE001 - pulse loop is best-effort, never fatal
            logger.exception(
                "[%s] Pulse loop attempt failed; falling back to single-pass",
                turn_id[:8],
            )
            return None

    async def _try_plan_status_answer(
        self,
        *,
        user_message: str,
        state_ctx,
        ledger,
        meter,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        host_user_id: str | None,
        t0: float,
    ):
        """PV2-5B: status-of-my-request from active_plans / slots — 0 LLM."""
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        from ai.engine.cognition.turn.plan_status import (
            can_answer_plan_status,
            is_plan_status_utterance,
            render_plan_status,
        )

        state = getattr(state_ctx, "state", None) if state_ctx is not None else None
        if not is_plan_status_utterance(user_message):
            return None
        if not can_answer_plan_status(state):
            return None
        text = render_plan_status(state, user_message)
        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = (text or "")[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = 0
        ledger.total_llm_calls = 0
        response = AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[],
            confidence=1.0,
            total_tokens=0,
            llm_calls=0,
            model="",
            response_type="inferred",
        )
        try:
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_llm_calls": 0,
                "plan_status": True,
            })
        except Exception:  # noqa: BLE001
            logger.debug("plan_status broadcast skipped", exc_info=True)
        _signal(ledger, "plan_status", True)
        ledger.turn_decision = ledger.turn_decision or "answer"
        return response, ledger

    async def _try_next_step_offer(
        self,
        *,
        user_message: str,
        state_ctx,
        ledger,
        meter,
        turn_id: str,
        instance_id: str,
        t0: float,
    ):
        """L4: next ESS verb from state — 0 LLM. Chat never submits."""
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        from ai.engine.cognition.turn.next_step import (
            render_next_step_offer,
            should_offer_next_step,
        )

        state = getattr(state_ctx, "state", None) if state_ctx is not None else None
        if not should_offer_next_step(user_message, state):
            return None
        text = render_next_step_offer(state, user_message)
        if not text:
            return None
        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = 0
        ledger.total_llm_calls = 0
        response = AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[],
            confidence=1.0,
            total_tokens=0,
            llm_calls=0,
            model="",
            response_type="inferred",
        )
        try:
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_llm_calls": 0,
                "next_step": True,
            })
        except Exception:  # noqa: BLE001
            logger.debug("next_step broadcast skipped", exc_info=True)
        _signal(ledger, "next_step", True)
        ledger.turn_decision = ledger.turn_decision or "answer"
        return response, ledger

    async def _try_v21_understand(
        self,
        *,
        user_message: str,
        conversation_history,
        ledger,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        host_user_id: str | None,
        instance_config: dict | None,
        t0: float,
        surface=None,
        state_ctx=None,
        user_info=None,
        process_mode: str = "",
    ):
        """Understand path. ``legacy`` skip; ``shadow`` log+fallthrough; ``v21`` act."""
        from types import SimpleNamespace

        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.agent.guardrails import build_default_pipeline
        from ai.engine.cognition.turn.execute import ExecuteWitness
        from ai.engine.cognition.turn.ess_read import build_ess_self_tool_call
        from ai.engine.cognition.turn.pipeline_v21 import act_on_decision, render_envelope
        from ai.engine.cognition.turn.understand import (
            build_understand_system_prompt,
            catalog_context,
            catalog_prompt_lines,
            navigation_prompt_lines,
            understand_mode,
            understand_turn,
        )
        from ai.engine.llm.router import route_chat

        mode = understand_mode()
        if mode == "legacy":
            return None

        # Plan drafts a reviewable task. A v21 exit here answers or hands off
        # instead, so the plan is never shown and no task is ever created.
        from ai.engine.agent.surface import Surface
        if Surface.resolve(
            surface, process_mode=process_mode, user_message=user_message or "",
        ) is Surface.CHAT_PLAN:
            _signal(ledger, "v21_understand", False, reason="plan_dial")
            return None

        state = getattr(state_ctx, "state", None) if state_ctx is not None else None
        # Write twins are described (Agent-only) so their not_for can route;
        # validate_decision downgrades any write call_tool to handoff_agent.
        scoped_catalog = _scoped_api_catalog(instance_config, user_info)
        lines, allowed, write_names = catalog_prompt_lines(
            user_message or "",
            scoped_catalog,
            k=12,
            context=catalog_context(conversation_history),
        )
        nav_lines = navigation_prompt_lines(
            _scoped_navigation_routes(instance_config, user_info)
        )
        cfg = dict(instance_config or {})
        if user_info is not None:
            cfg = {
                **cfg,
                "persona": _audience_persona(cfg, user_info),
            }
        system = build_understand_system_prompt(
            catalog_lines=lines,
            navigation_lines=nav_lines,
            state=state,
            user_info=user_info,
            instance_config=cfg or None,
        )
        messages = [{"role": "system", "content": system}]
        if conversation_history:
            messages.extend(list(conversation_history)[-8:])
        messages.append({"role": "user", "content": user_message or ""})

        async def complete(*, messages, tools, tool_choice, strict_tools):
            from ai.engine.llm.call_meter import stage

            with stage("understand"):
                return await route_chat(
                    task="cognition",
                    instance_id=instance_id,
                    conversation_id=f"understand-{conversation_id}",
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    strict_tools=strict_tools,
                    temperature=0.0,
                )

        try:
            decision = await understand_turn(
                complete=complete,
                messages=messages,
                catalog_tools=scoped_catalog,
                surface=surface,
                allowed_tools=allowed or None,
                write_tools=write_names or None,
                state=state,
            )
        except Exception:  # noqa: BLE001 — legacy spine remains
            logger.warning("v21 understand failed", exc_info=True)
            _signal(ledger, "v21_understand", False, reason="understand_error")
            return None
        if decision is None:
            _signal(ledger, "v21_understand", False, reason="malformed_decision")
            return None

        try:
            from ai.engine.cognition.turn.arbiter import shadow_understand

            shadow_understand(getattr(ledger, "turn_decision", None) or "answer", decision)
        except Exception:  # noqa: BLE001
            logger.debug("understand-shadow skipped", exc_info=True)

        if mode == "shadow":
            _signal(ledger, "v21_understand", False, reason="shadow_only")
            return None

        async def execute_tool(name: str, args: dict):
            del args  # host GET identity is the api name; the session is the caller
            witness = ExecuteWitness(
                executor=self.executor,
                hook_pipeline=build_default_pipeline(),
                hook_ctx_defaults={
                    "instance_id": instance_id,
                    "conversation_id": conversation_id,
                    "host_user_id": host_user_id,
                    "run_id": turn_id,
                    "agent_role": "orchestrator",
                    "is_worker": False,
                    "instance_config": instance_config,
                    "user_message": user_message,
                    "surface": surface,
                },
                run_id=turn_id,
                instance_id=instance_id,
                knowledge_store=self.knowledge_store,
            )
            execution = await witness.execute(
                text="",
                tool_calls=[build_ess_self_tool_call(name, turn_id)],
                stream_callback=None,
                progress_callback=None,
            )
            completed = list(getattr(execution, "completed_tools", None) or [])
            if completed and isinstance(completed[0], dict):
                return completed[0].get("result")
            return None

        executed: list[dict] = []
        try:
            text = await act_on_decision(
                decision,
                execute_tool=execute_tool,
                user_message=user_message or "",
                state=state,
                executed=executed,
                surface=surface,
            )
        except Exception:  # noqa: BLE001
            logger.warning("v21 act failed", exc_info=True)
            _signal(ledger, "v21_understand", False, reason="act_error")
            return None
        if not (text or "").strip():
            # Plan and Agent already own a multi-step goal. The canned
            # "switch" sentence is None there so the planner can draft it.
            _signal(ledger, "v21_understand", False, reason="fallthrough")
            return None

        handoff_actions: list[dict] = []
        cmd0 = decision.commands[0]
        if cmd0.op == "handoff_agent" and str(cmd0.process_id or "") == "plan":
            from ai.engine.agent.chat_surface import build_plan_mode_switch_handoff

            switch = build_plan_mode_switch_handoff(
                user_message=user_message or "", surface=surface,
            )
            handoff_actions = list(switch.get("actions") or [])

        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = text[:500]
        ledger.total_latency_ms = total_latency
        ledger.turn_decision = decision.commands[0].op if decision.commands else "answer"
        from ai.engine.llm.call_meter import current_meter

        _finalize_meter(ledger, current_meter(), ledger.turn_decision)
        if executed:
            ledger.execution = SimpleNamespace(completed_tools=list(executed))
        envelope = render_envelope(
            decision,
            executed,
            headline=text,
            user_message=user_message or "",
        )
        _signal(
            ledger,
            "v21_understand",
            True,
            op=ledger.turn_decision,
            ops=[c.op for c in decision.commands],
            validated=True,
            render=decision.commands[0].render if decision.commands else "text",
        )
        return AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[
                {"name": "call_host_api", "api_name": (row.get("tool_args") or {}).get("api_name")}
                for row in executed
            ],
            confidence=decision.confidence,
            total_tokens=0,
            llm_calls=1,
            model="",
            response_type="inferred",
            envelope=envelope,
            actions=handoff_actions,
        ), ledger

    async def _try_bound_ess_self_read(
        self,
        *,
        user_message: str,
        conversation_history,
        state_ctx,
        ledger,
        meter,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        host_user_id: str | None,
        instance_config: dict | None,
        t0: float,
        surface=None,
    ):
        """Bound ESS self-read: classify → call_host_api → 0-LLM restate.

        Draft never decides tool_calls. Writes stay on Chat handoff (ADR-0046).
        """
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.agent.guardrails import build_default_pipeline
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        from ai.engine.cognition.turn.ess_read import (
            answer_bound_ess_tools,
            bound_ess_self_api,
            build_ess_self_tool_call,
        )
        from ai.engine.cognition.turn.execute import ExecuteWitness
        from ai.engine.cognition.turn.handoff_agent import is_ess_write_utterance

        if is_ess_write_utterance(user_message or ""):
            _signal(ledger, "ess_bound_self_read", False, reason="ess_write")
            return None

        _prior_api = None
        _state = getattr(state_ctx, "state", None)
        if _state is not None:
            _prior_api = (getattr(_state, "intent", None) or {}).get("api")
        api = bound_ess_self_api(
            user_message,
            history=conversation_history,
            prior_api=_prior_api,
        )
        if not api:
            _signal(ledger, "ess_bound_self_read", False)
            return None

        tool_call = build_ess_self_tool_call(api, turn_id)
        hook_pipeline = build_default_pipeline()
        hook_ctx_defaults = {
            "instance_id": instance_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "run_id": turn_id,
            "agent_role": "orchestrator",
            "is_worker": False,
            "instance_config": instance_config,
            "user_message": user_message,
            "surface": surface,
        }
        execute_witness = ExecuteWitness(
            executor=self.executor,
            hook_pipeline=hook_pipeline,
            hook_ctx_defaults=hook_ctx_defaults,
            run_id=turn_id,
            instance_id=instance_id,
            knowledge_store=self.knowledge_store,
        )
        try:
            execution = await execute_witness.execute(
                text="",
                tool_calls=[tool_call],
                stream_callback=None,
                progress_callback=None,
            )
        except Exception:  # noqa: BLE001 — fall through to draft spine
            logger.warning("bound ESS self-read execute failed", exc_info=True)
            _signal(ledger, "ess_bound_self_read", False, reason="execute_error")
            return None

        completed = list(getattr(execution, "completed_tools", None) or [])
        text = answer_bound_ess_tools(
            completed,
            api_name=api,
            user_message=user_message or "",
        )
        if not (text or "").strip():
            _signal(ledger, "ess_bound_self_read", False, reason="empty_answer")
            return None

        # Seed last_results so follow-ups see the bound API, not a sibling list.
        if state_ctx is not None and getattr(state_ctx, "state", None) is not None:
            try:
                rows = list(state_ctx.state.last_results or [])
                digest = f"call_host_api {api}"
                for item in completed:
                    if isinstance(item, dict) and item.get("result") is not None:
                        raw = item.get("result")
                        if isinstance(raw, dict) and raw.get("count") is not None:
                            digest = f"call_host_api {api}: count={raw.get('count')}"
                        elif isinstance(raw, list):
                            digest = f"call_host_api {api}: count={len(raw)}"
                        break
                stored = None
                for item in completed:
                    if isinstance(item, dict) and isinstance(item.get("result"), (dict, list)):
                        stored = item.get("result")
                        break
                rows.append({
                    "tool": "call_host_api",
                    "api": api,
                    "digest": digest,
                    **({"result": stored} if stored is not None else {}),
                })
                state_ctx.state.last_results = rows
            except Exception:  # noqa: BLE001
                logger.debug("bound ESS last_results seed skipped", exc_info=True)

        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = 0
        ledger.total_llm_calls = 0
        ledger.execution = execution
        from ai.engine.cognition.turn.pipeline_v21 import rows_envelope
        from ai.engine.cognition.turn.runner_render import _wants_visual

        response = AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[{"name": "call_host_api", "api_name": api}],
            confidence=1.0,
            total_tokens=0,
            llm_calls=0,
            model="",
            response_type="inferred",
            # The bound api is the subject; a chart may draw from it alone.
            envelope=rows_envelope(
                completed,
                render="chart" if _wants_visual(user_message or "") else "text",
                headline=text,
                user_message=user_message or "",
            ),
        )
        try:
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_llm_calls": 0,
                "ess_bound_api": api,
            })
        except Exception:  # noqa: BLE001
            logger.debug("bound ESS broadcast skipped", exc_info=True)
        _signal(ledger, "ess_bound_self_read", True, api=api)
        ledger.turn_decision = ledger.turn_decision or "tool_answer"
        logger.info(
            "[ESS-BOUND] api=%s conv=%s text_len=%d",
            api,
            (conversation_id or "")[:8],
            len(text),
        )
        return response, ledger

    async def _try_zero_llm_surface(
        self,
        *,
        user_message: str,
        state_ctx=None,
        conversation_history=None,
        ledger,
        meter,
        turn_id: str,
        instance_id: str,
        t0: float,
    ):
        """C8/C10: thanks / clock / FAQ / stated-fact recall — 0 LLM."""
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        from ai.engine.cognition.turn.memory_recall import (
            extract_stated_facts,
            facts_from_state,
            remember_facts,
        )
        from ai.engine.cognition.turn.zero_llm import try_zero_llm_answer

        state = getattr(state_ctx, "state", None) if state_ctx is not None else None
        newly = extract_stated_facts(user_message)
        if newly and state is not None:
            remember_facts(state, newly)
        known = facts_from_state(state)
        hit = try_zero_llm_answer(
            user_message,
            facts=known,
            history=conversation_history,
            newly_stored=bool(newly),
            last_results=getattr(state, "last_results", None) if state is not None else None,
            open_question=getattr(state, "open_question", None) if state is not None else None,
        )
        if hit is None:
            return None
        text = str(hit.get("text") or "")
        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = 0
        ledger.total_llm_calls = 0
        response = AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[],
            confidence=1.0,
            total_tokens=0,
            llm_calls=0,
            model="",
            response_type=(
                "clarification"
                if str(hit.get("decision") or "") == "clarify"
                else "inferred"
            ),
        )
        try:
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_llm_calls": 0,
                "zero_llm": hit.get("gate"),
            })
        except Exception:  # noqa: BLE001
            logger.debug("zero_llm broadcast skipped", exc_info=True)
        _signal(ledger, str(hit.get("gate") or "zero_llm"), True)
        if str(hit.get("decision") or "") == "clarify":
            ledger.turn_decision = "clarify"
        else:
            ledger.turn_decision = ledger.turn_decision or "answer"
        return response, ledger

    async def _try_plan_dial_process_plan(
        self,
        *,
        user_message: str,
        process_mode: str,
        state_ctx,
        ledger,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        host_user_id: str | None,
        t0: float,
    ):
        """Plan dial + personal ESS brief → process-dial plan, 0 draft LLM.

        Drafts only (RULE_21): the plan lands in ``pending_approval``; nothing
        is submitted here. Answer + Open-in-Tasks action in the user's language.
        """
        from asgiref.sync import sync_to_async

        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        from ai.engine.cognition.turn.navigation import detect_lang
        from ai.engine.cognition.turn.plan_dial import (
            open_tasks_action,
            plan_dial_process_brief,
            render_plan_dial_answer,
        )

        brief = plan_dial_process_brief(
            user_message, process_mode=process_mode,
        )
        if not brief or not host_user_id:
            return None
        # A bare slot answer to an open Chat clarify stays with the slot-filler.
        state = getattr(state_ctx, "state", None) if state_ctx is not None else None
        if state is not None:
            decisions = getattr(state, "decisions", None) or []
            last = decisions[-1] if decisions and isinstance(decisions[-1], dict) else {}
            prior_api = str((getattr(state, "intent", None) or {}).get("api") or "")
            if prior_api and str(last.get("decision") or "") == "clarify" and len(brief) < 40:
                return None

        def _create_plan_sync():
            from django.contrib.auth import get_user_model

            from ai.plans_service import PlansService

            User = get_user_model()
            try:
                user = User.objects.get(pk=host_user_id)
            except (User.DoesNotExist, ValueError):
                return None
            return PlansService().create_plan(
                user, brief, conversation_id=conversation_id or "",
            )

        try:
            # thread_sensitive=False: create_plan re-enters the async engine
            # (same reason as the plan_task plugin).
            plan = await sync_to_async(_create_plan_sync, thread_sensitive=False)()
        except Exception:  # noqa: BLE001 — never break the turn
            logger.warning("plan_dial process plan create failed", exc_info=True)
            return None
        if not isinstance(plan, dict) or not plan.get("id"):
            return None

        lang = "ar" if detect_lang(brief) == "ar" else "en"
        text = render_plan_dial_answer(brief=brief, plan=plan, lang=lang)
        plan_id = str(plan.get("id") or "")

        if state is not None:
            try:
                from ai.engine.cognition.state_store import upsert_active_plan

                upsert_active_plan(
                    state,
                    plan_id=plan_id,
                    status=str(plan.get("status") or "pending_approval"),
                    title=brief[:80],
                    step_summary="; ".join(
                        str(s.get("intent") or "")
                        for s in (plan.get("steps") or [])
                        if isinstance(s, dict)
                    ),
                )
            except Exception:  # noqa: BLE001
                logger.debug("plan_dial active_plans write-back skipped", exc_info=True)

        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = 0
        ledger.total_llm_calls = 0
        response = AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[],
            confidence=1.0,
            total_tokens=0,
            llm_calls=0,
            model="",
            response_type="inferred",
            actions=[open_tasks_action(plan_id, lang)],
        )
        try:
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_llm_calls": 0,
                "plan_dial_process": plan_id,
            })
        except Exception:  # noqa: BLE001
            logger.debug("plan_dial broadcast skipped", exc_info=True)
        logger.info(
            "TurnPipelineRunner: Plan dial process plan id=%s steps=%d lang=%s",
            plan_id[:8], len(plan.get("steps") or []), lang,
        )
        _signal(ledger, "plan_dial_process", True, plan_id=plan_id)
        ledger.turn_decision = ledger.turn_decision or "tool_answer"
        return response, ledger

    async def _try_restyle_previous_answer(
        self,
        *,
        user_message: str,
        conversation_history,
        ledger,
        meter,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        t0: float,
    ):
        """«in arabic / more details» → rewrite the last answer. One LLM, no tools."""
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        from ai.engine.cognition.turn.plan_dial import (
            build_restyle_messages,
            is_restyle_request,
            last_assistant_answer,
            restyle_target_lang,
            restyle_wants_more_detail,
        )
        from ai.engine.llm.call_meter import stage as _stage

        if not is_restyle_request(user_message):
            return None
        previous = last_assistant_answer(conversation_history)
        if not previous:
            return None
        target = restyle_target_lang(user_message)
        messages = build_restyle_messages(
            previous_answer=previous[:6000],
            request=user_message,
            target_lang=target,
            more_detail=restyle_wants_more_detail(user_message),
        )
        try:
            from ai.engine.llm.router import route_chat

            with _stage("restyle"):
                result = await route_chat(
                    task="cognition",
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    messages=messages,
                    temperature=0.2,
                    tools=None,
                )
        except Exception:  # noqa: BLE001 — fall through to the normal spine
            logger.warning("restyle LLM call failed", exc_info=True)
            return None
        text = str((result or {}).get("content") or "").strip()
        if not text:
            return None
        total_latency = (time.monotonic() - t0) * 1000
        ledger.final_response = text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_llm_calls = 1
        response = AgentResponse(
            text=text,
            sources_cited=[],
            tools_used=[],
            confidence=0.9,
            total_tokens=int((result or {}).get("total_tokens") or 0),
            llm_calls=1,
            model=str((result or {}).get("model") or ""),
            response_type="inferred",
        )
        try:
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_llm_calls": 1,
                "restyle": target,
            })
        except Exception:  # noqa: BLE001
            logger.debug("restyle broadcast skipped", exc_info=True)
        _signal(ledger, "restyle", True, lang=target)
        ledger.turn_decision = ledger.turn_decision or "answer"
        return response, ledger

    async def _try_chat_write_handoff(
        self,
        *,
        user_message: str,
        conversation_history: list[dict] | None,
        state_ctx,
        instance_config: dict | None,
        surface=None,
    ):
        """PV2-3B: ESS write with enough slots → ChatHandoffOutcome; else seed state.

        Returns None when Chat should keep clarifying (incomplete slots) or the
        utterance is not an ESS write. Never stages host mutations.
        """
        from ai.engine.cognition.turn.handoff_agent import (
            build_chat_write_clarify,
            build_chat_write_handoff,
            build_slot_status_answer,
            combine_user_brief,
            enough_slots_for_chat_handoff,
            is_ess_slot_continuation,
            is_ess_write_utterance,
            is_bound_write_affirmation,
            is_ready_to_submit_ask,
            is_slot_status_ask,
            merge_slots,
            build_bound_write_confirmation_answer,
            resolve_ess_write_from_brief,
            seed_slots_into_state,
        )
        from ai.engine.cognition.plan.process_dial import (
            is_composite_brief,
            is_plan_dial_turn,
        )

        prior: dict = {}
        prior_api = ""
        if state_ctx is not None and getattr(state_ctx, "state", None) is not None:
            prior = dict(getattr(state_ctx.state, "slots", None) or {})
            prior_api = str((state_ctx.state.intent or {}).get("api") or "")

        prior_enough = bool(
            prior_api and enough_slots_for_chat_handoff(prior_api, prior)
        )
        current_is_write = is_ess_write_utterance(user_message)
        if prior and is_slot_status_ask(user_message):
            return build_slot_status_answer(
                api_name=prior_api,
                slots=prior,
                user_message=user_message,
            )
        if prior_enough and is_ready_to_submit_ask(user_message):
            return build_chat_write_handoff(
                api_name=prior_api,
                slots=prior,
                user_message=user_message,
                surface=surface,
            )
        # Already handed off — do not re-fire on meta follow-ups
        # ("is the handoff complete?", thanks). Thanks is a 0-LLM ack
        # (C8 / F-LIVE-10). A confirmation of the bound write restates the
        # handoff at 0 LLM, echoing the user's digits.
        last_decision = ""
        if state_ctx is not None and getattr(state_ctx, "state", None) is not None:
            decisions = getattr(state_ctx.state, "decisions", None) or []
            if decisions and isinstance(decisions[-1], dict):
                last_decision = str(decisions[-1].get("decision") or "")
        # Only restate after a handoff. "Yes, that's correct" while Chat is
        # still clarifying (leave t2) must stay an answer.
        if prior_enough and is_bound_write_affirmation(user_message, prior):
            if last_decision == "handoff_agent":
                return build_chat_write_handoff(
                    api_name=prior_api,
                    slots=prior,
                    user_message=user_message,
                    surface=surface,
                )
            if last_decision == "clarify":
                return build_bound_write_confirmation_answer(
                    api_name=prior_api,
                    slots=prior,
                    user_message=user_message,
                )
        if prior_enough and not current_is_write:
            return None
        # Fresh write, or a bare slot fill for an already-open write.
        if not current_is_write and not is_ess_slot_continuation(
            user_message, prior_api,
        ):
            return None

        # A brief with a guard, a branch, or two asks at once is a plan, not a
        # form. The single-write slot-filler must not answer «راجع قروضي … إذا
        # كان لدي قرض مفتوح توقف، إذا لا قدّم طلب قرض» with "which loan type?".
        # Step aside; the planner drafts the DAG (plan_task) and asks in context.
        if current_is_write and is_composite_brief(user_message):
            logger.info(
                "TurnPipelineRunner: composite ESS brief — slot-filler steps "
                "aside for the planner",
            )
            return None
        # Plan dial + fresh write brief → the header promised a drafted plan.
        # Keep the slot-filler only while the user is answering a clarify Chat
        # itself asked (chips / bare values), whatever the dial.
        answering_clarify = bool(prior_api) and last_decision == "clarify"
        if current_is_write and not answering_clarify and is_plan_dial_turn(
            user_message,
        ):
            logger.info(
                "TurnPipelineRunner: Plan dial + ESS write brief — slot-filler "
                "steps aside for the planner",
            )
            return None

        brief = combine_user_brief(user_message, conversation_history, prior)
        try:
            # Lexical — no MDM. Safe on the async Chat turn.
            resolved = resolve_ess_write_from_brief(
                brief, prefer_api=prior_api or None,
            )
        except Exception:  # noqa: BLE001 — never block the turn
            logger.debug("ESS write resolve failed", exc_info=True)
            return None
        if resolved is None:
            return None
        api_name, body = resolved
        slots = merge_slots(prior, body)
        seed_slots_into_state(state_ctx, api_name, slots)
        if not enough_slots_for_chat_handoff(api_name, slots):
            logger.info(
                "TurnPipelineRunner: ESS write incomplete slots api=%s — "
                "lexical clarify (no ReAct mutation)",
                api_name,
            )
            return build_chat_write_clarify(
                api_name=api_name,
                slots=slots,
                user_message=user_message,
            )
        first_leave_dump = (
            api_name == "submit_my_leave"
            and not any(prior.get(k) for k in ("start_date", "end_date", "days"))
            and bool(body.get("start_date") or body.get("end_date") or body.get("days"))
        )
        if first_leave_dump:
            return build_chat_write_clarify(
                api_name=api_name,
                slots=slots,
                user_message=user_message,
                echo=True,
            )
        just_completed_leave = (
            api_name == "submit_my_leave"
            and last_decision == "clarify"
            and not prior_enough
        )
        if just_completed_leave:
            return build_bound_write_confirmation_answer(
                api_name=api_name,
                slots=slots,
                user_message=user_message,
            )
        logger.info(
            "TurnPipelineRunner: Chat handoff_agent api=%s slots=%s",
            api_name, sorted(slots.keys()),
        )
        return build_chat_write_handoff(
            api_name=api_name,
            slots=slots,
            user_message=user_message,
            surface=surface,
        )

    async def _return_chat_handoff(
        self,
        *,
        outcome,
        ledger,
        meter,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        host_user_id: str | None,
        t0: float,
        finalize: bool = True,
    ):
        """Build a ChatHandoffOutcome response. ``finalize`` is the L3 commit."""
        from types import SimpleNamespace

        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run

        decision = str(getattr(outcome, "decision", None) or "handoff_agent")
        final_text = outcome.text
        total_latency = (time.monotonic() - t0) * 1000
        if decision == "handoff_agent":
            handoff_tool = {
                "tool_name": "call_host_api",
                "tool_args": {
                    "api_name": outcome.api_name,
                    "body": outcome.slots,
                },
                "result": outcome.tool_result,
                "error": None,
                "latency_ms": 0.0,
                "guardrail_flags": ["chat_no_host_mutation"],
            }
            if ledger.execution is not None:
                ledger.execution.completed_tools = [handoff_tool]
            else:
                ledger.execution = SimpleNamespace(completed_tools=[handoff_tool])

        ledger.final_response = (final_text or "")[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = 0
        ledger.total_llm_calls = 0
        ledger.force_action_fired = False

        if self.db is not None:
            try:
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    "final", 5,
                    {
                        "total_latency_ms": total_latency,
                        "handoff_agent": decision == "handoff_agent",
                        "api_name": outcome.api_name,
                        "chat_write_decision": decision,
                    },
                    0.0, verdict="pass",
                )
                await self.db.commit()
            except Exception:  # noqa: BLE001
                logger.debug("handoff ledger write skipped", exc_info=True)

        response = AgentResponse(
            text=final_text,
            sources_cited=[],
            tools_used=[],
            confidence=1.0,
            total_tokens=0,
            llm_calls=0,
            model="",
            response_type="inferred",
            actions=list(outcome.actions or []),
            # Clarify choices ride the follow-up rail → clickable chips in Chat.
            follow_ups=list(getattr(outcome, "follow_ups", None) or []),
            envelope=outcome.envelope,
        )
        await _broadcast_run(instance_id, "run.completed", {
            "run_id": turn_id,
            "total_latency_ms": total_latency,
            "total_tokens": 0,
            "total_llm_calls": 0,
            "handoff_agent": decision == "handoff_agent",
            "chat_write_decision": decision,
        })
        _signal(ledger, "skill_router", False)
        _signal(
            ledger,
            "chat_handoff" if decision == "handoff_agent" else f"chat_{decision}",
            True,
            api=outcome.api_name,
        )
        _signal(ledger, "weather_force", False)
        ledger.turn_decision = decision
        if finalize:
            _finalize_meter(ledger, meter, decision)
        return response, ledger

    async def _try_multi_step_plan(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        process_mode: str,
        host_user_id: str | None,
        page_context: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        retrieval,  # RetrievalResult
        progress_callback=None,
        stream_callback=None,
        state_ctx=None,
        surface=None,
    ):
        """PR-20: Attempt multi-step planning. Returns ReActResult, ChatHandoffOutcome, or None.

        None means "fall through to single-pass S3→S5" — the caller should
        treat this as "no multi-step needed."

        Chat + mutating ``call_host_api`` → ``ChatHandoffOutcome`` (ADR-0046);
        read-only multi-step plans still run ReActLoop.
        """
        from ai.engine.cognition.plan.planner import SkillAwarePlanner
        from ai.engine.cognition.plan.loop import ReActLoop
        from ai.engine.cognition.turn.draft import DraftWitness
        from ai.engine.cognition.turn.critic import CriticWitness
        from ai.engine.skills.registry import SkillRegistry
        from ai.engine.llm.prompts import build_chat_prompt
        from ai.engine.core.config import get_settings
        from ai.engine.cognition.turn.handoff_agent import (
            build_chat_write_handoff,
            enough_slots_for_chat_handoff,
            extract_plan_write,
            merge_slots,
            plan_has_mutating_host_api,
            seed_slots_into_state,
        )

        settings = get_settings()

        # Agent → Discuss seeds (and follow-ups) must never enter ReAct.
        from ai.engine.cognition.plan.planner import _wants_explicit_task_creation
        from ai.engine.cognition.turn.plan_revision import is_discuss_turn
        if is_discuss_turn(
            user_message,
            getattr(state_ctx, "state", None),
            process_mode,
        ):
            logger.info("TurnPipelineRunner: Agent discuss turn — skip ReAct")
            return None
        # "I need a task…" → Chat PLAN FIRST + plan_task, not silent ReAct.
        if _wants_explicit_task_creation(user_message, process_mode=process_mode):
            logger.info("TurnPipelineRunner: explicit task creation — skip ReAct")
            return None

        # Build skill registry from self.db
        skill_registry = SkillRegistry(self.db)

        # Build planner
        planner = SkillAwarePlanner(
            llm_client=self.llm_client,
            model=settings.LLM_MODEL,
        )

        plan = await planner.decompose(
            utterance=user_message,
            skill_registry=skill_registry,
            instance_id=instance_id,
            user_id=host_user_id or "",
            conversation_state=(
                state_ctx.state if state_ctx is not None else None
            ),
        )

        # Only activate ReAct loop for multi-step plans or skill-sourced plans
        if plan.source == "single_step" and len(plan.steps) <= 1:
            logger.debug("TurnPipelineRunner: single-step plan, skipping ReAct loop")
            return None

        catalog = (instance_config or {}).get("api_catalog") or []
        if plan_has_mutating_host_api(plan, api_catalog=catalog):
            api_name, body = extract_plan_write(plan)
            prior = {}
            if state_ctx is not None and getattr(state_ctx, "state", None) is not None:
                prior = dict(getattr(state_ctx.state, "slots", None) or {})
            slots = merge_slots(prior, body)
            seed_slots_into_state(state_ctx, api_name, slots)
            if enough_slots_for_chat_handoff(api_name, slots):
                logger.info(
                    "TurnPipelineRunner: mutating plan → handoff_agent "
                    "(skip ReAct) api=%s source=%s",
                    api_name, plan.source,
                )
                return build_chat_write_handoff(
                    api_name=api_name,
                    slots=slots,
                    user_message=user_message,
                    surface=surface,
                )
            logger.info(
                "TurnPipelineRunner: mutating plan incomplete slots — "
                "skip ReAct, fall through to clarify api=%s",
                api_name,
            )
            return None

        logger.info(
            "TurnPipelineRunner: activating ReAct loop source=%s steps=%d",
            plan.source, len(plan.steps),
        )

        # Build system prompt — LLM-synthesized
        config = instance_config or {}
        system_prompt = await build_chat_prompt(
            instance_name=config.get("display_name", "Unknown System"),
            system_description=config.get("description", ""),
            relevant_knowledge=(
                retrieval.knowledge_chunks[0]["content"]
                if retrieval.knowledge_chunks else "No knowledge loaded yet."
            ),
            relevant_memories=(
                retrieval.memory_chunks[0]["content"]
                if retrieval.memory_chunks else "No memories available."
            ),
            page_context=page_context or "unknown",
            user_info=user_info,
            persona=_audience_persona(config, user_info),
            api_catalog=_scoped_api_catalog(config, user_info),
            navigation_routes=_scoped_navigation_routes(config, user_info),
            domain_topics=config.get("domain_topics"),
            instance_config={
                **config,
                "persona": _audience_persona(config, user_info),
                "api_catalog": _scoped_api_catalog(config, user_info),
            },
            conversation_id=conversation_id,
            instance_id=instance_id,
        )

        # Build witnesses
        draft_witness = DraftWitness(
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
            executor=self.executor,
        )
        critic_witness = CriticWitness()

        loop = ReActLoop(
            draft_witness=draft_witness,
            critic_witness=critic_witness,
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
            db=self.db,
        )

        react_result = await loop.run(
            plan=plan,
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
            host_user_id=host_user_id,
            conversation_state=(
                state_ctx.state if state_ctx is not None else None
            ),
        )

        return react_result

    async def _try_fan_out(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None,
        page_context: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        retrieval,
        turn_id: str,
        budget_tracker=None,  # P3.4: BudgetTracker for per-run token limits
        state_ctx=None,
    ):
        """P3.2: Attempt orchestrator fan-out. Returns _FanOutResponse or None.

        None means "fall through to PR-20 / single-pass" — the caller should
        treat this as "fan-out not applicable."
        """
        from dataclasses import dataclass

        @dataclass
        class _FanOutResponse:
            final_text: str
            total_tokens: int
            total_latency_ms: float
            worker_ids: list[str]
            worker_count: int
            succeeded_count: int
            artifact_refs: list[dict]

        from ai.engine.agent.registry import AgentRegistry
        from ai.engine.agent.workers import WorkerPool, WorkerTask
        from ai.engine.llm.router import route_chat

        settings = get_settings()

        # Balanced budget gate: skip orchestrator only for clear ESS host
        # writes (leave/loan/attendance) — process_dial / Chat handoff own
        # those. Other mutations and analytics still get a fan-out decision.
        try:
            from ai.engine.agent.chat_surface import is_ess_write_intent

            if is_ess_write_intent(user_message or ""):
                logger.debug(
                    "TurnPipelineRunner: skip fan-out for ESS write intent"
                )
                return None
        except Exception:  # noqa: BLE001 — never block the turn
            pass

        # Look up orchestrator agent
        registry = AgentRegistry(self.db)
        await registry.seed_defaults(instance_id)

        orchestrator = await registry.get_agent(instance_id, "orchestrator")
        if orchestrator is None or not orchestrator.is_active:
            logger.debug("TurnPipelineRunner: no active orchestrator for instance=%s", instance_id)
            return None

        # Check orchestrator has valid workers
        workers = await registry.get_workers_for(orchestrator.id)
        active_workers = [(a, h) for a, h in workers if a.is_active]
        if not active_workers:
            logger.debug("TurnPipelineRunner: orchestrator has no active workers")
            return None

        # Build orchestrator ContextPack (Identity + catalog Task + fan-out Task).
        config = instance_config or {}
        from ai.engine.cognition.context_pack import TASK_FANOUT, build_context_pack
        from ai.engine.llm.prompts import build_chat_prompt
        task_body = await build_chat_prompt(
            instance_name=config.get("display_name", "Unknown System"),
            system_description=config.get("description", ""),
            relevant_knowledge=(
                retrieval.knowledge_chunks[0]["content"]
                if retrieval.knowledge_chunks else "No knowledge loaded yet."
            ),
            relevant_memories=(
                retrieval.memory_chunks[0]["content"]
                if retrieval.memory_chunks else "No memories available."
            ),
            page_context=page_context or "unknown",
            user_info=user_info,
            persona=_audience_persona(config, user_info),
            api_catalog=_scoped_api_catalog(config, user_info),
            navigation_routes=_scoped_navigation_routes(config, user_info),
            domain_topics=config.get("domain_topics"),
            instance_config={
                **config,
                "persona": _audience_persona(config, user_info),
                "api_catalog": _scoped_api_catalog(config, user_info),
            },
            conversation_id=conversation_id,
            instance_id=instance_id,
        )
        orch_pack = build_context_pack(
            state_ctx.state if state_ctx is not None else None,
            surface="chat",
            stage="fanout",
            user_info=user_info,
            instance_config=config,
            conversation_history=conversation_history,
            retrieval=retrieval,
            task_body=f"{task_body}\n\n{TASK_FANOUT}",
            include_state=True,
            include_knowledge=False,
            include_memory=False,
            include_history=False,
        )
        system_prompt = orch_pack.system_prompt()

        # Orchestrator decision call: should we fan out?
        orchestrator_messages = [
            {"role": "system", "content": orch_pack.system_prompt()},
        ]
        if conversation_history:
            orchestrator_messages.extend(conversation_history[-6:])
        orchestrator_messages.append({"role": "user", "content": user_message})

        # Only give orchestrator the fan-out tools
        from ai.engine.agent.tools import STATIC_TOOL_DEFINITIONS
        orch_tools = [
            t for t in STATIC_TOOL_DEFINITIONS
            if t.get("function", {}).get("name") in ("delegate_to_workers", "synthesize_worker_results")
        ]

        decision = await route_chat(
            task="chat",
            instance_id=instance_id,
            conversation_id=conversation_id,
            messages=orchestrator_messages,
            tools=orch_tools,
            db=self.db,
        )

        tool_calls = decision.get("tool_calls") or []
        if not tool_calls:
            # Orchestrator chose not to fan out — fall through
            logger.debug("TurnPipelineRunner: orchestrator chose not to fan out")
            return None

        # Process delegate_to_workers tool call
        delegate_call = None
        for tc in tool_calls:
            if tc.get("function", {}).get("name") == "delegate_to_workers":
                delegate_call = tc
                break

        if delegate_call is None:
            return None

        import json as _json
        try:
            delegate_args = _json.loads(delegate_call["function"]["arguments"])
        except (_json.JSONDecodeError, KeyError, TypeError):
            logger.warning("TurnPipelineRunner: invalid delegate_to_workers args")
            return None

        worker_specs = delegate_args.get("workers", [])
        if not worker_specs:
            return None

        # Build WorkerTask list
        tasks = []
        for spec in worker_specs:
            tasks.append(WorkerTask(
                agent_role=spec.get("agent_role", ""),
                task=spec.get("task", ""),
                context_hints=spec.get("context_hints"),
            ))

        if not tasks:
            return None

        # P3.4: Allocate worker budgets and record justification
        worker_budgets = None
        if budget_tracker is not None:
            justification = delegate_args.get("justification", f"Fan-out: {len(tasks)} parallel workers")
            await budget_tracker.set_justification(justification)
            worker_budgets = budget_tracker.allocate_worker_budget(len(tasks))
            logger.info(
                "BudgetTracker: fan-out allocation workers=%d total_pool=%d per_worker=%d",
                len(tasks), sum(worker_budgets), worker_budgets[0] if worker_budgets else 0,
            )

        # Run fan-out
        pool = WorkerPool(
            llm_client=self.llm_client,
            db=self.db,
            instance_id=instance_id,
            conversation_id=conversation_id,
            # P1-07: worker tool calls run through the same S5 dispatch path as
            # the orchestrator (read-only host APIs + knowledge lookups).
            executor=self.executor,
            instance_config=instance_config,
            knowledge_store=self.knowledge_store,
        )
        fan_out_result = await pool.fan_out(
            tasks=tasks,
            agent_registry=registry,
            orchestrator_id=orchestrator.id,
            system_prompt=system_prompt,
            worker_budgets=worker_budgets,
        )

        # Synthesize results
        if fan_out_result.artifact_refs:
            from ai.engine.cognition.context_pack import (
                TASK_FANOUT_SYNTHESIS,
                build_context_pack,
            )
            synth_pack = build_context_pack(
                state_ctx.state if state_ctx is not None else None,
                surface="chat",
                stage="fanout_synthesis",
                user_info=user_info,
                instance_config=instance_config,
                task_body=(
                    f"{system_prompt}\n\n{TASK_FANOUT_SYNTHESIS}\n\n"
                    f"User request: {user_message}"
                ),
                user_body=_json.dumps(fan_out_result.artifact_refs, indent=2),
                include_state=True,
                include_knowledge=False,
                include_memory=False,
                include_history=False,
            )
            synthesis_messages = [
                {"role": "system", "content": synth_pack.system_prompt()},
                {"role": "user", "content": synth_pack.user_prompt()},
            ]

            synthesis = await route_chat(
                task="chat",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=synthesis_messages,
                db=self.db,
            )
            final_text = synthesis.get("content") or ""
            synth_tokens = synthesis.get("input_tokens", 0) + synthesis.get("output_tokens", 0)
        else:
            final_text = "I wasn't able to gather information from my workers. Let me try a different approach."
            synth_tokens = 0

        total_tokens = (
            decision.get("input_tokens", 0) + decision.get("output_tokens", 0)
            + fan_out_result.total_tokens
            + synth_tokens
        )

        return _FanOutResponse(
            final_text=final_text,
            total_tokens=total_tokens,
            total_latency_ms=fan_out_result.total_latency_ms,
            worker_ids=fan_out_result.worker_ids,
            worker_count=len(tasks),
            succeeded_count=fan_out_result.succeeded_count,
            artifact_refs=fan_out_result.artifact_refs,
        )
