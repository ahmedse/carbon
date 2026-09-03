"""TurnPipelineRunner — orchestrates the six-witness pipeline for one turn.

BE-01-5: Spine is the default path. Runs S1→S2→S3→S4→S5→S6 sequentially,
writing one TurnLedgerRow per stage. PulseAgent.think() has been deleted.
"""
import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.cognition.turn.witnesses import (
    TurnLedger,
)

logger = logging.getLogger("pulse.cognition.turn.runner")

# Lazy import — avoids circular dependency with notifier
broadcast_run_event = None


# ── GAP-M7: capability-tool salience guard ────────────────────────────────

_CAPABILITY_QUERY_PATTERN = re.compile(
    r"\b(?:"
    r"what can you do|"
    r"what do you have access to|"
    r"what features|"
    r"show me capabilities|"
    r"your capabilities|"
    r"what are you able to do|"
    r"what can i use"
    r")\b",
    re.IGNORECASE,
)


def _is_capability_query(text: str) -> bool:
    """True if the user explicitly asks about capabilities/access (regex)."""
    if not text:
        return False
    return bool(_CAPABILITY_QUERY_PATTERN.search(text))


def _filter_draft_tools(
    draft_tools: list[dict] | None,
    user_message: str,
    salience_domain: str,
) -> list[dict] | None:
    """Exclude ``list_my_capabilities`` unless the user explicitly asked about
    capabilities/access or the turn is an identity-domain turn (GAP-M7)."""
    if (
        draft_tools
        and not _is_capability_query(user_message)
        and salience_domain != "identity"
    ):
        return [
            d for d in draft_tools
            if d.get("function", {}).get("name") != "list_my_capabilities"
        ]
    return draft_tools


#: Spine static tools ALWAYS exposed to the chat planner. Registry plugins
#: contribute the rest via ``chat_tool_names()`` (G-C: freeze the spine, grow
#: the periphery — new chat tools need zero edits to this module).
_CHAT_STATIC_TOOLS = frozenset({
    "search_knowledge", "get_entity_details",
    "learn_fact", "forget_fact",
    # call_host_api is the ONLY way the chat planner reaches live host data
    # (list_emission_factors, get_calculation_summary, …). The system prompt's
    # "Available Host API Endpoints" section tells the model to call these via
    # call_host_api, so it MUST be in the chat tool set — otherwise the model
    # falls back to search_knowledge (KG-only) or hallucinates the endpoint
    # names as raw tool calls ("Unknown tool: get_calculation_summary").
    "call_host_api",
})


async def _write_trajectory_own_session(run_id: str) -> None:
    """Write the trajectory on a DEDICATED session (fire-and-forget safe).

    Must not reuse the turn session: the caller may close it while this
    background task is still running, which triggers an asyncpg
    "another operation is in progress" race (seen in evals, where the
    harness closes the session immediately after the turn).
    """
    from ai.store import get_store
    from ai.engine.cognition.trajectory import write_trajectory

    factory = get_store().get_session_factory()
    async with factory() as traj_db:
        await write_trajectory(run_id, traj_db)


def _render_tool_results_for_synthesis(
    completed_tools: list[dict],
    max_chars: int = 20000,
) -> str:
    """Render executed tool results as readable JSON for the synthesis LLM.

    Unwraps the host envelope ``{"status_code": 200, "data": {...}}`` and
    surfaces the inner payload, capping at ``max_chars`` to bound token cost.
    List payloads record their total row count so the model can still answer
    "how many" even when the rendered rows are truncated.
    """
    import json as _json

    sections: list[str] = []
    used = 0
    for tr in completed_tools:
        name = tr.get("tool_name", "unknown")
        raw = tr.get("result")

        data = raw
        if isinstance(raw, str):
            try:
                data = _json.loads(raw)
            except (TypeError, ValueError):
                data = raw

        # Unwrap the host executor envelope.
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]

        list_payload = None
        list_key = None
        if isinstance(data, dict):
            for key in ("results", "items", "rows"):
                if key in data and isinstance(data[key], list):
                    list_payload = data[key]
                    list_key = key
                    break

        header = f"### {name}\n"
        if list_payload is not None:
            header += f"(total rows: {len(list_payload)})\n"
            body = _json.dumps(list_payload, ensure_ascii=False, default=str)
        else:
            body = _json.dumps(data, ensure_ascii=False, indent=2, default=str)

        section = header + body
        if used + len(section) > max_chars:
            remaining = max_chars - used
            section = section[:remaining] + "\n…(truncated)"
        sections.append(section)
        used += len(section)
        if used >= max_chars:
            break

    return "\n\n".join(sections)


# Delivery (cognitive-intent) axis — how the user wants the answer DELIVERED,
# distinct from WHICH endpoint. Maps the intent classifier's `delivery` value
# to (a) the S3 directive phrase and (b) the GAP-W9 synthesis guidance.
_DELIVERY_INJECTION = {
    "list": "see the full list of records",
    "lookup": "find one specific value",
    "explain": "understand what this is, how it is used, and why it matters",
    "analyze": "get insight — patterns, extremes, and what drives it",
    "compare": "compare the relevant entries side by side",
    "summarize": "get a high-level summary",
}

_DELIVERY_SYNTHESIS = {
    "list": (
        "The user wants the complete record set — present every row in a clean "
        "Markdown table (meaningful columns only) and add a chart if the values "
        "are comparable."
    ),
    "lookup": (
        "The user wants one specific value — answer with that value directly, "
        "bold it, and keep surrounding detail minimal."
    ),
    "explain": (
        "The user wants to UNDERSTAND this dataset, not just see rows. Lead "
        "with what it IS and how it is used, group it meaningfully (by "
        "category/scope), name the notable entries and what they mean, and "
        "present the data as a Markdown table PLUS a Mermaid chart so it is "
        "both readable and visual. End with one natural next step."
    ),
    "analyze": (
        "The user wants insight — surface the extremes (highest/lowest), the "
        "groupings, and patterns. Lead with the finding, then support it with "
        "a Markdown table and a Mermaid chart."
    ),
    "compare": (
        "The user wants a side-by-side comparison — contrast the entries on the "
        "dimensions that matter using a Markdown table and a Mermaid bar chart."
    ),
    "summarize": (
        "The user wants a roll-up — give headline numbers, a compact table and "
        "chart of the main groups, no exhaustive list."
    ),
}


async def _synthesize_tool_results(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    completed_tools: list[dict],
    draft_text: str,
    model: str | None = None,
    delivery: str = "explain",
) -> dict | None:
    """Ask the LLM to write a grounded final answer from executed tool results.

    Fires only when tools returned usable data AND the draft prose is empty or
    a short "promise to fetch" (the common tool-only turn where the model
    writes "I'll fetch …" and the fetched data is otherwise discarded).

    Returns ``{"text", "tokens", "model"}`` on success, or ``None`` when
    synthesis is unnecessary or the call fails (callers keep the original).
    """
    usable: list[dict] = []
    for tr in completed_tools or []:
        if tr.get("error"):
            continue
        if tr.get("requires_confirmation"):
            continue
        if tr.get("result") is None:
            continue
        usable.append(tr)

    if not usable:
        return None

    stripped = (draft_text or "").strip()
    # A substantial prose answer already exists — don't re-synthesize.
    if len(stripped) >= 300:
        return None

    results_text = _render_tool_results_for_synthesis(usable)
    if not results_text.strip():
        return None

    from ai.engine.llm.router import route_chat

    delivery_guide = _DELIVERY_SYNTHESIS.get(delivery or "explain", _DELIVERY_SYNTHESIS["explain"])
    system = (
        "You are finalising an answer for a data-platform assistant. Write the "
        "final reply to the user's question using ONLY the tool results below.\n"
        f"Delivery intent: {delivery_guide}\n"
        "SCOPING (critical): answer EXACTLY what the user asked. If the user's "
        "question names a specific entity — a module, branch, scope, table, "
        "product, or other named item — scope the entire answer to THAT entity "
        "only: filter the tool results down to it and do NOT enumerate, roll "
        "up, table, or chart the other entities. Only when the user asks for "
        "an overview, a comparison, or 'all' should you show the full "
        "breakdown. Never answer 'about the whole organisation' when the user "
        "named one branch.\n"
        "FORMAT — rich, publication-grade: open with a **bold one-line "
        "takeaway**; if there are 3+ records, ALWAYS include a Markdown table "
        "of the meaningful columns; if the records carry comparable numbers, "
        "ALSO emit a Mermaid chart (```mermaid pie``` for proportions, "
        "```mermaid xychart-beta``` with a `bar` series for ranking/magnitude "
        "and `line` for a trend). Mermaid line rules (critical): open the "
        "```mermaid fence on its OWN line after a blank line, close ``` on its "
        "own line, and put every directive on its own line — never inline the "
        "fence after prose or collapse the chart to one line. Use ## / ### "
        "headings, **bold** key figures "
        "and field names, and close with 2-4 “Key takeaways” as a bold-lead "
        "bullet list. State actual values — never invent numbers. Omit verbose "
        "metadata (raw source strings, internal ids, tags). Do not mention "
        "tools, API calls, fetching, or that you 'found' the data. If the data "
        "has no matching rows, say so plainly."
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"synthesis-{conversation_id}",
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"User's question: {user_message}\n\n"
                        f"Tool results (JSON):\n{results_text}"
                    ),
                },
            ],
            temperature=0.3,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("Tool-result synthesis LLM call failed", exc_info=True)
        return None

    synthesized = (result.get("content") or "").strip()
    if not synthesized:
        return None

    tokens = int(result.get("input_tokens", 0) or 0) + int(result.get("output_tokens", 0) or 0)
    return {"text": synthesized, "tokens": tokens, "model": result.get("model", "")}


class TurnPipelineRunner:
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
    ):
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.executor = executor
        self.db = db
        # Curated tool set exposed to the S3 planner when an executor is
        # wired. Mutation/confirmation tools (create_dq_rule) plus read tools
        # that ground answers, including call_host_api so the planner can reach
        # the live host endpoints listed in the system prompt.
        self._draft_tools: list[dict] | None = None
        if executor is not None:
            try:
                from ai.engine.agent.tools import get_tool_definitions
                from ai.engine.agent.plugins import chat_tool_names

                # Chat-visible tool set = spine static tools ∪ registry plugins
                # that opt in (chat_visible=True). New tools arrive by adding a
                # plugin + registering it — zero edits to this allow-list (G-C).
                allow = _CHAT_STATIC_TOOLS | chat_tool_names()
                self._draft_tools = [
                    d for d in get_tool_definitions()
                    if d.get("function", {}).get("name") in allow
                ]
            except Exception:  # noqa: BLE001 - tools are best-effort, never fatal
                logger.warning("Could not load draft tool definitions", exc_info=True)
                self._draft_tools = None

    async def run(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None = None,
        page_context: str = "",
        conversation_history: list[dict] | None = None,
        instance_config: dict | None = None,
        user_info: dict | None = None,
        progress_callback=None,
        stream_callback=None,
        model: str | None = None,
        # Phase 22-A — per-user default chat temperature (0.0-2.0); None
        # keeps the draft witness's built-in default (0.3).
        temperature: float | None = None,
    ) -> tuple:
        """Execute one turn. Returns (AgentResponse, TurnLedger)."""
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor

        settings = get_settings()
        turn_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        t0 = time.monotonic()

        ledger = TurnLedger(
            turn_id=turn_id,
            instance_id=instance_id,
            host_user_id=host_user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            created_at=created_at,
        )

        # ── P3.4: Per-run token budget ────────────────────────────────────
        from ai.engine.agent.budget import BudgetTracker
        budget = None
        if self.db is not None:
            budget = BudgetTracker(
                run_id=turn_id,
                total_budget=settings.RUN_TOKEN_BUDGET_DEFAULT,
                db_session=self.db,
            )

        # ── Six-witness pipeline (always active) ──────────────────────────
        total_tokens = 0
        total_llm_calls = 0
        logger.info(f"[{turn_id[:8]}] Pipeline start  user={host_user_id}'")

        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run
        await _broadcast_run(instance_id, "run.started", {
            "run_id": turn_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "user_message": user_message,
        })

        # ── [GAP-M6] Pre-S1 pending-confirmation short-circuit ───────────
        # If the user is answering Pulse's own "shall I remember X?" with a
        # short affirmative, prepare the memory card directly — never route
        # "yes" through the LLM as a decontextualized query.
        try:
            from ai.engine.cognition.dialogue.pending_action import (
                get_pending_action_store,
            )
            _pending_store = get_pending_action_store()
            _pending = _pending_store.check_confirmation(conversation_id, user_message)
            if _pending and self.executor is not None and instance_id:
                from ai.engine.agent.tools import execute_learn_fact
                await execute_learn_fact(
                    fact=_pending["fact"],
                    category=_pending.get("category", "observation"),
                    instance_id=instance_id,
                    executor=self.executor,
                    conversation_id=conversation_id,
                )
                _pending_store.clear(conversation_id)

                _confirm_text = (
                    "Done — I've prepared a memory card for that. "
                    "Click confirm to save it permanently."
                )
                total_latency = (time.monotonic() - t0) * 1000
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    "final", 5,
                    {
                        "total_latency_ms": total_latency,
                        "total_tokens": 0,
                        "total_llm_calls": 0,
                        "pending_confirmation_shortcircuit": True,
                    },
                    total_latency, verdict="pass",
                )
                if self.db is not None:
                    await self.db.commit()

                ledger.final_response = _confirm_text[:500]
                ledger.total_latency_ms = total_latency

                response = AgentResponse(
                    text=_confirm_text,
                    sources_cited=[],
                    tools_used=[],
                    confidence=0.8,
                    total_tokens=0,
                    llm_calls=0,
                    model="",
                )
                await _broadcast_run(instance_id, "run.completed", {
                    "run_id": turn_id,
                    "total_latency_ms": total_latency,
                    "total_tokens": 0,
                    "total_llm_calls": 0,
                    "pending_confirmation_shortcircuit": True,
                })
                return response, ledger
        except Exception:  # noqa: BLE001 - memory hook must never block the turn
            logger.warning(
                "[%s] Pending-confirmation short-circuit failed; "
                "continuing normal pipeline",
                turn_id[:8], exc_info=True,
            )

        # S1 — Salience
        s1_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s1_salience",
            "stage_index": 0,
        })
        from ai.engine.cognition.turn.salience import SalienceWitness
        salience_witness = SalienceWitness()
        salience = await salience_witness.assess(user_message)
        ledger.salience = salience
        s1_latency = (time.monotonic() - s1_start) * 1000
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s1_salience",
            "stage_index": 0,
            "latency_ms": s1_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "salience", 0, {"domain": salience.domain, "route": salience.route, "weight": salience.weight},
            s1_latency, verdict="pass",
        )

        # [GAP-2] Extract named entity → update working memory
        # [GAP-4] Detect preference signals → update session preferences
        from ai.engine.cognition.dialogue.entity_extractor import EntityExtractor
        from ai.engine.memory.working import get_working_memory
        from ai.engine.learning.preferences import PreferenceClassifier, get_session_preference_store

        _wm = get_working_memory()
        _entity = EntityExtractor().extract(user_message)
        if _entity:
            _wm.set_focus(conversation_id, _entity.name, _entity.entity_type)
        _pref_store = get_session_preference_store()
        _pref_store.update(conversation_id, PreferenceClassifier().classify(user_message))

        # ── S1.5 — Intent Resolution (LLM-as-classifier, no local models) ──
        # Recognises which read-only endpoint the user is after, with a
        # confidence ladder that answers / disambiguates / clarifies. Falls
        # through silently on any failure — never blocks the turn.
        _intent_resolution = None
        if settings.INTENT_RESOLVER_ENABLED:
            try:
                from ai.engine.cognition.turn.intent import IntentResolver
                from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver
                _resolved_for_intent = AnaphoraResolver(_wm).resolve(
                    conversation_id, user_message
                )
                _intent_resolution = await IntentResolver().resolve(
                    user_message=_resolved_for_intent,
                    api_catalog=(instance_config or {}).get("api_catalog"),
                    conversation_history=conversation_history,
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    db=self.db,
                    model=settings.INTENT_RESOLVER_MODEL or None,
                    min_confidence=settings.INTENT_RESOLVER_MIN_CONFIDENCE,
                    ambiguity_gap=settings.INTENT_RESOLVER_AMBIGUITY_GAP,
                )
            except Exception:
                logger.warning(
                    "[%s] Intent resolution failed; continuing without it",
                    turn_id[:8], exc_info=True,
                )

        if _intent_resolution is not None:
            total_llm_calls += 1
            total_tokens += (
                _intent_resolution.input_tokens + _intent_resolution.output_tokens
            )
            await self._write_ledger_row(
                turn_id, instance_id, conversation_id, host_user_id,
                "intent", 0, {
                    "action": _intent_resolution.action,
                    "zone": _intent_resolution.zone,
                    "intent": _intent_resolution.intent,
                    "confidence": _intent_resolution.confidence,
                    "candidates": [
                        {"name": c.name, "confidence": c.confidence}
                        for c in _intent_resolution.candidates
                    ],
                },
                (time.monotonic() - s1_start) * 1000,
                tokens_used=_intent_resolution.input_tokens + _intent_resolution.output_tokens,
                model_used=_intent_resolution.model_used, verdict="pass",
            )
            # Thread the zone to the engine runtime so it can surface
            # provenance (metadata["intent_zone"]) to the frontend.
            ledger.intent_zone = _intent_resolution.zone

            # [S1.5-zone] Hard refuse — off_limits (jailbreak/PII/security) is a
            # GATE layered on top of any zone. Mirrors the clarify/disambiguate
            # shortcircuit exactly: a proper persisted assistant message, never
            # an HTTP error.
            if _intent_resolution.zone == "off_limits":
                _refuse_text = (
                    "I'm not able to help with that request. "
                    "If you have a question about your platform data, emissions, "
                    "or data quality, I'm here to help."
                )
                total_latency = (time.monotonic() - t0) * 1000
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    "final", 5,
                    {
                        "total_latency_ms": total_latency,
                        "total_tokens": total_tokens,
                        "total_llm_calls": total_llm_calls,
                        "intent_shortcircuit": "off_limits",
                    },
                    total_latency, verdict="pass",
                )
                if self.db is not None:
                    await self.db.commit()

                ledger.final_response = _refuse_text[:500]
                ledger.total_latency_ms = total_latency
                ledger.total_tokens = total_tokens
                ledger.total_llm_calls = total_llm_calls

                response = AgentResponse(
                    text=_refuse_text,
                    sources_cited=[],
                    tools_used=[],
                    confidence=0.7,
                    total_tokens=total_tokens,
                    llm_calls=total_llm_calls,
                    model="",
                    response_type="clarification",
                    confidence_label="medium",
                )
                await _broadcast_run(instance_id, "run.completed", {
                    "run_id": turn_id,
                    "total_latency_ms": total_latency,
                    "total_tokens": total_tokens,
                    "total_llm_calls": total_llm_calls,
                    "intent_shortcircuit": "off_limits",
                })
                return response, ledger

            # Confidence ladder short-circuits: ask / offer options instead of
            # guessing. These return before S2/S3 so no hallucinated tool runs.
            if _intent_resolution.action in ("clarify", "disambiguate"):
                if _intent_resolution.action == "clarify":
                    _short_text = _intent_resolution.clarification or (
                        "Could you clarify what you'd like me to look up?"
                    )
                else:
                    _opts = _intent_resolution.options or [
                        c.name for c in _intent_resolution.candidates[:3]
                    ]
                    _short_text = (
                        "I can look that up a few different ways — which do "
                        "you mean?\n" + "\n".join(f"- {o}" for o in _opts)
                    )
                total_latency = (time.monotonic() - t0) * 1000
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    "final", 5,
                    {
                        "total_latency_ms": total_latency,
                        "total_tokens": total_tokens,
                        "total_llm_calls": total_llm_calls,
                        "intent_shortcircuit": _intent_resolution.action,
                    },
                    total_latency, verdict="pass",
                )
                if self.db is not None:
                    await self.db.commit()

                ledger.final_response = _short_text[:500]
                ledger.total_latency_ms = total_latency
                ledger.total_tokens = total_tokens
                ledger.total_llm_calls = total_llm_calls

                response = AgentResponse(
                    text=_short_text,
                    sources_cited=[],
                    tools_used=[],
                    confidence=0.7,
                    total_tokens=total_tokens,
                    llm_calls=total_llm_calls,
                    model="",
                    response_type="clarification",
                    confidence_label="medium",
                )
                await _broadcast_run(instance_id, "run.completed", {
                    "run_id": turn_id,
                    "total_latency_ms": total_latency,
                    "total_tokens": total_tokens,
                    "total_llm_calls": total_llm_calls,
                    "intent_shortcircuit": _intent_resolution.action,
                })
                return response, ledger

        # S2 — Retrieval
        s2_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s2_retrieval",
            "stage_index": 1,
        })
        from ai.engine.cognition.turn.retrieve import RetrievalWitness
        retrieve_witness = RetrievalWitness(
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
        )
        retrieval = await retrieve_witness.retrieve(
            instance_id, conversation_id, user_message, user_info,
        )
        ledger.retrieval = retrieval
        s2_latency = retrieval.retrieval_latency_ms
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s2_retrieval",
            "stage_index": 1,
            "latency_ms": s2_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "retrieval", 1, {"chunks": len(retrieval.knowledge_chunks)},
            s2_latency, verdict="pass",
        )

        # ── P3.2: Orchestrator fan-out gate (after S2, before PR-20) ──────
        # If an orchestrator agent is active and the user message warrants
        # parallel decomposition, fan out to workers and synthesize results.
        fan_out_result = None
        if settings.AGENT_ORCHESTRATOR_ENABLED and self.db is not None:
            try:
                fan_out_result = await self._try_fan_out(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    host_user_id=host_user_id,
                    page_context=page_context,
                    conversation_history=conversation_history,
                    instance_config=instance_config,
                    user_info=user_info,
                    retrieval=retrieval,
                    turn_id=turn_id,
                    budget_tracker=budget,
                )
            except Exception:
                logger.exception("Fan-out attempt failed; falling back to multi-step / single-pass")

        if fan_out_result is not None:
            # ── Fan-out path: skip S3→S5 and PR-20, go straight to S6 ─────
            final_text = fan_out_result.final_text
            total_tokens = fan_out_result.total_tokens
            total_llm_calls = 1  # orchestrator synthesis call

            # Record fan-out ledger fields
            ledger.fan_out_used = True
            ledger.fan_out_worker_count = len(fan_out_result.worker_ids)
            ledger.fan_out_worker_ids = fan_out_result.worker_ids
            ledger.fan_out_artifact_refs = fan_out_result.artifact_refs
            ledger.fan_out_total_tokens = fan_out_result.total_tokens
            ledger.fan_out_latency_ms = fan_out_result.total_latency_ms

            logger.info(
                "TurnPipelineRunner: fan-out complete turn=%s workers=%d succeeded=%d",
                turn_id[:8], fan_out_result.worker_count, fan_out_result.succeeded_count,
            )

            # S6 — Final ledger summary
            s6_start = time.monotonic()
            total_latency = (time.monotonic() - t0) * 1000
            s6_latency = (time.monotonic() - s6_start) * 1000

            # P3.4: Consume budget for fan-out LLM calls + log snapshot
            if budget is not None:
                await budget.consume(total_tokens)
                ledger.budget_snapshot = budget.snapshot()
                ledger.budget_exceeded = budget.exceeded

            await self._write_ledger_row(
                turn_id, instance_id, conversation_id, host_user_id,
                "final", 5,
                {
                    "total_latency_ms": total_latency,
                    "total_tokens": total_tokens,
                    "total_llm_calls": total_llm_calls,
                    "verdict": "pass",
                    "fan_out_path": True,
                    "fan_out_worker_count": fan_out_result.worker_count,
                    "fan_out_artifact_count": len(fan_out_result.artifact_refs),
                },
                s6_latency, verdict="pass",
            )
            await self.db.commit()

            ledger.final_response = final_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = total_tokens
            ledger.total_llm_calls = total_llm_calls

            response = AgentResponse(
                text=final_text,
                sources_cited=[],
                tools_used=[],
                confidence=0.8,
                total_tokens=total_tokens,
                llm_calls=total_llm_calls,
                model="",
            )
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_tokens": total_tokens,
                "total_llm_calls": total_llm_calls,
                "fan_out_path": True,
            })
            return response, ledger

        # ── PR-20: Multi-step planning gate (after S2, before S3) ──────────
        # If a multi-step plan is needed, run ReActLoop instead of single-pass S3→S5.
        react_result = None
        if settings.KG_MULTI_STEP_ENABLED and self.db is not None:
            try:
                react_result = await self._try_multi_step_plan(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=user_message,
                    host_user_id=host_user_id,
                    page_context=page_context,
                    conversation_history=conversation_history,
                    instance_config=instance_config,
                    user_info=user_info,
                    retrieval=retrieval,
                    progress_callback=progress_callback,
                    stream_callback=stream_callback,
                )
            except Exception:
                logger.exception("Multi-step plan attempt failed; falling back to single-pass")

        if react_result is not None:
            # ── ReAct path: skip S3→S5 single-pass, go straight to S6 ──────
            final_text = react_result.final_response
            total_tokens = 0  # ReAct loop tracks its own token usage
            total_llm_calls = react_result.replans_used + len(react_result.step_results)

            for i, sr in enumerate(react_result.step_results):
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    f"react_step_{i}", 2 + i,
                    {
                        "step_id": sr.step_id,
                        "intent": sr.intent,
                        "critic_verdict": sr.critic_verdict,
                        "executed": sr.executed,
                        "error": sr.error,
                    },
                    0.0,  # latency tracked per-step in ReActLoop
                    verdict=sr.critic_verdict,
                    flags=sr.critic_flags,
                )

            logger.info(
                "TurnPipelineRunner: ReAct loop complete steps=%d replans=%d succeeded=%s",
                len(react_result.step_results), react_result.replans_used, react_result.succeeded,
            )

            # S6 — Final ledger summary
            s6_start = time.monotonic()
            total_latency = (time.monotonic() - t0) * 1000
            s6_latency = (time.monotonic() - s6_start) * 1000
            await self._write_ledger_row(
                turn_id, instance_id, conversation_id, host_user_id,
                "final", 5,
                {
                    "total_latency_ms": total_latency,
                    "total_tokens": total_tokens,
                    "total_llm_calls": total_llm_calls,
                    "critic_verdict": "pass" if react_result.succeeded else "veto",
                    "react_path": True,
                },
                s6_latency, verdict="pass" if react_result.succeeded else "veto",
            )
            await self.db.commit()

            # P4.1: Write trajectory (fire-and-forget, own session)
            _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))
            asyncio.ensure_future(AutoMemoryExtractor.try_extract(
                user_message=user_message,
                instance_id=instance_id,
                host_user_id=host_user_id,
                db_session=self.db,
            ))

            # Populate completed_tools so _run_chat's surfacing layer fires on ReAct turns
            _react_completed_tools = [
                {
                    "tool_name": getattr(sr, "tool_name", None) or f"react_step_{i}",
                    "result":    sr.tool_result if hasattr(sr, "tool_result") else (sr.tool_output if hasattr(sr, "tool_output") else {}),
                    "error":     sr.error if hasattr(sr, "error") else None,
                    "latency_ms": sr.latency_ms if hasattr(sr, "latency_ms") else 0.0,
                    "guardrail_flags": sr.critic_flags if hasattr(sr, "critic_flags") else [],
                }
                for i, sr in enumerate(react_result.step_results)
                if getattr(sr, "executed", True)
            ]
            if ledger.execution is not None:
                ledger.execution.completed_tools = _react_completed_tools
            else:
                from types import SimpleNamespace
                ledger.execution = SimpleNamespace(completed_tools=_react_completed_tools)

            ledger.final_response = final_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = total_tokens
            ledger.total_llm_calls = total_llm_calls

            response = AgentResponse(
                text=final_text,
                sources_cited=[],
                tools_used=[],
                confidence=0.8 if react_result.succeeded else 0.3,
                total_tokens=total_tokens,
                llm_calls=total_llm_calls,
                model="",
            )
            await _broadcast_run(instance_id, "run.completed", {
                "run_id": turn_id,
                "total_latency_ms": total_latency,
                "total_tokens": total_tokens,
                "total_llm_calls": total_llm_calls,
            })
            return response, ledger

        # ── Existing single-pass S3→S5 path ────────────────────────────────

        # S3 — Draft (LLM tool-use loop via DraftWitness)
        s3_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s3_draft",
            "stage_index": 2,
        })
        from ai.engine.cognition.turn.draft import DraftWitness
        draft_witness = DraftWitness(
            llm_client=self.llm_client,
            knowledge_store=self.knowledge_store,
            memory_manager=self.memory_manager,
            executor=self.executor,
        )
        # Build system prompt — LLM-synthesized
        config = instance_config or {}
        from ai.engine.llm.prompts import build_chat_prompt
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
            persona=config.get("persona"),
            api_catalog=config.get("api_catalog"),
            navigation_routes=config.get("navigation_routes"),
            domain_topics=config.get("domain_topics"),
            instance_config=config,
            conversation_id=conversation_id,
            instance_id=instance_id,
        )

        # Tool-aware drafting: when an executor is wired, expose the curated
        # tool set to the LLM and append the anti-fabrication grounding rules.
        draft_tools = self._draft_tools if self.executor is not None else None
        # [GAP-M7] Salience guard: only surface list_my_capabilities when the
        # user is asking about identity/access, never as a confusion fallback.
        draft_tools = _filter_draft_tools(draft_tools, user_message, salience.domain)
        # Zone-aware grounding: the anti-fabrication GROUNDING RULES are for
        # Zone 1 (platform-grounded) only. Zones concept/real_time/general get
        # a lighter directive (or the web_research mandate) instead.
        _is_platform_zone = (
            _intent_resolution is None             # resolver didn't run → safe default
            or _intent_resolution.zone in ("platform", "off_limits")
        )
        if draft_tools and _is_platform_zone:
            system_prompt = (
                f"{system_prompt}\n\n"
                "GROUNDING RULES — follow them exactly:\n"
                "- You have tools available. Use them to do real work instead "
                "of guessing. When a tool matches the user's request, call it "
                "right away — do not answer in prose instead of using it, and "
                "do not say you cannot run/execute tasks.\n"
                "- PLAN FIRST, CONVERT ON CONFIRMATION: when the user asks you "
                "to plan, study, research, audit, orchestrate, or 'make a "
                "multi-agent workflow' for something, DO NOT call plan_task "
                "and DO NOT create any task yet. Instead, think it through and "
                "PROPOSE a plan directly in chat: a short numbered list of "
                "steps, each naming the tool or agent that would do it and the "
                "deliverable it produces. Then invite the user to discuss, add, "
                "remove, or reword steps. This proposal lives only in the chat "
                "— it is NOT a task yet. A plain question (e.g. 'what is the "
                "GHG Protocol?') should just be answered directly, with no "
                "plan proposal at all.\n"
                "- Iterate the proposal in chat as the user gives feedback. "
                "Re-present the revised numbered plan after each change and ask "
                "whether it is settled.\n"
                "- ONLY when the user explicitly confirms the plan is settled "
                "(e.g. 'settled', 'go', 'convert it to a task', 'create the "
                "task', 'make it a task', 'yes build it'), call plan_task with "
                "the final agreed brief. That single call turns the agreed plan "
                "into a real pending_approval task. Never call plan_task before "
                "this confirmation, and never auto-create a task on detection.\n"
                "- The plan_task tool DRAFTS a plan and returns a plan id in "
                "pending_approval; it does not execute anything. After calling "
                "it, tell the user the plan id and that it awaits approval in "
                "the Tasks panel. Never claim a task ran or completed.\n"
                "- After plan_task has created the task, if the user asks to "
                "change a step of that task, use edit_plan. If the user asks to "
                "run/approve it, use approve_plan. Never approve or run without "
                "the user's confirmation.\n"
                "- NEVER claim an action succeeded (e.g. 'rule created') unless "
                "a tool result confirms it.\n"
                "- The create_dq_rule tool only STAGES a proposal — it returns "
                "a confirmation execution. Nothing is written until the user "
                "confirms. Tell the user a confirmation button appeared; do "
                "NOT say the rule was created.\n"
                "- The create_dq_rule tool creates a rule DEFINITION; binding "
                "it to a field is OPTIONAL and happens separately via "
                "bind_dq_rules. When the user says the rule is general or that "
                "they will bind it later, create it WITHOUT data_table/"
                "data_field (omit both). Only ask which field/column to use "
                "when the user wants the rule bound to a specific column now. "
                "Never offer a duplicate-check instead of proceeding.\n"
                "- Use web_research when the task needs internet facts (e.g. a "
                "study comparing carbon standards) — cite its results; never "
                "invent sources.\n"
                "- Use export_document to produce a downloadable Word/Excel "
                "artifact when the user wants the findings as a document; tell "
                "them the download link appeared.\n"
                "- If a tool errors, report the error plainly.\n"
                "- You have long-term memory through the learn_fact tool. "
                "When the user asks you to remember/store something, call "
                "learn_fact; it proposes a fact and the user confirms before "
                "it is saved (forget_fact removes a fact). After proposing, "
                "tell the user a confirmation button appeared — do NOT claim "
                "the fact is already saved, and do NOT say you lack memory, "
                "that memory is unavailable/disabled, or that you can only "
                "remember 'if memory is enabled in the future'. If asked "
                "whether you can remember things, answer yes: via "
                "learn_fact/forget_fact, which the user controls.\n"
                "- Only claim a capability that a tool result in this turn "
                "just demonstrated. Your native abilities (writing prose, "
                "general knowledge, arithmetic) are NOT 'Pulse capabilities' "
                "and must not be listed as such. Use the capability-list tool "
                "only when the user asks what you/they can do or access — "
                "never as a fallback when you are unsure.\n"
                "- When the user asks what you can do, use the capability-list "
                "tool so the app can attach the matching page links as small "
                "buttons under your reply."
            )
        elif draft_tools and _intent_resolution is not None:
            _zone = _intent_resolution.zone
            if _zone == "real_time":
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "This question requires live information. Use the "
                    "web_research tool to fetch current data. Always attribute "
                    "the source in your answer. After answering, offer to connect "
                    "the findings to the user's platform data if relevant."
                )
            elif _zone in ("concept", "general"):
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "Answer this question from your knowledge. No platform tool "
                    "call is needed. If there is a natural connection to the "
                    "user's platform data (e.g. their emission factors, DQ rules), "
                    "offer to show that data after answering."
                )

        # [GAP-3] Resolve anaphora: substitute pronouns with active entity
        from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver
        _resolved_user_message = AnaphoraResolver(_wm).resolve(
            conversation_id, user_message
        )

        # [GAP-2] Inject active entity context into system prompt
        _wm_fragment = _wm.to_prompt_fragment(conversation_id)
        if _wm_fragment:
            system_prompt = f"{system_prompt}\n\n{_wm_fragment}"

        # [GAP-4] Inject session preference constraints into system prompt
        _pref_constraints = _pref_store.to_prompt_constraints(conversation_id)
        if _pref_constraints:
            system_prompt = f"{system_prompt}\n\n{_pref_constraints}"

        # [GAP-5/6] Load skill terminology + route query to matching skills
        _skill_terminology: dict[str, str] = {}
        if self.db is not None:
            try:
                from ai.engine.skills.registry import SkillRegistry
                from ai.engine.skills.router import SkillRouter
                _registry = SkillRegistry(self.db)
                _promoted_skills = await _registry.list_promoted(instance_id)
                _router = SkillRouter()
                _matched_skills = _router.find_matching_skills(user_message, _promoted_skills)
                _skill_terminology = _router.get_terminology(_matched_skills)
            except Exception:
                logger.warning(
                    "Skill routing failed; continuing without terminology injection",
                    exc_info=True,
                )
        if _skill_terminology:
            from ai.engine.knowledge.terminology import TerminologyResolver
            system_prompt = TerminologyResolver().inject(system_prompt, _skill_terminology)

        # [S1.5] Inject the intent resolver's matched endpoint into S3 so the
        # planner *confirms* the tool instead of lecturing from memory. This is
        # the mechanism that stops "tell me about emission factors here" from
        # becoming a textbook answer — the matched tool is now named up front.
        if (
            _intent_resolution is not None
            and _intent_resolution.action == "answer"
            and _intent_resolution.candidates
        ):
            from ai.engine.cognition.turn.intent import _endpoint_to_domain_phrase
            _top_cand = _intent_resolution.candidates[0]
            _phrases = [_endpoint_to_domain_phrase(c.name) for c in _intent_resolution.candidates[:3]]
            _delivery_phrase = _DELIVERY_INJECTION.get(
                _intent_resolution.delivery, _DELIVERY_INJECTION["explain"]
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

        # [C1] Adaptive reasoning lane — route genuinely hard turns (deep
        # salience) to the reasoning-grade model. An explicit user-selected
        # model always wins; otherwise a deep turn uses the "reason" task
        # lane (LLM_REASON_MODEL → legacy escalation → LLM_MODEL fallback).
        from ai.engine.llm.router import get_model_for_task as _get_model_for_task
        _draft_model = model
        if not _draft_model and salience.route == "deep":
            _draft_model = _get_model_for_task("reason")
            ledger.reason_escalation = {
                "trigger": "deep_salience",
                "from_model": "",
                "to_model": _draft_model,
                "verdict_before": None,
                "verdict_after": None,
            }

        draft = await draft_witness.draft(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=_resolved_user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            instance_config=instance_config,
            user_info=user_info,
            budget_tracker=budget,
            model=_draft_model,
            tools=draft_tools,
            temperature=temperature,
        )
        # [GAP-1] Fallback handler: ensure non-empty response.
        # Skip when the draft already has tool calls — a tool-only turn (LLM
        # emits no prose but calls a tool to answer) is legitimate and GAP-W8
        # surfaces the tool results as text after S5. Firing the fallback here
        # would replace that with a fake refusal, which the anti-hallucination
        # gate then strips, leaving an empty reply (empty-content regression).
        import dataclasses as _dc
        from ai.engine.cognition.dialogue.fallback import FallbackHandler
        _fallback_text = FallbackHandler().handle(user_message, draft.text)
        if _fallback_text != draft.text and not draft.tool_calls:
            draft = _dc.replace(
                draft,
                text=_fallback_text,
                confidence=0.4,
                model_used=draft.model_used or "fallback",
            )

        ledger.draft = draft
        total_tokens += draft.tokens_used
        total_llm_calls += 1  # S3 is one direct route_chat() call

        # Phase 21-A: carry the prompt/completion split + resolved model for
        # per-generation usage attribution (written once at completion).
        ledger.prompt_tokens += draft.prompt_tokens
        ledger.completion_tokens += draft.completion_tokens
        ledger.model_used = draft.model_used or ledger.model_used

        # P3.4: Consume budget for S3 draft LLM call
        if budget is not None:
            await budget.consume(draft.tokens_used)

        s3_latency = (time.monotonic() - s3_start) * 1000
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s3_draft",
            "stage_index": 2,
            "latency_ms": s3_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "draft", 2,
            {"text_len": len(draft.text), "tool_calls": len(draft.tool_calls), "confidence": draft.confidence},
            s3_latency, tokens_used=draft.tokens_used, model_used=draft.model_used, verdict="pass",
        )

        # S4 — Critic (rules-tier + LLM-tier when flags raised)
        s4_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s4_critic",
            "stage_index": 3,
        })
        from ai.engine.cognition.turn.critic import CriticWitness
        critic_witness = CriticWitness()
        critic = await critic_witness.review(
            draft,
            retrieval,
            enable_llm_critic=True,
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=_resolved_user_message,
            salience=salience,
        )

        # [knowledge_gap routing] Escalate via the reason lane or return
        # honest uncertainty — never mask. (C1: the reason lane resolves
        # LLM_REASON_MODEL → legacy LLM_ESCALATION_MODEL → LLM_MODEL.)
        if critic.verdict == "knowledge_gap":
            _reason_configured = bool(
                (settings.LLM_REASON_MODEL or settings.LLM_ESCALATION_MODEL or "").strip()
            )
            escalation_model = (
                _get_model_for_task("reason") if _reason_configured else ""
            )
            current_model = draft.model_used or ""
            if escalation_model and escalation_model != current_model:
                logger.info(
                    "[%s] knowledge_gap detected — escalating to reason lane (%s)",
                    turn_id[:8], escalation_model,
                )
                draft = await draft_witness.draft(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    user_message=_resolved_user_message,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    instance_config=instance_config,
                    user_info=user_info,
                    budget_tracker=budget,
                    model=escalation_model,
                    tools=draft_tools,
                    temperature=temperature,
                )
                total_tokens += draft.tokens_used
                total_llm_calls += 1
                # Re-run FallbackHandler in case escalated model also returns
                # empty (but not for a tool-only turn — see GAP-1 above).
                _fallback_text = FallbackHandler().handle(_resolved_user_message, draft.text)
                if _fallback_text != draft.text and not draft.tool_calls:
                    import dataclasses as _dc
                    draft = _dc.replace(draft, text=_fallback_text, confidence=0.4)
                critic = await critic_witness.review(
                    draft, retrieval, enable_llm_critic=False,
                    instance_id=instance_id, conversation_id=conversation_id,
                    user_message=_resolved_user_message, salience=salience,
                )
                # C1: record the escalation + quality signal (critic verdict
                # before/after) so the delta is measurable (L7).
                ledger.reason_escalation = {
                    "trigger": "knowledge_gap",
                    "from_model": current_model,
                    "to_model": escalation_model,
                    "verdict_before": "knowledge_gap",
                    "verdict_after": critic.verdict,
                }
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    "escalation", 4,
                    ledger.reason_escalation,
                    (time.monotonic() - s4_start) * 1000,
                    model_used=escalation_model,
                    verdict=critic.verdict,
                    flags=["knowledge_gap"],
                )
            else:
                # No reason/escalation model configured — honest uncertainty, not fake clarification.
                from ai.engine.cognition.dialogue.fallback import HonestUncertaintyHandler
                honest_text = HonestUncertaintyHandler().handle(
                    _resolved_user_message, critic.partial_knowledge
                )
                logger.info(
                    "[%s] knowledge_gap — no reason model, returning honest uncertainty",
                    turn_id[:8],
                )
                import dataclasses as _dc
                draft = _dc.replace(draft, text=honest_text, confidence=0.2, model_used="honest_uncertainty")
                # Critic passes through — this is not a safety issue.
                critic = _dc.replace(critic, verdict="pass_with_flag", flags=["knowledge_gap"])
        ledger.critic = critic
        s4_latency = (time.monotonic() - s4_start) * 1000
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s4_critic",
            "stage_index": 3,
            "latency_ms": s4_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "critic", 3,
            {
                "verdict": critic.verdict,
                "flags": critic.flags,
                "rewritten": bool(critic.rewritten_text),
                "llm_critic_enabled": True,
            },
            s4_latency, verdict=critic.verdict, flags=critic.flags,
        )

        # Use rewritten text if critic provided one
        _draft_text_was_empty = not (critic.rewritten_text or draft.text or "").strip()
        final_text = critic.rewritten_text if critic.rewritten_text else draft.text

        # S5 — Execute (real parallel tool dispatch + streaming)
        s5_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s5_execute",
            "stage_index": 4,
        })
        from ai.engine.cognition.turn.execute import ExecuteWitness
        from ai.engine.agent.guardrails import build_default_pipeline

        hook_pipeline = build_default_pipeline()
        hook_ctx_defaults = {
            "instance_id": instance_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "run_id": turn_id,
            "agent_role": "orchestrator",
            "is_worker": False,
            "instance_config": instance_config,
        }
        execute_witness = ExecuteWitness(
            executor=self.executor,
            hook_pipeline=hook_pipeline,
            hook_ctx_defaults=hook_ctx_defaults,
            run_id=turn_id,
            instance_id=instance_id,
        )
        execution = await execute_witness.execute(
            text=final_text,
            tool_calls=draft.tool_calls,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        ledger.execution = execution
        s5_latency = execution.execution_latency_ms
        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s5_execute",
            "stage_index": 4,
            "latency_ms": s5_latency,
        })
        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "execution", 4,
            {
                "streamed": execution.streamed,
                "tools_executed": len(execution.completed_tools),
                "per_tool_latency_ms": execution.per_tool_latency_ms,
            },
            s5_latency, verdict="pass",
        )

        # [GAP-W8/W9] Tool-result grounding: when the planner executed tools, the
        # pre-tool draft is either empty or a short "I'll fetch …" promise — the
        # fetched data is otherwise discarded. Re-synthesize the final answer from
        # the ACTUAL tool results (GAP-W9, LLM → clean prose + real values), then
        # fall back to a deterministic summary (GAP-W8) only when synthesis is
        # unavailable. Order matters: the LLM synthesis produces the values the
        # user asked for; the deterministic summary is the "never blank" net.
        _synth = await _synthesize_tool_results(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=_resolved_user_message,
            completed_tools=execution.completed_tools,
            draft_text=final_text,
            model=draft.model_used or model,
            delivery=_intent_resolution.delivery if _intent_resolution else "explain",
        )
        if _synth and _synth.get("text"):
            final_text = _synth["text"]
            total_tokens += int(_synth.get("tokens") or 0)
            total_llm_calls += 1
            logger.info(
                "[%s] Tool-result synthesis — final answer written from %d tool result(s) (%d tokens)",
                turn_id[:8], len(execution.completed_tools), int(_synth.get("tokens") or 0),
            )
        elif _draft_text_was_empty and execution.completed_tools:
            from ai.engine.cognition.turn.execute import _build_tool_result_summary
            injected = _build_tool_result_summary(execution.completed_tools)
            if injected:
                final_text = injected
                logger.info(
                    "[%s] Tool-only response — injected tool results as text (draft was empty, %d tools executed)",
                    turn_id[:8], len(execution.completed_tools),
                )

        # S6 — Final ledger summary
        s6_start = time.monotonic()
        await _broadcast_run(instance_id, "run.step.started", {
            "run_id": turn_id,
            "stage": "s6_finalize",
            "stage_index": 5,
        })
        total_latency = (time.monotonic() - t0) * 1000
        s6_latency = (time.monotonic() - s6_start) * 1000

        # P3.4: Log budget snapshot to ledger
        if budget is not None:
            ledger.budget_snapshot = budget.snapshot()
            ledger.budget_exceeded = budget.exceeded

        await self._write_ledger_row(
            turn_id, instance_id, conversation_id, host_user_id,
            "final", 5,
            {
                "total_latency_ms": total_latency,
                "total_tokens": total_tokens,
                "total_llm_calls": total_llm_calls,
                "critic_verdict": critic.verdict,
            },
            s6_latency, verdict=critic.verdict,
        )
        await self.db.commit()

        # P4.1: Write trajectory (fire-and-forget, own session)
        _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))

        ledger.final_response = final_text[:500]
        ledger.total_latency_ms = total_latency
        ledger.total_tokens = total_tokens
        ledger.total_llm_calls = total_llm_calls

        logger.info(
            "TurnPipelineRunner: turn=%s domain=%s route=%s critic=%s latency=%.0fms tokens=%d",
            turn_id[:8], salience.domain, salience.route, critic.verdict,
            total_latency, total_tokens,
        )

        response = AgentResponse(
            text=final_text,
            sources_cited=draft.claimed_citations,
            tools_used=draft.tool_calls,
            confidence=draft.confidence,
            total_tokens=total_tokens,
            llm_calls=total_llm_calls,
            model=draft.model_used,
        )
        asyncio.ensure_future(AutoMemoryExtractor.try_extract(
            user_message=user_message,
            instance_id=instance_id,
            host_user_id=host_user_id,
            db_session=self.db,
        ))

        await _broadcast_run(instance_id, "run.step.completed", {
            "run_id": turn_id,
            "stage": "s6_finalize",
            "stage_index": 5,
            "latency_ms": s6_latency,
        })
        await _broadcast_run(instance_id, "run.completed", {
            "run_id": turn_id,
            "total_latency_ms": total_latency,
            "total_tokens": total_tokens,
            "total_llm_calls": total_llm_calls,
        })

        # [GAP-M6] Post-response proposal detection: if this turn proposed a
        # memory action in prose, record it so the next "yes" is recognised.
        try:
            from ai.engine.cognition.dialogue.pending_action import (
                get_pending_action_store,
            )
            _pending_store = get_pending_action_store()
            _proposal = _pending_store.detect_proposal(final_text)
            if _proposal:
                _pending_store.set_pending(
                    conversation_id, _proposal["fact"], _proposal["category"]
                )
        except Exception:  # noqa: BLE001 - memory hook must never block the turn
            logger.warning(
                "[%s] Pending-action proposal detection failed",
                turn_id[:8], exc_info=True,
            )

        return response, ledger

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

    async def _try_multi_step_plan(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        host_user_id: str | None,
        page_context: str,
        conversation_history: list[dict] | None,
        instance_config: dict | None,
        user_info: dict | None,
        retrieval,  # RetrievalResult
        progress_callback=None,
        stream_callback=None,
    ):
        """PR-20: Attempt multi-step planning. Returns ReActResult or None.

        None means "fall through to single-pass S3→S5" — the caller should
        treat this as "no multi-step needed."
        """
        from ai.engine.cognition.plan.planner import SkillAwarePlanner
        from ai.engine.cognition.plan.loop import ReActLoop
        from ai.engine.cognition.turn.draft import DraftWitness
        from ai.engine.cognition.turn.critic import CriticWitness
        from ai.engine.skills.registry import SkillRegistry
        from ai.engine.llm.prompts import build_chat_prompt
        from ai.engine.core.config import get_settings

        settings = get_settings()

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
        )

        # Only activate ReAct loop for multi-step plans or skill-sourced plans
        if plan.source == "single_step" and len(plan.steps) <= 1:
            logger.debug("TurnPipelineRunner: single-step plan, skipping ReAct loop")
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
            persona=config.get("persona"),
            api_catalog=config.get("api_catalog"),
            navigation_routes=config.get("navigation_routes"),
            domain_topics=config.get("domain_topics"),
            instance_config=config,
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

        # Build orchestrator system prompt
        config = instance_config or {}
        from ai.engine.llm.prompts import build_chat_prompt
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
            persona=config.get("persona"),
            api_catalog=config.get("api_catalog"),
            navigation_routes=config.get("navigation_routes"),
            domain_topics=config.get("domain_topics"),
            instance_config=config,
            conversation_id=conversation_id,
            instance_id=instance_id,
        )

        # Orchestrator decision call: should we fan out?
        orchestrator_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": (
                "You are the orchestrator agent. Your role is to decide whether this "
                "user request would benefit from parallel decomposition across worker "
                "agents. If the request has multiple independent sub-questions or "
                "requires diverse expertise, call delegate_to_workers. If it's a simple "
                "single-focus question, respond with a brief text reply (no tool call) "
                "and the pipeline will fall through to single-pass processing."
                " When the user asks to retrieve, analyse, or compare data — even without the word \"plan\" — fan out to the appropriate specialist workers. Prefer fan-out for aggregation, trend, comparison, ranking, or cross-domain questions. Only decline for greetings, simple factual lookups, or clarification requests."
            )},
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
            synthesis_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": (
                    "You are the orchestrator. Synthesize the following worker findings "
                    "into a single coherent response to the user's original request. "
                    "Do NOT mention workers or internal mechanics — just present the "
                    "combined answer naturally.\n\n"
                    "User request: " + user_message
                )},
                {"role": "user", "content": _json.dumps(fan_out_result.artifact_refs, indent=2)},
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
