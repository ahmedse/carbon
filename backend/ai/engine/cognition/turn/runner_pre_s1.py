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


def _superseded_committed_exit(turn_route) -> str:
    """Gate a committed route's v21 exit can no longer stage (V21-2), or ``""``.

    ``REPORT_CLARIFY`` commits the turn to the typed report-focus question, but
    that exit is superseded on ``PULSE_UNDERSTAND=v21`` (``may_stage`` is
    ``False``) and the Decision call below is skipped for committed routes. The
    skip is recorded by the fallthrough counter with its reason instead of
    staying silent; the Phase 2 fix gates the route itself.
    """
    if not getattr(turn_route, "committed", False):
        return ""
    gate = ""
    if turn_route.kind is RouteKind.REPORT_CLARIFY:
        gate = "typed_router"
    elif turn_route.kind is RouteKind.RESTYLE:
        gate = "restyle"
    if gate and not may_stage(gate):
        return gate
    return ""


def _unfinished_v21_decision(ledger) -> str:
    """The Decision miss this turn recorded, or ``""`` when it finished (IRP-8).

    On ``PULSE_UNDERSTAND=v21`` an un-fired ``v21_understand`` signal with one
    of these reasons means the Decision did not finish: ``fallthrough`` /
    ``unrepairable`` (the call ran and produced no exit) and
    ``committed_route_skipped`` (a committed route whose v21 exit is
    superseded). A deliberate skip — ``plan_dial`` (the Plan drafter owns the
    dial) or ``shadow_only`` (shadow logs, legacy answers) — is not a miss and
    is never returned.
    """
    for signal in getattr(ledger, "decision_signals", None) or []:
        if not isinstance(signal, dict):
            continue
        if signal.get("gate") != "v21_understand" or signal.get("fired"):
            continue
        reason = str((signal.get("detail") or {}).get("reason") or "")
        if reason in ("fallthrough", "unrepairable", "committed_route_skipped"):
            return reason
    return ""


def _v21_chat_no_fallthrough(st, *, ledger, state, surface):
    """ADR-0056 / IRP-8 (V21-1): a v21 Chat turn the Decision did not finish.

    pre-S1 owns the boundary: every soft exit has been considered and none was
    staged, so a Chat turn on v21 has no legacy spine (S1–S6) to fall into. The
    recorded miss is answered with the typed, visible error (ADR-0053) and
    named on the ledger (``fell_through`` / ``fallthrough_reason``) so a live
    run (IB-10) can count it.

    Agent keeps the planner path: its surface is not Chat, so this returns
    ``None`` and the spine runs exactly as before.
    """
    from ai.engine.cognition.turn.degradation import Degradation
    from ai.engine.cognition.turn.runner_surfaces import _degraded_reply
    from ai.engine.cognition.turn.understand import understand_mode

    if understand_mode() != "v21":
        return None
    if surface is None or not getattr(surface, "is_chat", False):
        return None
    reason = _unfinished_v21_decision(ledger)
    if not reason:
        return None
    ledger.fell_through = True
    ledger.fallthrough_reason = reason
    return _degraded_reply(
        ledger, Degradation("understand", reason), state, "v21",
        user_message=str(getattr(st, "user_message", "") or ""),
    )


async def run_pre_s1_gates(
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
    # I2: Handle open_question.confirm before all other gates
    # Affirmation to a pending confirm question → execute the bound tool deterministically
    if turn_route.confirm and runner.executor is not None and instance_id:
        try:
            _confirm_payload = turn_route.confirm
            from ai.engine.cognition.turn.plan_revision import (
                KIND as _PLAN_REVISION,
                build_revision_handoff,
            )
            if _confirm_payload.get("kind") == _PLAN_REVISION:
                # Chat proposes, Agent applies (ADR-0046): the confirmed
                # revision becomes a 0-LLM handoff to the Tasks panel. Chat
                # never calls edit_plan — the Chat guard would cancel it.
                response = build_revision_handoff(_confirm_payload, st.user_message)
                total_latency = (time.monotonic() - t0) * 1000
                await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': 0, 'total_llm_calls': 0, 'plan_revision_handoff': _confirm_payload.get('plan_id') or ''}, total_latency, verdict='pass')
                if runner.db is not None:
                    await runner.db.commit()
                ledger.final_response = response.text[:500]
                ledger.total_latency_ms = total_latency
                await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': 0, 'total_llm_calls': 0, 'plan_revision_handoff': True})
                _signal(ledger, 'open_question_confirm', True, api='plan_revision', plan_id=str(_confirm_payload.get('plan_id') or ''))
                _finalize_meter(ledger, meter, 'plan_revision_handoff')
                return (response, ledger)
            _confirm_api = str(_confirm_payload.get("api") or "").strip()
            if _confirm_api:
                from ai.engine.cognition.turn.ess_read import build_ess_self_tool_call
                # Inject bound ESS tool call
                _tool_call = build_ess_self_tool_call(_confirm_api, turn_id)
                # Mark that we're forcing this call (bypass draft LLM)
                st.forced_tool_call = _tool_call
                _signal(ledger, 'open_question_confirm', True, api=_confirm_api)
        except Exception:
            logger.warning('[%s] open_question_confirm injection failed; continuing', turn_id[:8], exc_info=True)
            _signal(ledger, 'open_question_confirm', False, error='injection_failed')
    else:
        _signal(ledger, 'open_question_confirm', False)

    _pending_fired = False
    try:
        from ai.engine.cognition.dialogue.pending_action import get_pending_action_store
        _pending_store = get_pending_action_store()
        _pending = _pending_store.check_confirmation(conversation_id, st.user_message)
        if _pending and runner.executor is not None and instance_id:
            _pending_fired = True
            from ai.engine.agent.tools import execute_learn_fact
            await execute_learn_fact(fact=_pending['fact'], category=_pending.get('category', 'observation'), instance_id=instance_id, executor=runner.executor, conversation_id=conversation_id)
            _pending_store.clear(conversation_id)
            _confirm_text = "Done — I've prepared a memory card for that. Click confirm to save it permanently."
            total_latency = (time.monotonic() - t0) * 1000
            await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': 0, 'total_llm_calls': 0, 'pending_confirmation_shortcircuit': True}, total_latency, verdict='pass')
            if runner.db is not None:
                await runner.db.commit()
            ledger.final_response = _confirm_text[:500]
            ledger.total_latency_ms = total_latency
            response = AgentResponse(text=_confirm_text, sources_cited=[], tools_used=[], confidence=0.8, total_tokens=0, llm_calls=0, model='')
            await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': 0, 'total_llm_calls': 0, 'pending_confirmation_shortcircuit': True})
            _signal(ledger, 'pending_confirm', True, action='memory_confirm')
            _finalize_meter(ledger, meter, 'memory_confirm')
            return (response, ledger)
    except Exception:
        logger.warning('[%s] Pending-confirmation short-circuit failed; continuing normal pipeline', turn_id[:8], exc_info=True)
    _signal(ledger, 'pending_confirm', _pending_fired)
    # Agent → Discuss is typed state, not transcript scanning (ADR-0049 P9):
    # a pending ``plan_revision`` question on the Plan dial, or the FE seed
    # turn with a linkable plan. ``discuss_thread`` also covers outcome-talk
    # seeds on Ask (prose-only for that one turn).
    from ai.engine.cognition.plan.planner import _is_agent_discuss_turn
    from ai.engine.cognition.turn.plan_revision import is_discuss_turn, linked_plan_ref
    st.discuss_ctx = is_discuss_turn(st.user_message, state, process_mode)
    st.plan_revision_ref = linked_plan_ref(state, st.user_message) if st.discuss_ctx else None
    st.discuss_thread = st.discuss_ctx or _is_agent_discuss_turn(st.user_message)
    _nav_fast_fired = False
    if not may_stage('nav_fast_path'):
        _signal(ledger, 'nav_fast_path', False, reason='v21')
    elif settings.NAVIGATION_RESOLVER_ENABLED and (not st.discuss_thread) and (not turn_route.committed):
        try:
            from ai.engine.cognition.turn.process_brief import is_deliverable_request, is_process_briefing
            from ai.engine.cognition.turn.navigation import is_how_where_ui, resolve_navigation
            from ai.engine.cognition.turn.handoff_agent import is_ess_write_utterance
            if is_process_briefing(st.user_message):
                logger.info('[%s] Skipping navigation fast-path (process briefing)', turn_id[:8])
                _signal(ledger, 'nav_fast_path', False, reason='process_briefing')
            elif is_ess_write_utterance(st.user_message) and (not is_how_where_ui(st.user_message)) or re.search('\\bremember\\b|learn_fact|تذكر|احفظ', st.user_message or '', re.I):
                _signal(ledger, 'nav_fast_path', False, reason='write_or_memory')
            elif is_deliverable_request(st.user_message):
                logger.info('[%s] Skipping navigation fast-path (deliverable request)', turn_id[:8])
                _signal(ledger, 'nav_fast_path', False, reason='deliverable_request')
            else:
                _nav = resolve_navigation(st.user_message, instance_config)
                if _nav.action in ('navigate', 'disambiguate'):
                    _nav_fast_fired = True
                    total_latency = (time.monotonic() - t0) * 1000
                    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'final', 5, {'total_latency_ms': total_latency, 'total_tokens': 0, 'total_llm_calls': 0, 'navigation_shortcircuit': _nav.action, 'navigation_source': 'deterministic_fast_path', 'navigation_targets': [t.route for t in _nav.targets]}, total_latency, verdict='pass')
                    if runner.db is not None:
                        await runner.db.commit()
                    ledger.final_response = _navigation_text(_nav)[:500]
                    ledger.total_latency_ms = total_latency
                    ledger.intent_zone = 'platform'
                    response = _navigation_response(_nav)
                    await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'total_latency_ms': total_latency, 'total_tokens': 0, 'total_llm_calls': 0, 'navigation_shortcircuit': _nav.action})
                    _signal(ledger, 'nav_fast_path', True, action=_nav.action)
                    stage_soft_exit(staged, 'navigate', 'nav_fast_path', response)
                _signal(ledger, 'nav_fast_path', False, action=getattr(_nav, 'action', 'none'))
        except Exception:
            logger.warning('[%s] Navigation short-circuit failed; continuing normal pipeline', turn_id[:8], exc_info=True)
            _signal(ledger, 'nav_fast_path', False, error='exception')
    elif st.discuss_thread and settings.NAVIGATION_RESOLVER_ENABLED:
        logger.info('[%s] Skipping navigation short-circuit (Agent discuss thread)', turn_id[:8])
        _signal(ledger, 'nav_fast_path', False, reason='discuss_thread')
    elif not settings.NAVIGATION_RESOLVER_ENABLED:
        _signal(ledger, 'nav_fast_path', False, reason='disabled')
    if not _nav_fast_fired and ledger.decision_signals is not None:
        if not any((s.get('gate') == 'nav_fast_path' for s in ledger.decision_signals)):
            _signal(ledger, 'nav_fast_path', False)
    _plan_status = None
    if not turn_route.committed and may_stage('plan_status'):
        _plan_status = await runner._try_plan_status_answer(user_message=st.user_message, state_ctx=state_ctx, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, t0=t0)
    if _plan_status is not None:
        stage_soft_exit(staged, 'answer', 'plan_status', _plan_status[0])
    # ADR-0056: on v21 the Decision owns writes, self-reads and deixis; these
    # wording gates only run on the legacy path until it is deleted.
    from ai.engine.cognition.turn.understand import understand_mode

    _legacy = understand_mode() != "v21"
    st.chat_handoff = None
    if _legacy and not turn_route.committed and _plan_status is None:
        st.chat_handoff = await runner._try_chat_write_handoff(user_message=st.user_message, conversation_history=conversation_history, state_ctx=state_ctx, instance_config=instance_config, surface=surface)
    if st.chat_handoff is None and _plan_status is None and may_stage('next_step'):
        _next_step = await runner._try_next_step_offer(user_message=st.user_message, state_ctx=state_ctx, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, t0=t0)
        if _next_step is not None:
            stage_soft_exit(staged, 'answer', 'next_step', _next_step[0])
    if st.chat_handoff is not None:
        _handoff_pair = await runner._return_chat_handoff(outcome=st.chat_handoff, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, t0=t0, finalize=False)
        _handoff_decision = str(getattr(st.chat_handoff, 'decision', None) or 'handoff_agent')
        stage_exit(staged, _handoff_decision, 'chat_handoff' if _handoff_decision == 'handoff_agent' else f'chat_{_handoff_decision}', _handoff_pair[0])
    # I6: "where are those?" with exactly one subject in durable state is a
    # continuation of that subject, not a question. Normalize the message so
    # the bound self-read binds it; the deixis gate in S1 then stays silent.
    try:
        _resolved_msg = ''
        if _legacy:
            from ai.engine.cognition.dialogue.deixis import resolve_deixis_subject
            _deixis_results = list(getattr(state, 'last_results', None) or []) if state is not None else []
            _resolved_msg = resolve_deixis_subject(st.user_message, last_results=_deixis_results)
        if _resolved_msg:
            st.deixis_subject = _resolved_msg.rsplit(' — ', 1)[-1]
            st.user_message = _resolved_msg
            _signal(ledger, 'deixis_resolved', True, subject=st.deixis_subject)
        else:
            _signal(ledger, 'deixis_resolved', False)
    except Exception:
        logger.debug('[%s] deixis subject resolution skipped', turn_id[:8], exc_info=True)
    st.ess_bound = None
    if _legacy and not turn_route.committed and st.chat_handoff is None and (runner.executor is not None):
        st.ess_bound = await runner._try_bound_ess_self_read(user_message=st.user_message, conversation_history=conversation_history, state_ctx=state_ctx, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, instance_config=instance_config, t0=t0, surface=surface)
    if st.ess_bound is not None:
        stage_exit(staged, 'tool_answer', 'ess_bound_self_read', st.ess_bound[0])
    _superseded_exit = _superseded_committed_exit(turn_route)
    if _superseded_exit:
        # V21-2 defect: a committed route whose exit is superseded cannot be
        # reached by the Decision (the call below is skipped on committed
        # routes). Record the fallthrough with its reason so the counter sees
        # it, never a silent S3–S6 answer. Fired=False: the Arbiter ignores it.
        _signal(
            ledger, 'v21_understand', False,
            reason='committed_route_skipped',
            route=turn_route.kind.value,
            exit_gate=_superseded_exit,
        )
    if st.ess_bound is None and (not turn_route.committed) and (st.chat_handoff is None) and (runner.executor is not None):
        _v21 = await runner._try_v21_understand(user_message=st.user_message, conversation_history=conversation_history, ledger=ledger, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, instance_config=instance_config, t0=t0, surface=surface, state_ctx=state_ctx, user_info=user_info, process_mode=process_mode, progress_callback=progress_callback, dense_thinking=bool(getattr(st, 'dense_thinking', False)), page_context=page_context)
        if _v21 is not None:
            return _v21
    _zero = None
    if not turn_route.committed and st.ess_bound is None and may_stage('zero_llm'):
        _zero = await runner._try_zero_llm_surface(user_message=st.user_message, state_ctx=state_ctx, conversation_history=conversation_history, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, t0=t0)
    if _zero is not None:
        _zero_resp = _zero[0]
        _zero_decision = 'clarify' if getattr(_zero_resp, 'response_type', '') == 'clarification' else 'answer'
        stage_soft_exit(staged, _zero_decision, 'zero_llm', _zero_resp)
    if turn_route.kind is RouteKind.PLAN_PROCESS:
        # v21 supersedes the soft exit, so the planner owns the turn directly.
        # A proposal returns here. One read on this dial is the draft card.
        # Understanding answers that read only when this dial has no draft.
        _plan_dial = await runner._try_plan_dial_process_plan(user_message=st.user_message, process_mode=process_mode, state_ctx=state_ctx, ledger=ledger, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, t0=t0)
        if _plan_dial is not None:
            return _plan_dial
        _v21_plan = await runner._try_v21_understand(user_message=st.user_message, conversation_history=conversation_history, ledger=ledger, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, host_user_id=host_user_id, instance_config=instance_config, t0=t0, surface=surface, state_ctx=state_ctx, user_info=user_info, process_mode=process_mode, progress_callback=progress_callback, dense_thinking=bool(getattr(st, 'dense_thinking', False)), page_context=page_context)
        if _v21_plan is not None:
            return _v21_plan
    if turn_route.kind is RouteKind.RESTYLE and may_stage('restyle'):
        _restyle = await runner._try_restyle_previous_answer(user_message=st.user_message, conversation_history=conversation_history, ledger=ledger, meter=meter, turn_id=turn_id, instance_id=instance_id, conversation_id=conversation_id, t0=t0)
        if _restyle is not None:
            stage_soft_exit(staged, 'answer', 'restyle', _restyle[0])
    if turn_route.kind is RouteKind.REPORT_CLARIFY and may_stage('typed_router'):
        question = turn_route.open_question
        text = question.prompt if question is not None else ''
        response = AgentResponse(text=text, sources_cited=[], tools_used=[], confidence=1.0, total_tokens=0, llm_calls=0, model='', response_type='clarification', follow_ups=[item.get('label') or item.get('value') or '' for item in (question.to_dict().get('options', []) if question is not None else [])], open_question=question.to_dict() if question is not None else None)
        _signal(ledger, 'chat_clarify', True, kind='report_focus')
        stage_soft_exit(staged, 'clarify', 'typed_router', response)
    _process_brief_early_fired = False
    if not st.discuss_thread and (not turn_route.committed) and may_stage('process_brief_early'):
        try:
            from asgiref.sync import sync_to_async
            from ai.engine.cognition.turn.process_brief import try_process_briefing
            _early_brief = await sync_to_async(try_process_briefing, thread_sensitive=True)(st.user_message)
            if _early_brief is not None:
                _process_brief_early_fired = True
                _pid, _brief_text = _early_brief
                total_latency = (time.monotonic() - t0) * 1000
                ledger.intent_zone = 'concept'
                ledger.final_response = _brief_text[:500]
                ledger.total_latency_ms = total_latency
                response = AgentResponse(text=_brief_text, sources_cited=[], tools_used=[], confidence=1.0, total_tokens=0, llm_calls=0, model='', response_type='inferred', actions=[])
                await _broadcast_run(instance_id, 'run.completed', {'run_id': turn_id, 'process_briefing': _pid, 'navigation_source': 'skipped_for_process_brief'})
                _signal(ledger, 'process_brief_early', True, process_id=_pid)
                stage_soft_exit(staged, 'process_brief', 'process_brief_early', response)
        except Exception:
            logger.warning('[%s] Process briefing early gate failed; continuing', turn_id[:8], exc_info=True)
    _signal(ledger, 'process_brief_early', _process_brief_early_fired)
    _early = _commit_staged(ledger, meter, staged)
    if _early is not None:
        return _early
    return _v21_chat_no_fallthrough(st, ledger=ledger, state=state, surface=surface)

