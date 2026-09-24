"""Extracted stage block from TurnPipelineRunner._run_metered."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from ai.engine.agent.reasoning import AgentResponse
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

async def run_s1_intent(
    runner,
    st: MeteredTurnState,
    *,
    instance_id: str,
    conversation_id: str,
    host_user_id: str | None,
    process_mode: str,
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
    st.s1_start = time.monotonic()
    await _broadcast_run(instance_id, 'run.step.started', {'run_id': turn_id, 'stage': 's1_salience', 'stage_index': 0})
    from ai.engine.cognition.turn.salience import SalienceWitness
    salience_witness = SalienceWitness()
    st.salience = await salience_witness.assess(st.user_message)
    ledger.salience = st.salience
    _signal(ledger, 'salience', False, domain=st.salience.domain, route=st.salience.route)
    s1_latency = (time.monotonic() - st.s1_start) * 1000
    await _broadcast_run(instance_id, 'run.step.completed', {'run_id': turn_id, 'stage': 's1_salience', 'stage_index': 0, 'latency_ms': s1_latency})
    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'salience', 0, {'domain': st.salience.domain, 'route': st.salience.route, 'weight': st.salience.weight}, s1_latency, verdict='pass')
    from ai.engine.cognition.dialogue.entity_extractor import EntityExtractor
    from ai.engine.memory.working import get_working_memory
    from ai.engine.learning.preferences import PreferenceClassifier, get_session_preference_store
    st.wm = get_working_memory()
    _is_wq = runner._is_weather_query
    _wm_focus_now = st.wm.get_focus(conversation_id)
    st.is_weather_rewrite_turn = False
    if _wm_focus_now is not None and _wm_focus_now.entity_type == 'pending_weather' and (not _is_wq(st.user_message)):
        _pending_weather_query = _wm_focus_now.entity
        with stage('weather_normalize'):
            _normalized_location = await _normalize_weather_location(instance_id=instance_id, conversation_id=conversation_id, original_question=_pending_weather_query, user_reply=st.user_message.strip(), conversation_history=conversation_history, model=model, user_info=user_info, instance_config=instance_config, state=state_ctx.state if state_ctx is not None else None)
        st.user_message = f'weather in {_normalized_location}'
        logger.info('[WEATHER-FT] Rewrote bare location reply to: %r', st.user_message)
        st.is_weather_rewrite_turn = True
        st.wm.set_focus(conversation_id, st.user_message, 'weather_resolution')
    _entity = EntityExtractor().extract(st.user_message)
    if _entity:
        st.wm.set_focus(conversation_id, _entity.name, _entity.entity_type)
    st.pref_store = get_session_preference_store()
    if host_user_id:
        try:
            from asgiref.sync import sync_to_async as _pref_s2a
            await _pref_s2a(st.pref_store.update, thread_sensitive=True)(host_user_id, PreferenceClassifier().classify(st.user_message))
        except Exception as _e:
            logger.warning('[GAP-4] preference persist failed user=%s: %s', host_user_id, _e)
    try:
        from ai.engine.cognition.dialogue.deixis import should_gate_deixis
        _deixis_last_results = list(getattr(getattr(state_ctx, 'state', None), 'last_results', None) or []) if state_ctx is not None else []
        _deixis_q = None if st.deixis_subject else should_gate_deixis(st.user_message, conversation_history=conversation_history, last_results=_deixis_last_results)
        if _deixis_q:
            # I5: deixis must not exit if there's no last_result to refer to
            _last_tool_result = None
            if state_ctx and state_ctx.state:
                _results = state_ctx.state.last_results or []
                _last_tool_result = _results[-1] if _results else None
            
            if _last_tool_result:
                try:
                    from ai.pulse_ux_telemetry import emit_ux
                    emit_ux('chat.deixis_gate', has_topic='**' in _deixis_q)
                except Exception:
                    pass
                # I1: Attach typed open_question with kind=confirm_subject and confirm from last tool
                _confirm_payload = {
                    "op": "call_tool",
                    "api": str(_last_tool_result.get("api") or ""),
                    "args": {},
                }
                _open_q = {
                    "kind": "confirm_subject",
                    "prompt": _deixis_q,
                    "slot": "",
                    "confirm": _confirm_payload,
                }
                total_latency = (time.monotonic() - t0) * 1000
                await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'intent_shortcircuit': 'deixis'}, total_latency, verdict='pass')
                if runner.db is not None:
                    await runner.db.commit()
                ledger.final_response = _deixis_q[:500]
                ledger.total_latency_ms = total_latency
                ledger.total_tokens = st.total_tokens
                ledger.total_llm_calls = st.total_llm_calls
                response = AgentResponse(text=_deixis_q, sources_cited=[], tools_used=[], confidence=0.75, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='', response_type='clarification', confidence_label='medium', open_question=_open_q)
                await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'intent_shortcircuit': 'deixis'})
                _signal(ledger, 'deixis', True)
                stage_soft_exit(staged, 'clarify', 'deixis', response)
            else:
                # I5: No last_result → deixis question is invalid, fall through
                _signal(ledger, 'deixis', False, reason='no_last_results')
    except Exception:
        logger.warning('[%s] Deixis gate failed; continuing', turn_id[:8], exc_info=True)
    _signal(ledger, 'deixis', False)
    _after_deixis = _commit_staged(ledger, meter, staged)
    if _after_deixis is not None:
        return _after_deixis
    st.intent_resolution = None
    if settings.INTENT_RESOLVER_ENABLED:
        try:
            from ai.engine.cognition.turn.intent import IntentResolver
            from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver
            _resolved_for_intent = AnaphoraResolver(st.wm).resolve(conversation_id, st.user_message)
            with stage('intent'):
                st.intent_resolution = await IntentResolver().resolve(user_message=_resolved_for_intent, api_catalog=_scoped_api_catalog(instance_config, user_info), navigation_routes=_scoped_navigation_routes(instance_config, user_info), tenant_org=(instance_config or {}).get('tenant_org'), conversation_history=conversation_history, instance_id=instance_id, conversation_id=conversation_id, db=runner.db, model=settings.INTENT_RESOLVER_MODEL or None, min_confidence=settings.INTENT_RESOLVER_MIN_CONFIDENCE, ambiguity_gap=settings.INTENT_RESOLVER_AMBIGUITY_GAP, user_info=user_info, instance_config=instance_config, state=state_ctx.state if state_ctx is not None else None)
        except Exception:
            logger.warning('[%s] Intent resolution failed; continuing without it', turn_id[:8], exc_info=True)
    if state_ctx is not None:
        state_ctx.intent = st.intent_resolution
    if st.intent_resolution is not None:
        st.total_llm_calls += 1
        st.total_tokens += st.intent_resolution.input_tokens + st.intent_resolution.output_tokens
        await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'intent', 0, {'action': st.intent_resolution.action, 'zone': st.intent_resolution.zone, 'intent': st.intent_resolution.intent, 'confidence': st.intent_resolution.confidence, 'candidates': [{'name': c.name, 'confidence': c.confidence} for c in st.intent_resolution.candidates]}, (time.monotonic() - st.s1_start) * 1000, tokens_used=st.intent_resolution.input_tokens + st.intent_resolution.output_tokens, model_used=st.intent_resolution.model_used, verdict='pass')
        ledger.intent_zone = st.intent_resolution.zone
        if not st.discuss_thread:
            from asgiref.sync import sync_to_async
            from ai.engine.cognition.turn.process_brief import try_process_briefing
            _brief = await sync_to_async(try_process_briefing, thread_sensitive=True)(st.user_message)
            if _brief is not None:
                _pid, _brief_text = _brief
                total_latency = (time.monotonic() - t0) * 1000
                await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'process_briefing': _pid}, total_latency, verdict='pass')
                if runner.db is not None:
                    await runner.db.commit()
                ledger.final_response = _brief_text[:500]
                ledger.total_latency_ms = total_latency
                ledger.total_tokens = st.total_tokens
                ledger.total_llm_calls = st.total_llm_calls
                response = AgentResponse(text=_brief_text, sources_cited=[], tools_used=[], confidence=1.0, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='', response_type='inferred', actions=[])
                await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'process_briefing': _pid})
                _signal(ledger, 'process_brief', True, process_id=_pid)
                _signal(ledger, 'intent_short_circuit', False, action='process_brief')
                stage_soft_exit(staged, 'process_brief', 'process_brief', response)
        from ai.engine.cognition.turn.process_brief import is_deliverable_request as _is_deliv
        if not st.discuss_thread and (not _is_deliv(st.user_message)) and (st.intent_resolution.action == 'navigate') and st.intent_resolution.navigate_target:
            from ai.engine.cognition.turn.navigation import ground_navigation
            _nav = ground_navigation(st.intent_resolution.navigate_target, instance_config)
            if _nav.action in ('navigate', 'disambiguate'):
                total_latency = (time.monotonic() - t0) * 1000
                await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'navigation_shortcircuit': _nav.action, 'navigation_source': 'llm_intent', 'navigation_targets': [t.route for t in _nav.targets]}, total_latency, verdict='pass')
                if runner.db is not None:
                    await runner.db.commit()
                ledger.final_response = _navigation_text(_nav)[:500]
                ledger.total_latency_ms = total_latency
                ledger.total_tokens = st.total_tokens
                ledger.total_llm_calls = st.total_llm_calls
                response = _navigation_response(_nav, total_tokens=st.total_tokens, total_llm_calls=st.total_llm_calls)
                await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'navigation_shortcircuit': _nav.action})
                _signal(ledger, 'nav_ground', True, action=_nav.action)
                _signal(ledger, 'intent_short_circuit', False, action='navigate')
                stage_soft_exit(staged, 'navigate', 'nav_ground', response)
            _signal(ledger, 'nav_ground', False, action='navigate')
        else:
            _signal(ledger, 'nav_ground', False)
        if st.intent_resolution.zone == 'off_limits':
            from ai.engine.cognition.dialogue.deixis import is_confirm_reply
            if is_confirm_reply(st.user_message):
                st.intent_resolution.zone = 'platform'
                logger.info('[%s] Confirm reply reclassified off_limits → platform', turn_id[:8])
        _off_limits_override = ''
        if st.intent_resolution.zone == 'off_limits' and _is_declared_in_scope(st.user_message, instance_config):
            st.intent_resolution.zone = 'platform'
            ledger.intent_zone = 'platform'
            _off_limits_override = 'declared_in_scope'
            logger.info('[%s] In-scope ask reclassified off_limits → platform', turn_id[:8])
        if st.intent_resolution.zone == 'off_limits':
            _refuse_text = _refusal_text(instance_config, st.user_message)
            total_latency = (time.monotonic() - t0) * 1000
            await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'intent_shortcircuit': 'off_limits'}, total_latency, verdict='pass')
            if runner.db is not None:
                await runner.db.commit()
            ledger.final_response = _refuse_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = st.total_tokens
            ledger.total_llm_calls = st.total_llm_calls
            response = AgentResponse(text=_refuse_text, sources_cited=[], tools_used=[], confidence=0.7, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='', response_type='clarification', confidence_label='medium')
            await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'intent_shortcircuit': 'off_limits'})
            _signal(ledger, 'off_limits', True, zone='off_limits')
            _signal(ledger, 'intent_short_circuit', True, action='off_limits')
            stage_exit(staged, 'refuse', 'off_limits', response)
        if _off_limits_override:
            _signal(ledger, 'off_limits', False, zone=st.intent_resolution.zone, override=_off_limits_override)
        else:
            _signal(ledger, 'off_limits', False, zone=st.intent_resolution.zone)
        if st.intent_resolution.action in ('clarify', 'disambiguate') and (not st.is_weather_rewrite_turn):
            if st.intent_resolution.action == 'clarify':
                _short_text = st.intent_resolution.clarification or "Could you clarify what you'd like me to look up?"
                # I1: Attach typed open_question with kind=confirm_api and confirm payload
                _top_candidate = (st.intent_resolution.candidates or [None])[0]
                _top_api = str(getattr(_top_candidate, 'name', '') or '') if _top_candidate else ""
                _open_q_confirm = None
                if _top_api:
                    _open_q_confirm = {
                        "op": "call_tool",
                        "api": _top_api,
                        "args": {},
                    }
                _open_q = {
                    "kind": "confirm_api",
                    "prompt": _short_text,
                    "slot": "",
                    "confirm": _open_q_confirm,
                } if _top_api else {
                    "kind": "unbound",
                    "prompt": _short_text,
                    "slot": "",
                }
            else:
                _opts = st.intent_resolution.options or [c.name for c in st.intent_resolution.candidates[:3]]
                _short_text = 'I can look that up a few different ways — which do you mean?\n' + '\n'.join((f'- {o}' for o in _opts))
                # I1: Attach typed open_question with kind=pick_api and options
                _open_q_options = []
                for i, cand in enumerate((st.intent_resolution.candidates or [])[:3]):
                    _open_q_options.append({
                        "id": str(i + 1),
                        "label": str(getattr(cand, 'name', '') or f"Option {i+1}"),
                        "value": str(getattr(cand, 'name', '') or ""),
                    })
                _open_q = {
                    "kind": "pick_api",
                    "prompt": _short_text,
                    "slot": "",
                    "options": _open_q_options,
                }
            total_latency = (time.monotonic() - t0) * 1000
            await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'intent_shortcircuit': st.intent_resolution.action}, total_latency, verdict='pass')
            if runner.db is not None:
                await runner.db.commit()
            ledger.final_response = _short_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = st.total_tokens
            ledger.total_llm_calls = st.total_llm_calls
            response = AgentResponse(text=_short_text, sources_cited=[], tools_used=[], confidence=0.7, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='', response_type='clarification', confidence_label='medium', open_question=_open_q)
            await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': st.total_tokens, 'total_llm_calls': st.total_llm_calls, 'intent_shortcircuit': st.intent_resolution.action})
            if _is_wq(st.user_message):
                st.wm.set_focus(conversation_id, st.user_message, 'pending_weather')
                logger.info('[WEATHER-FT] Intent shortcircuit — stored pending_weather: %r', st.user_message)
            _signal(ledger, 'intent_short_circuit', True, action=st.intent_resolution.action)
            _signal(ledger, 'chat_clarify', True, action=st.intent_resolution.action)
            stage_soft_exit(staged, 'clarify', 'chat_clarify', response)
        _signal(ledger, 'intent_short_circuit', False, action=st.intent_resolution.action)
        _signal(ledger, 'process_brief', False)
    else:
        _signal(ledger, 'intent_short_circuit', False, action='none')
        _signal(ledger, 'process_brief', False)
        _signal(ledger, 'nav_ground', False)
        _signal(ledger, 'off_limits', False)
    if not st.discuss_thread:
        from asgiref.sync import sync_to_async
        from ai.engine.cognition.turn.process_brief import try_process_briefing
        _brief_fb = await sync_to_async(try_process_briefing, thread_sensitive=True)(st.user_message)
        if _brief_fb is not None:
            _pid, _brief_text = _brief_fb
            total_latency = (time.monotonic() - t0) * 1000
            ledger.intent_zone = 'concept'
            ledger.final_response = _brief_text[:500]
            ledger.total_latency_ms = total_latency
            response = AgentResponse(text=_brief_text, sources_cited=[], tools_used=[], confidence=1.0, total_tokens=st.total_tokens, llm_calls=st.total_llm_calls, model='', response_type='inferred', actions=[])
            await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'process_briefing': _pid})
            _signal(ledger, 'process_brief', True, process_id=_pid)
            stage_soft_exit(staged, 'process_brief', 'process_brief', response)
    _gated = _commit_staged(ledger, meter, staged)
    if _gated is not None:
        return _gated

