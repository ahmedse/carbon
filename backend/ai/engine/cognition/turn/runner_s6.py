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

async def run_s6_finalize(
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

) -> tuple:
    s6_start = time.monotonic()
    await _broadcast_run(instance_id, 'run.step.started', {'run_id': turn_id, 'stage': 's6_finalize', 'stage_index': 5})
    total_latency = (time.monotonic() - t0) * 1000
    s6_latency = (time.monotonic() - s6_start) * 1000
    if budget is not None:
        ledger.budget_snapshot = budget.snapshot()
        ledger.budget_exceeded = budget.exceeded
    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'critic_verdict': st.critic.verdict, 'verification_passed': ledger.verification_passed, 'verification_unsupported': ledger.verification_unsupported, 'verification_error': ledger.verification_error}, s6_latency, verdict=st.critic.verdict)
    await runner.db.commit()
    _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))
    ledger.final_response = st.final_text[:500]
    ledger.total_latency_ms = total_latency
    ledger.total_tokens = st.total_tokens
    ledger.total_llm_calls = st.total_llm_calls
    logger.info('TurnPipelineRunner: turn=%s domain=%s route=%s critic=%s latency=%.0fms tokens=%d', turn_id[:8], st.salience.domain, st.salience.route, st.critic.verdict, total_latency, st.total_tokens)
    response = AgentResponse(text=st.final_text, sources_cited=st.draft.claimed_citations, tools_used=st.draft.tool_calls, confidence=st.draft.confidence, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model=st.draft.model_used, envelope=st.synth.get('envelope') if st.synth else None)
    with stage('auto_memory'):
        asyncio.ensure_future(AutoMemoryExtractor.try_extract(user_message=st.user_message, instance_id=instance_id, host_user_id=host_user_id, db_session=runner.db))
    await _broadcast_run(instance_id, 'run.step.completed', {'run_id': turn_id, 'stage': 's6_finalize', 'stage_index': 5, 'latency_ms': s6_latency})
    await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls})
    try:
        from ai.engine.cognition.dialogue.pending_action import get_pending_action_store
        _pending_store = get_pending_action_store()
        _proposal = _pending_store.detect_proposal(st.final_text)
        if _proposal:
            _pending_store.set_pending(conversation_id, _proposal['fact'], _proposal['category'])
    except Exception:
        logger.warning('[%s] Pending-action proposal detection failed', turn_id[:8], exc_info=True)
    _chat_handoff_fired = False
    for _tool in st.execution.completed_tools or []:
        _raw = _tool.get('result') if isinstance(_tool, dict) else None
        _parsed = _raw
        if isinstance(_raw, str):
            try:
                import json as _json_handoff
                _parsed = _json_handoff.loads(_raw)
            except (TypeError, ValueError):
                _parsed = None
        if isinstance(_parsed, dict) and _parsed.get('action') == 'chat_handoff':
            _chat_handoff_fired = True
            break
    _signal(ledger, 'chat_handoff', _chat_handoff_fired)
    if _chat_handoff_fired:
        _turn_decision = 'handoff_agent'
    elif st.execution.completed_tools:
        _signal(ledger, 'tools_executed', True)
        _turn_decision = 'tool_answer'
    else:
        _turn_decision = 'answer'
    _finalize_meter(ledger, meter, _turn_decision)
    return (response, ledger)

