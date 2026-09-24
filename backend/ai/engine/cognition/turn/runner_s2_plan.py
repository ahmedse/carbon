"""Extracted stage block from TurnPipelineRunner._run_metered."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from ai.engine.agent.reasoning import AgentResponse
from ai.engine.cognition.auto_memory import AutoMemoryExtractor
from ai.engine.cognition.turn.runner_helpers import get_settings
from ai.engine.cognition.turn.exit_policy import may_stage, stage_exit, stage_soft_exit
from ai.engine.cognition.turn.router import RouteKind
from ai.engine.llm.call_meter import stage

from ai.engine.cognition.turn.runner_helpers import (
    _audience_persona,
    _commit_staged,
    _finalize_meter,
    _scoped_api_catalog,
    _scoped_navigation_routes,
    _signal,
)
from ai.engine.cognition.turn.runner_metered_state import MeteredTurnState
from ai.engine.cognition.turn.runner_render import (
    _DELIVERY_INJECTION,
    _normalize_weather_location,
    _normalize_weather_question,
    _synthesize_tool_results,
)
from ai.engine.cognition.turn.runner_surfaces import (
    _navigation_response,
    _navigation_text,
)
from ai.engine.cognition.turn.runner_util import (
    _completed_tools_from_react,
    _fanout_skip_reason,
    _filter_draft_tools,
    _is_declared_in_scope,
    _is_text_transform_request,
    _refusal_text,
    _write_trajectory_own_session,
)

logger = logging.getLogger("pulse.cognition.turn.runner")

async def run_s2_and_plan_gates(
    runner,
    st: MeteredTurnState,
    *,
    instance_id: str,
    conversation_id: str,
    host_user_id: str | None,
    process_mode: str,
    surface,
    page_context: str,
    conversation_history: list[dict] | None,
    instance_config: dict | None,
    user_info: dict | None,
    progress_callback,
    stream_callback,
    model: str | None,
    temperature: float | None,
    knowledge_items: list | None,
    scope: dict | None,
    process_state: dict | None,
    meter,
    state_ctx,
    budget,
    turn_id: str,
    t0: float,
    ledger,
    staged,
    settings,
    turn_route,
    original_user_message: str,
    state,
    _broadcast_run,

) -> tuple | None:
    s2_start = time.monotonic()
    await _broadcast_run(instance_id, 'run.step.started', {'run_id': turn_id, 'stage': 's2_retrieval', 'stage_index': 1})
    from ai.engine.cognition.turn.retrieve import RetrievalWitness
    retrieve_witness = RetrievalWitness(knowledge_store=runner.knowledge_store, memory_manager=runner.memory_manager)
    st.retrieval = await retrieve_witness.retrieve(instance_id, conversation_id, st.user_message, user_info, knowledge_items=knowledge_items, scope=scope, process_state=process_state, host_user_id=str(host_user_id) if host_user_id else None)
    ledger.retrieval = st.retrieval
    st.s2_latency = st.retrieval.retrieval_latency_ms
    await _broadcast_run(instance_id, 'run.step.completed', {'run_id': turn_id, 'stage': 's2_retrieval', 'stage_index': 1, 'latency_ms': st.s2_latency})
    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'retrieval', 1, {'chunks': len(st.retrieval.knowledge_chunks)}, st.s2_latency, verdict='pass')
    fan_out_result = None
    _fanout_skip = None
    if settings.AGENT_ORCHESTRATOR_ENABLED and runner.db is not None:
        _fanout_skip = _fanout_skip_reason(st.user_message, st.intent_resolution, conversation_history, min_tokens=settings.FANOUT_PROBE_MIN_TOKENS)
        if _fanout_skip:
            logger.info('[%s] fanout_skipped reason=%s', turn_id[:8], _fanout_skip)
            _signal(ledger, 'fanout_probe', False, reason=_fanout_skip)
    if settings.AGENT_ORCHESTRATOR_ENABLED and runner.db is not None and (not _fanout_skip):
        try:
            with stage('fanout'):
                fan_out_result = await runner._try_fan_out(instance_id=instance_id, conversation_id=conversation_id, user_message=st.user_message, host_user_id=host_user_id, page_context=page_context, conversation_history=conversation_history, instance_config=instance_config, user_info=user_info, retrieval=st.retrieval, turn_id=turn_id, budget_tracker=budget, state_ctx=state_ctx)
        except Exception:
            logger.exception('Fan-out attempt failed; falling back to multi-step / single-pass')
    if fan_out_result is not None:
        st.final_text = fan_out_result.final_text
        st.total_tokens = fan_out_result.total_tokens
        st.total_llm_calls = 1
        ledger.fan_out_used = True
        ledger.fan_out_worker_count = len(fan_out_result.worker_ids)
        ledger.fan_out_worker_ids = fan_out_result.worker_ids
        ledger.fan_out_artifact_refs = fan_out_result.artifact_refs
        ledger.fan_out_total_tokens = fan_out_result.total_tokens
        ledger.fan_out_latency_ms = fan_out_result.total_latency_ms
        logger.info('TurnPipelineRunner: fan-out complete turn=%s workers=%d succeeded=%d', turn_id[:8], fan_out_result.worker_count, fan_out_result.succeeded_count)
        s6_start = time.monotonic()
        total_latency = (time.monotonic() - t0) * 1000
        s6_latency = (time.monotonic() - s6_start) * 1000
        if budget is not None:
            await budget.consume(st.total_tokens)
            ledger.budget_snapshot = budget.snapshot()
            ledger.budget_exceeded = budget.exceeded
        await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'verdict': 'pass', 'fan_out_path': True, 'fan_out_worker_count': fan_out_result.worker_count, 'fan_out_artifact_count': len(fan_out_result.artifact_refs)}, s6_latency, verdict='pass')
        await runner.db.commit()
        ledger.final_response = st.final_text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = st.total_tokens
        ledger.total_llm_calls = st.total_llm_calls
        response = AgentResponse(text=st.final_text, sources_cited=[], tools_used=[], confidence=0.8, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='')
        await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'fan_out_path': True})
        _signal(ledger, 'skill_router', False)
        _signal(ledger, 'chat_handoff', False)
        _signal(ledger, 'weather_force', False)
        _finalize_meter(ledger, meter, 'answer')
        return (response, ledger)
    pulse_loop_result = None
    _pulse_is_platform_zone = st.intent_resolution is not None and st.intent_resolution.zone in ('platform', 'off_limits')
    # Plan drafts a task for review. Running the read here answers the brief in
    # the bubble, so the plan is never shown and no task is created.
    from ai.engine.agent.surface import Surface as _Surface
    _pulse_on_plan_dial = _Surface.resolve(surface, process_mode=process_mode, user_message=st.user_message or '') is _Surface.CHAT_PLAN
    if settings.PULSE_LOOP_ENABLED and runner.db is not None and runner._draft_tools and (not settings.KG_MULTI_STEP_ENABLED) and _pulse_is_platform_zone and (not _pulse_on_plan_dial):
        try:
            with stage('pulse_loop'):
                pulse_loop_result = await runner._try_pulse_loop(instance_id=instance_id, conversation_id=conversation_id, user_message=st.user_message, host_user_id=host_user_id, page_context=page_context, conversation_history=conversation_history, instance_config=instance_config, user_info=user_info, retrieval=st.retrieval, progress_callback=progress_callback, stream_callback=stream_callback, turn_id=turn_id, intent_resolution=st.intent_resolution, state_ctx=state_ctx)
        except Exception:
            logger.exception('[%s] Pulse loop attempt failed; falling back to single-pass', turn_id[:8])
    if pulse_loop_result is not None:
        st.final_text = pulse_loop_result.final_response
        st.total_tokens = 0
        st.total_llm_calls = pulse_loop_result.replans_used + len(pulse_loop_result.step_results)
        for i, sr in enumerate(pulse_loop_result.step_results):
            await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, f'react_step_{i}', 2 + i, {'step_id': sr.step_id, 'intent': sr.intent, 'critic_verdict': sr.critic_verdict, 'executed': sr.executed, 'error': sr.error}, 0.0, verdict=sr.critic_verdict, flags=sr.critic_flags)
        logger.info('TurnPipelineRunner: ReAct loop complete steps=%d replans=%d succeeded=%s', len(pulse_loop_result.step_results), pulse_loop_result.replans_used, pulse_loop_result.succeeded)
        s6_start = time.monotonic()
        total_latency = (time.monotonic() - t0) * 1000
        s6_latency = (time.monotonic() - s6_start) * 1000
        await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'critic_verdict': 'pass' if pulse_loop_result.succeeded else 'veto', 'pulse_loop_path': True}, s6_latency, verdict='pass' if pulse_loop_result.succeeded else 'veto')
        await runner.db.commit()
        _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))
        with stage('auto_memory'):
            asyncio.ensure_future(AutoMemoryExtractor.try_extract(user_message=st.user_message, instance_id=instance_id, host_user_id=host_user_id, db_session=runner.db))
        _react_completed_tools = _completed_tools_from_react(pulse_loop_result.step_results)
        if ledger.execution is not None:
            ledger.execution.completed_tools = _react_completed_tools
        else:
            from types import SimpleNamespace
            ledger.execution = SimpleNamespace(completed_tools=_react_completed_tools)
        try:
            from ai.engine.memory.working import update_focus_from_resolve_results
            update_focus_from_resolve_results(st.wm, conversation_id, _react_completed_tools)
        except Exception:
            logger.debug('[%s] resolve_entity focus update skipped (pulse_loop)', turn_id[:8], exc_info=True)
        ledger.final_response = st.final_text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = st.total_tokens
        ledger.total_llm_calls = st.total_llm_calls
        response = AgentResponse(text=st.final_text, sources_cited=[], tools_used=[], confidence=0.8 if pulse_loop_result.succeeded else 0.3, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='')
        await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls})
        _signal(ledger, 'skill_router', False)
        _signal(ledger, 'chat_handoff', False)
        _signal(ledger, 'weather_force', False)
        _finalize_meter(ledger, meter, 'tool_answer')
        return (response, ledger)
    react_result = None
    if settings.KG_MULTI_STEP_ENABLED and runner.db is not None:
        try:
            with stage('multi_step_plan'):
                react_result = await runner._try_multi_step_plan(instance_id=instance_id, conversation_id=conversation_id, user_message=st.user_message, process_mode=process_mode, host_user_id=host_user_id, page_context=page_context, conversation_history=conversation_history, instance_config=instance_config, user_info=user_info, retrieval=st.retrieval, progress_callback=progress_callback, stream_callback=stream_callback, state_ctx=state_ctx, surface=surface)
        except Exception:
            logger.exception('Multi-step plan attempt failed; falling back to single-pass')
    from ai.engine.cognition.turn.handoff_agent import ChatHandoffOutcome
    if isinstance(react_result, ChatHandoffOutcome):
        return await runner._return_chat_handoff(outcome=react_result, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, t0=t0)
    if react_result is not None:
        st.final_text = react_result.final_response
        st.total_tokens = 0
        st.total_llm_calls = react_result.replans_used + len(react_result.step_results)
        for i, sr in enumerate(react_result.step_results):
            await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, f'react_step_{i}', 2 + i, {'step_id': sr.step_id, 'intent': sr.intent, 'critic_verdict': sr.critic_verdict, 'executed': sr.executed, 'error': sr.error}, 0.0, verdict=sr.critic_verdict, flags=sr.critic_flags)
        logger.info('TurnPipelineRunner: ReAct loop complete steps=%d replans=%d succeeded=%s', len(react_result.step_results), react_result.replans_used, react_result.succeeded)
        s6_start = time.monotonic()
        total_latency = (time.monotonic() - t0) * 1000
        s6_latency = (time.monotonic() - s6_start) * 1000
        await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'critic_verdict': 'pass' if react_result.succeeded else 'veto', 'react_path': True}, s6_latency, verdict='pass' if react_result.succeeded else 'veto')
        await runner.db.commit()
        _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))
        with stage('auto_memory'):
            asyncio.ensure_future(AutoMemoryExtractor.try_extract(user_message=st.user_message, instance_id=instance_id, host_user_id=host_user_id, db_session=runner.db))
        _react_completed_tools = _completed_tools_from_react(react_result.step_results)
        if ledger.execution is not None:
            ledger.execution.completed_tools = _react_completed_tools
        else:
            from types import SimpleNamespace
            ledger.execution = SimpleNamespace(completed_tools=_react_completed_tools)
        try:
            from ai.engine.memory.working import update_focus_from_resolve_results
            update_focus_from_resolve_results(st.wm, conversation_id, _react_completed_tools)
        except Exception:
            logger.debug('[%s] resolve_entity focus update skipped (react)', turn_id[:8], exc_info=True)
        ledger.final_response = st.final_text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = st.total_tokens
        ledger.total_llm_calls = st.total_llm_calls
        response = AgentResponse(text=st.final_text, sources_cited=[], tools_used=[], confidence=0.8 if react_result.succeeded else 0.3, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='')
        await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls})
        _signal(ledger, 'skill_router', False)
        _signal(ledger, 'chat_handoff', False)
        _signal(ledger, 'weather_force', False)
        _finalize_meter(ledger, meter, 'tool_answer')
        return (response, ledger)

