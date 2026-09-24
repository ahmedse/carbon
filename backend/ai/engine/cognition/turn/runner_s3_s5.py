"""Extracted stage block from TurnPipelineRunner._run_metered."""
from __future__ import annotations

import asyncio
import inspect
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
    _wants_visual,
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

async def run_s3_through_s5(
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
    _is_wq = runner._is_weather_query
    s3_start = time.monotonic()
    await _broadcast_run(instance_id, 'run.step.started', {'run_id': turn_id, 'stage': 's3_draft', 'stage_index': 2})
    if progress_callback is not None:
        _stage = (
            "Drafting a plan for you to review…"
            if str(process_mode or "") == "plan"
            else "Reading your request…"
        )
        _maybe = progress_callback(_stage)
        if inspect.isawaitable(_maybe):
            await _maybe
    from ai.engine.cognition.turn.draft import DraftWitness
    draft_witness = DraftWitness(llm_client=runner.llm_client, knowledge_store=runner.knowledge_store, memory_manager=runner.memory_manager, executor=runner.executor)
    config = instance_config or {}
    from ai.engine.llm.prompts import build_chat_prompt
    system_prompt = await build_chat_prompt(instance_name=config.get('display_name', 'Unknown System'), system_description=config.get('description', ''), relevant_knowledge=st.retrieval.knowledge_chunks[0]['content'] if st.retrieval.knowledge_chunks else 'No knowledge loaded yet.', relevant_memories=st.retrieval.memory_chunks[0]['content'] if st.retrieval.memory_chunks else 'No memories available.', page_context=page_context or 'unknown', user_info=user_info, persona=_audience_persona(config, user_info), api_catalog=_scoped_api_catalog(config, user_info), navigation_routes=_scoped_navigation_routes(config, user_info), domain_topics=config.get('domain_topics'), instance_config={**config, 'persona': _audience_persona(config, user_info), 'api_catalog': _scoped_api_catalog(config, user_info)}, conversation_id=conversation_id, instance_id=instance_id, process_mode=process_mode)
    _domain_ctx_enabled = config.get('domain_context_enabled', None) if config.get('domain_context_enabled') is not None else settings.PULSE_DOMAIN_CONTEXT_ENABLED
    if _domain_ctx_enabled:
        try:
            if runner.domain_context_assembler is not None:
                _domain_context = await runner.domain_context_assembler().assemble(app_identifier=config.get('app_identifier'))
                if _domain_context:
                    system_prompt = f'{system_prompt}\n{_domain_context}'
        except Exception:
            logger.warning(f'[{turn_id[:8]}] Domain context assembly failed', exc_info=True)
    draft_tools = runner._draft_tools if runner.executor is not None else None
    draft_tools = _filter_draft_tools(
        draft_tools, st.user_message, st.salience.domain, process_mode,
        conversation_history,
    )
    _discuss_turn = st.discuss_ctx
    if _discuss_turn:
        draft_tools = None
    _is_platform_zone = st.intent_resolution is None or st.intent_resolution.zone in ('platform', 'off_limits')
    if _discuss_turn:
        # Chat proposes; Agent applies. The reply itself becomes the typed
        # ``plan_revision`` question (runner_s6) — a bare "apply / yes" next
        # turn hands it to the Tasks panel without another LLM call.
        _plan_title = str((st.plan_revision_ref or {}).get('title') or '').strip()
        _plan_line = f' The plan under discussion: "{_plan_title}".' if _plan_title else ''
        system_prompt = f'{system_prompt}\n\nAGENT DISCUSS MODE — follow exactly:\n- The user is refining or discussing an existing Agent plan in Chat.{_plan_line}\n- Reply in prose only: one improved brief and/or a short numbered step list. Your reply IS the proposed revision — write it so it can be applied verbatim.\n- Keep the step list multi-step when the brief has multiple actions (compute, validate, compare rates, report, do-not-commit). Never collapse to a single vague step.\n- Do NOT call any tools (no invoke_skill, call_host_api, resolve_entity, aggregate_entity, plan_task, edit_plan, approve_plan, web_research, export_document).\n- Do NOT re-run the prior analysis or fetch live data.\n- Do NOT navigate the user to an app (Payroll, People, …).\n- Do NOT claim the plan was changed. End with one line: the user can say "apply" to take this revision to Agent, where they review the diff and approve it.\n'
    elif draft_tools and _is_platform_zone:
        from ai.engine.cognition.turn.handoff_agent import chat_grounding_rules_block
        system_prompt = f'{system_prompt}\n\n{chat_grounding_rules_block(surface, process_mode=process_mode)}'
    from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver
    _resolved_user_message = AnaphoraResolver(st.wm).resolve(conversation_id, st.user_message)
    if str(process_mode or '') == 'plan':
        from ai.engine.cognition.turn.runner_util import plan_followup_context
        _plan_ctx = plan_followup_context(st.user_message, conversation_history)
        if _plan_ctx:
            # A short Plan reply answers the assistant's own question about the
            # earlier brief. Without the brief the draft asks what it refers to.
            _resolved_user_message = (
                f'{_plan_ctx}\n\n(Answer to your last question: {st.user_message})'
            )
    _wm_fragment = st.wm.to_prompt_fragment(conversation_id)
    if _wm_fragment:
        system_prompt = f'{system_prompt}\n\n{_wm_fragment}'
    _state_for_pack = state_ctx.state if state_ctx is not None else None
    _pref_constraints = ''
    if host_user_id:
        try:
            from asgiref.sync import sync_to_async as _pref_s2a
            _pref_constraints = await _pref_s2a(st.pref_store.to_prompt_constraints, thread_sensitive=True)(host_user_id)
        except Exception as _e:
            logger.warning('[GAP-4] preference read failed user=%s: %s', host_user_id, _e)
    if _pref_constraints:
        system_prompt = f'{system_prompt}\n\n{_pref_constraints}'
    _skill_terminology: dict[str, str] = {}
    _skill_router_fired = False
    if runner.db is not None:
        try:
            from ai.engine.skills.registry import SkillRegistry
            from ai.engine.skills.router import SkillRouter
            _registry = SkillRegistry(runner.db)
            _promoted_skills = await _registry.list_promoted(instance_id)
            _router = SkillRouter()
            _matched_skills = _router.find_matching_skills(st.user_message, _promoted_skills)
            _skill_terminology = _router.get_terminology(_matched_skills)
            _skill_router_fired = bool(_matched_skills)
        except Exception:
            logger.warning('Skill routing failed; continuing without terminology injection', exc_info=True)
    _signal(ledger, 'skill_router', _skill_router_fired, matched=len(_skill_terminology))
    if _skill_terminology:
        from ai.engine.knowledge.terminology import TerminologyResolver
        system_prompt = TerminologyResolver().inject(system_prompt, _skill_terminology)
    if (
        str(process_mode or '') != 'plan'
        and st.intent_resolution is not None
        and st.intent_resolution.action == 'answer'
        and st.intent_resolution.candidates
    ):
        from ai.engine.cognition.turn.intent import _endpoint_to_domain_phrase
        _top_cand = st.intent_resolution.candidates[0]
        _phrases = [_endpoint_to_domain_phrase(c.name) for c in st.intent_resolution.candidates[:3]]
        _delivery_phrase = _DELIVERY_INJECTION.get(st.intent_resolution.delivery, _DELIVERY_INJECTION['explain'])
        system_prompt = f'{system_prompt}\n\nINTENT (already recognised): the user is asking about "{_phrases[0]}" and wants to {_delivery_phrase}. The intent resolver matched `{_top_cand.name}` with confidence {_top_cand.confidence:.2f}. Call `{_top_cand.name}` via call_host_api right away to answer from real data in the system — do NOT give a generic or textbook answer, and do NOT re-ask what the user means. Synthesise the result into a direct answer: do not dump the raw rows, name the material facts and cite real values inline, and only render a table if the user asked to see everything.'
    from ai.engine.llm.router import get_model_for_task as _get_model_for_task
    _draft_model = model
    if not _draft_model and st.salience.route == 'deep':
        _draft_model = _get_model_for_task('reason')
        ledger.reason_escalation = {'trigger': 'deep_salience', 'from_model': '', 'to_model': _draft_model, 'verdict_before': None, 'verdict_after': None}
    with stage('draft'):
        from ai.engine.cognition.context_pack import build_context_pack
        _draft_lang = ''
        if state_ctx is not None:
            _draft_lang = str(getattr(state_ctx.state, 'language', '') or '')
        draft_pack = build_context_pack(_state_for_pack, surface='chat', stage='draft', user_info=user_info, instance_config=config, conversation_history=conversation_history, retrieval=st.retrieval, language=_draft_lang, task_body=system_prompt, include_state=True, include_knowledge=False, include_memory=False, include_history=False)
        from ai.engine.cognition.turn.force_tool import draft_force_kwargs, ensure_forced_call
        _fn_names = {str((d.get('function') or {}).get('name') or '') for d in draft_tools or [] if isinstance(d, dict)}
        _fn_names.discard('')
        st.draft = await draft_witness.draft(instance_id=instance_id, conversation_id=conversation_id, user_message=_resolved_user_message, system_prompt='', conversation_history=conversation_history, instance_config=instance_config, user_info=user_info, budget_tracker=budget, model=_draft_model, tools=draft_tools, temperature=temperature, pack=draft_pack, **draft_force_kwargs(st.intent_resolution, _fn_names))
        st.draft = ensure_forced_call(st.draft, st.intent_resolution, turn_id, _fn_names)
        # I2: If open_question_confirm injected a forced_tool_call, inject it now
        if st.forced_tool_call and "call_host_api" in _fn_names:
            calls = list(getattr(st.draft, "tool_calls", None) or [])
            calls.append(st.forced_tool_call)
            import dataclasses as _dc_inject
            st.draft = _dc_inject.replace(st.draft, tool_calls=calls, text="")
    import dataclasses as _dc
    import json as _json
    from ai.engine.cognition.turn.runner_util import (
        ensure_plan_review_text,
        plan_accept_brief,
    )
    _accept_brief = plan_accept_brief(st.user_message, conversation_history)
    if _accept_brief and "plan_task" in _fn_names:
        _calls = list(getattr(st.draft, "tool_calls", None) or [])
        if not any(
            ((c.get("function") or {}).get("name") == "plan_task")
            for c in _calls if isinstance(c, dict)
        ):
            _calls.append({
                "id": "plan_accept",
                "type": "function",
                "function": {
                    "name": "plan_task",
                    "arguments": _json.dumps({"brief": _accept_brief}),
                },
            })
            st.draft = _dc.replace(st.draft, tool_calls=_calls)
    if str(process_mode or '') == 'plan':
        if _accept_brief:
            # Acceptance creates exactly one reviewable task. Never let a
            # model-emitted read/search accompany plan_task on this turn.
            _plan_calls = [
                c for c in (getattr(st.draft, "tool_calls", None) or [])
                if isinstance(c, dict)
                and ((c.get("function") or {}).get("name") == "plan_task")
            ]
            st.draft = _dc.replace(st.draft, tool_calls=_plan_calls, text="")
        else:
            # Before acceptance, Plan is text-only and must always show a
            # numbered plan. Questions may follow the plan, never replace it.
            st.draft = _dc.replace(
                st.draft,
                text=ensure_plan_review_text(
                    getattr(st.draft, "text", "") or "",
                    _resolved_user_message,
                ),
                tool_calls=[],
            )
    from ai.engine.cognition.dialogue.fallback import FallbackHandler
    _fallback_text = FallbackHandler().handle(st.user_message, st.draft.text)
    if _fallback_text != st.draft.text and (not st.draft.tool_calls):
        st.draft = _dc.replace(st.draft, text=_fallback_text, confidence=0.4, model_used=st.draft.model_used or 'fallback')
    ledger.draft = st.draft
    st.total_tokens += st.draft.tokens_used
    st.total_llm_calls += 1
    ledger.prompt_tokens += st.draft.prompt_tokens
    ledger.completion_tokens += st.draft.completion_tokens
    ledger.model_used = st.draft.model_used or ledger.model_used
    if budget is not None:
        await budget.consume(st.draft.tokens_used)
    s3_latency = (time.monotonic() - s3_start) * 1000
    await _broadcast_run(instance_id, 'run.step.completed', {'run_id': turn_id, 'stage': 's3_draft', 'stage_index': 2, 'latency_ms': s3_latency})
    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'draft', 2, {'text_len': len(st.draft.text), 'tool_calls': len(st.draft.tool_calls), 'confidence': st.draft.confidence}, s3_latency, tokens_used=st.draft.tokens_used, model_used=st.draft.model_used, verdict='pass')
    s4_start = time.monotonic()
    await _broadcast_run(instance_id, 'run.step.started', {'run_id': turn_id, 'stage': 's4_critic', 'stage_index': 3})
    from ai.engine.cognition.turn.critic import CriticWitness
    critic_witness = CriticWitness()
    with stage('critic'):
        st.critic = await critic_witness.review(st.draft, st.retrieval, enable_llm_critic=True, instance_id=instance_id, conversation_id=conversation_id, user_message=_resolved_user_message, salience=st.salience, user_info=user_info, instance_config=instance_config, conversation_history=conversation_history, state=state_ctx.state if state_ctx is not None else None)
    if st.critic.verdict == 'knowledge_gap':
        _reason_configured = bool((settings.LLM_REASON_MODEL or settings.LLM_ESCALATION_MODEL or '').strip())
        escalation_model = _get_model_for_task('reason') if _reason_configured else ''
        current_model = st.draft.model_used or ''
        if escalation_model and escalation_model != current_model:
            logger.info('[%s] knowledge_gap detected — escalating to reason lane (%s)', turn_id[:8], escalation_model)
            with stage('escalate'):
                st.draft = await draft_witness.draft(instance_id=instance_id, conversation_id=conversation_id, user_message=_resolved_user_message, system_prompt='', conversation_history=conversation_history, instance_config=instance_config, user_info=user_info, budget_tracker=budget, model=escalation_model, tools=draft_tools, temperature=temperature, pack=draft_pack, **draft_force_kwargs(st.intent_resolution, _fn_names))
                st.draft = ensure_forced_call(st.draft, st.intent_resolution, turn_id, _fn_names)
                st.total_tokens += st.draft.tokens_used
                st.total_llm_calls += 1
                _fallback_text = FallbackHandler().handle(_resolved_user_message, st.draft.text)
                if _fallback_text != st.draft.text and (not st.draft.tool_calls):
                    import dataclasses as _dc
                    st.draft = _dc.replace(st.draft, text=_fallback_text, confidence=0.4)
                st.critic = await critic_witness.review(st.draft, st.retrieval, enable_llm_critic=False, instance_id=instance_id, conversation_id=conversation_id, user_message=_resolved_user_message, salience=st.salience)
            ledger.reason_escalation = {'trigger': 'knowledge_gap', 'from_model': current_model, 'to_model': escalation_model, 'verdict_before': 'knowledge_gap', 'verdict_after': st.critic.verdict}
            await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'escalation', 4, ledger.reason_escalation, (time.monotonic() - s4_start) * 1000, model_used=escalation_model, verdict=st.critic.verdict, flags=['knowledge_gap'])
        else:
            from ai.engine.cognition.dialogue.fallback import HonestUncertaintyHandler
            honest_text = HonestUncertaintyHandler().handle(_resolved_user_message, st.critic.partial_knowledge)
            logger.info('[%s] knowledge_gap — no reason model, returning honest uncertainty', turn_id[:8])
            import dataclasses as _dc
            st.draft = _dc.replace(st.draft, text=honest_text, confidence=0.2, model_used='honest_uncertainty')
            st.critic = _dc.replace(st.critic, verdict='pass_with_flag', flags=['knowledge_gap'])
    if st.critic.verdict == 'veto':
        _veto_msg = (st.critic.veto_reason or '').strip() or 'This action was blocked pending review.'
        logger.warning('[%s] S4 veto (%s) — blocking %d tool call(s): %s', turn_id[:8], ', '.join(st.critic.flags) or 'unspecified', len(st.draft.tool_calls or []), _veto_msg[:160])
        st.draft = _dc.replace(st.draft, tool_calls=[], text=_veto_msg)
    ledger.critic = st.critic
    s4_latency = (time.monotonic() - s4_start) * 1000
    await _broadcast_run(instance_id, 'run.step.completed', {'run_id': turn_id, 'stage': 's4_critic', 'stage_index': 3, 'latency_ms': s4_latency})
    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'critic', 3, {'verdict': st.critic.verdict, 'flags': st.critic.flags, 'rewritten': bool(st.critic.rewritten_text), 'llm_critic_enabled': True}, s4_latency, verdict=st.critic.verdict, flags=st.critic.flags)
    _draft_text_was_empty = not (st.critic.rewritten_text or st.draft.text or '').strip()
    st.final_text = st.critic.rewritten_text if st.critic.rewritten_text else st.draft.text
    _weather_force_fired = False
    if runner.executor is not None and _is_wq(_resolved_user_message) and (not _is_text_transform_request(_resolved_user_message)) and (st.critic.verdict != 'veto'):
        _has_weather_call = any(((tc.get('function') or {}).get('name') == 'web_research' for tc in st.draft.tool_calls or []))
        if not _has_weather_call:
            _weather_force_fired = True
            import json as _json
            with stage('weather_normalize'):
                _place = await _normalize_weather_question(instance_id=instance_id, conversation_id=conversation_id, question=_resolved_user_message, conversation_history=conversation_history, model=model, weather_extractor=runner.weather_extractor, user_info=user_info, instance_config=instance_config, state=state_ctx.state if state_ctx is not None else None)
            st.draft = _dc.replace(st.draft, tool_calls=[{'id': f'call_weather_{turn_id[:8]}', 'function': {'name': 'web_research', 'arguments': _json.dumps({'query': f'weather in {_place}'})}}], text='', confidence=0.6)
            st.final_text = ''
            _draft_text_was_empty = True
            ledger.intent_zone = 'real_time'
            logger.info('[WEATHER-DETERMINISTIC] Forced web_research for %r -> %r', _resolved_user_message, _place)
    _signal(ledger, 'weather_force', _weather_force_fired)
    _ess_force_before = list(getattr(st.draft, 'tool_calls', None) or [])
    try:
        from ai.engine.cognition.turn.force_tool import ensure_forced_call
        from ai.engine.cognition.turn.understand import understand_mode
        if understand_mode() != 'v21' and (not _ess_force_before):
            st.draft = ensure_forced_call(st.draft, st.intent_resolution, turn_id, _fn_names)
            if not (getattr(st.draft, 'text', None) or '').strip() and st.draft.tool_calls:
                st.final_text, _draft_text_was_empty = ('', True)
    except Exception:
        logger.debug('ESS self-read force skipped', exc_info=True)
    _signal(ledger, 'ess_self_read_force', list(getattr(st.draft, 'tool_calls', None) or []) != _ess_force_before)
    s5_start = time.monotonic()
    await _broadcast_run(instance_id, 'run.step.started', {'run_id': turn_id, 'stage': 's5_execute', 'stage_index': 4})
    from ai.engine.cognition.turn.execute import ExecuteWitness
    from ai.engine.agent.guardrails import build_default_pipeline
    hook_pipeline = build_default_pipeline()
    hook_ctx_defaults = {'instance_id': instance_id, 'conversation_id': conversation_id, 'host_user_id': host_user_id, 'run_id': turn_id, 'agent_role': 'orchestrator', 'is_worker': False, 'instance_config': instance_config, 'user_message': _resolved_user_message, 'process_mode': process_mode, 'surface': surface}
    execute_witness = ExecuteWitness(executor=runner.executor, hook_pipeline=hook_pipeline, hook_ctx_defaults=hook_ctx_defaults, run_id=turn_id, instance_id=instance_id, knowledge_store=runner.knowledge_store)
    st.execution = await execute_witness.execute(text=st.final_text, tool_calls=st.draft.tool_calls, stream_callback=stream_callback, progress_callback=progress_callback)
    ledger.execution = st.execution
    s5_latency = st.execution.execution_latency_ms
    await _broadcast_run(instance_id, 'run.step.completed', {'run_id': turn_id, 'stage': 's5_execute', 'stage_index': 4, 'latency_ms': s5_latency})
    await runner._write_ledger_row(turn_id, instance_id, conversation_id, host_user_id, 'execution', 4, {'streamed': st.execution.streamed, 'tools_executed': len(st.execution.completed_tools), 'per_tool_latency_ms': st.execution.per_tool_latency_ms}, s5_latency, verdict='pass')
    try:
        from ai.engine.memory.working import update_focus_from_resolve_results
        update_focus_from_resolve_results(st.wm, conversation_id, st.execution.completed_tools)
    except Exception:
        logger.debug('[%s] resolve_entity focus update skipped', turn_id[:8], exc_info=True)
    try:
        from ai.engine.agent.tools import stamp_compensation_deny_on_soft_empty
        _caps = frozenset()
        if runner.executor is not None and hasattr(runner.executor, 'user_capabilities'):
            try:
                _caps = frozenset(runner.executor.user_capabilities() or ())
            except Exception:
                _caps = frozenset()
        st.execution.completed_tools = stamp_compensation_deny_on_soft_empty(st.execution.completed_tools, user_message=_resolved_user_message, caps=_caps)
    except Exception:
        logger.debug('B5 compensation soft-empty stamp skipped', exc_info=True)
    from ai.engine.cognition.turn.ess_read import empty_history_misread
    from ai.engine.cognition.turn.catalog_render import honest_unsummarized_fallback, should_honest_fallback
    from ai.engine.cognition.turn.runner_util import (
        plan_created_receipt,
        plan_task_error_receipt,
    )
    from ai.engine.cognition.turn.zero_llm import is_empty_payslip_tool_result, render_empty_payslip_answer
    _synth = None
    _plan_receipt = plan_created_receipt(st.execution.completed_tools)
    _plan_error = plan_task_error_receipt(st.execution.completed_tools)
    _ess_empty = empty_history_misread(st.execution.completed_tools, user_message=_resolved_user_message)
    if _plan_receipt:
        # plan_task already returns a grounded product receipt. Synthesizing
        # and verifying that one line added multiple LLM calls and could leave
        # the UI spinning on provider retries after the task already existed.
        st.final_text = _plan_receipt
        _synth = None
    elif _plan_error:
        st.final_text = _plan_error
        _synth = None
    elif is_empty_payslip_tool_result(st.execution.completed_tools):
        st.final_text = render_empty_payslip_answer(_resolved_user_message)
        _synth = None
        if state_ctx is not None and getattr(state_ctx, 'state', None) is not None:
            rows = list(state_ctx.state.last_results or [])
            rows.append({'tool': 'call_host_api', 'api': 'list_my_payslips', 'digest': 'call_host_api list_my_payslips: count=0'})
            state_ctx.state.last_results = rows
    else:
        _catalog_render = None
        try:
            from ai.engine.cognition.plan.export_bind import render_bound_catalog_read
            from ai.engine.cognition.turn.grounding import ungrounded_numbers
            from ai.engine.cognition.turn.navigation import detect_lang as _detect_lang
            _lang = 'ar' if _detect_lang(_resolved_user_message) == 'ar' else 'en'
            for _item in st.execution.completed_tools or []:
                if not isinstance(_item, dict):
                    continue
                if str(_item.get('tool_name') or '') != 'call_host_api':
                    continue
                _args = _item.get('tool_args') if isinstance(_item.get('tool_args'), dict) else {}
                _api = str(_args.get('api_name') or _args.get('name') or _args.get('api') or '')
                if not _api:
                    continue
                _candidate = render_bound_catalog_read(_item, _api, _lang)
                if not _candidate:
                    continue
                _payload = _item.get('result')
                if ungrounded_numbers(_candidate, [_payload]):
                    logger.warning('[%s] Catalog render dropped — ungrounded numerals api=%s', turn_id[:8], _api)
                    continue
                _catalog_render = _candidate
                break
        except Exception:
            _catalog_render = None
        # When a Word/Excel export landed, the download receipt is the answer —
        # do not let a leave/loan catalog dump become the chat headline.
        _export_landed = False
        for _item in st.execution.completed_tools or []:
            if not isinstance(_item, dict):
                continue
            if str(_item.get('tool_name') or '') != 'export_document':
                continue
            _res = _item.get('result')
            if isinstance(_res, str):
                try:
                    import json as _json
                    _res = _json.loads(_res)
                except (TypeError, ValueError):
                    _res = None
            if isinstance(_res, dict) and _res.get('action') == 'download' and not _res.get('error'):
                _export_landed = True
                break
        if _catalog_render and (not _wants_visual(_resolved_user_message)) and (not _export_landed):
            st.final_text = _catalog_render
            _synth = None
        elif _ess_empty is not None and (not _export_landed):
            st.final_text = str(_ess_empty.get('text') or '')
            _synth = None
        else:
            with stage('synthesis'):
                _synth = await _synthesize_tool_results(instance_id=instance_id, conversation_id=conversation_id, user_message=_resolved_user_message, completed_tools=st.execution.completed_tools, draft_text=st.final_text, model=st.draft.model_used or model, delivery=st.intent_resolution.delivery if st.intent_resolution else 'explain', envelope_synthesizer=runner.envelope_synthesizer, stream_callback=stream_callback, progress_callback=progress_callback, user_info=user_info, instance_config=instance_config, state=state_ctx.state if state_ctx is not None else None)
    if _synth and _synth.get('text'):
        st.final_text = _synth['text']
        st.total_tokens += int(_synth.get('tokens') or 0)
        st.total_llm_calls += 1
        logger.info('[%s] Tool-result synthesis — final answer written from %d tool result(s) (%d tokens)', turn_id[:8], len(st.execution.completed_tools), int(_synth.get('tokens') or 0))
        if _synth.get('is_clarification'):
            _clarif_msg = _synth.get('clarification_user_message') or _resolved_user_message
            _is_wq2 = runner._is_weather_query
            if _is_wq2(_clarif_msg) and (not st.is_weather_rewrite_turn):
                st.wm.set_focus(conversation_id, _clarif_msg, 'pending_weather')
                logger.info('[WEATHER-FT] Stored pending_weather intent for conv %s: %r', conversation_id[:8], _clarif_msg)
    elif should_honest_fallback(st.final_text, st.execution.completed_tools):
        # Invariant: fires only when no render exists. A blanked draft
        # (forced call) followed by a catalog / empty-host render is an answer.
        from ai.engine.cognition.turn.navigation import detect_lang as _detect_lang_fb
        _fb_lang = 'ar' if _detect_lang_fb(_resolved_user_message) == 'ar' else 'en'
        st.final_text = honest_unsummarized_fallback(_fb_lang)
        logger.info('[%s] Tool-only response — honest fallback (no render, draft_empty=%s, %d tools executed)', turn_id[:8], _draft_text_was_empty, len(st.execution.completed_tools))
    if (
        settings.PULSE_VERIFY_ENABLED
        and st.execution.completed_tools
        and st.final_text
        and not _plan_receipt
    ):
        try:
            from ai.engine.cognition.turn.verify import VerificationWitness
            from ai.engine.llm.router import model_for_profile
            _vw = VerificationWitness()
            with stage('verify'):
                _vr = await _vw.verify(answer=st.final_text, tool_results=st.execution.completed_tools, user_message=_resolved_user_message, instance_id=instance_id, conversation_id=conversation_id, model=model_for_profile('verify') or st.draft.model_used or model, user_info=user_info, instance_config=instance_config, state=state_ctx.state if state_ctx is not None else None)
            if not _vr.passed and _vr.corrected_text:
                st.final_text = _vr.corrected_text
                logger.info('[%s] Verification corrected answer: unsupported=%s', turn_id[:8], _vr.unsupported_claims)
            st.total_tokens += _vr.tokens_used
            st.total_llm_calls += 1
            ledger.verification_passed = _vr.passed
            ledger.verification_unsupported = _vr.unsupported_claims
            ledger.verification_error = _vr.error
        except Exception as e:
            logger.warning('[%s] Verification step failed', turn_id[:8], exc_info=True)
            ledger.verification_passed = False
            ledger.verification_error = str(e)
    if not st.execution.completed_tools and st.retrieval.knowledge_chunks:
        st.execution.completed_tools.append({'tool_name': 'search_knowledge', 'tool_args': {'query': st.user_message}, 'result': {'count': len(st.retrieval.knowledge_chunks)}, 'error': None, 'latency_ms': st.s2_latency})
    st.synth = _synth

