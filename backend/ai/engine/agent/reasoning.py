"""
PulseAgent — main reasoning engine with tool-use loop.
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from types import SimpleNamespace

from ai.engine.core.config import get_settings
from ai.engine.llm.prompts import build_chat_prompt
from ai.engine.llm.router import get_model_for_task, route_chat

# Fast regex to detect simple conversational messages that don't need tools
_CONVERSATIONAL_RE = re.compile(
    r"^\s*"
    r"(?:hi+|hello+|hey+|yo+|good\s*(?:morning|afternoon|evening|night|day)"
    r"|thanks?(?:\s+you)?|thank\s+you|thx|ty"
    r"|bye+|goodbye|see\s+ya|later"
    r"|ok(?:ay)?|sure|great|cool|nice|got\s+it|understood"
    r"|yes|no|nope|yep|yeah|yea|nah"
    r"|how\s+are\s+you|what(?:'s|\s+is)\s+up|who\s+are\s+you|what\s+(?:can|do)\s+you\s+do"
    r"|help(?:\s+me)?|what\s+can\s+you\s+help\s+with"
    r"|are\s+you\s+(?:an?\s+)?(?:ai|bot|expert|human|real)"
    r"|what(?:'s|\s+is)\s+your\s+name"
    r")\s*[?!.,]*\s*$",
    re.IGNORECASE,
)

# Identity / account questions answered from the authenticated user context
# (user_info injected into the prompt) — these are grounded, not guesses.
_IDENTITY_RE = re.compile(
    r"\b("
    r"who\s+am\s+i"
    r"|who\s+is\s+logged\s+in|am\s+i\s+logged\s+in"
    r"|what(?:'s|\s+is)\s+my\s+(?:name|username|email|role|account|user\s*id|id)"
    r"|my\s+(?:account|profile|username|email|role)\b"
    r"|what(?:'s|\s+is)\s+my\s+profile"
    r")",
    re.IGNORECASE,
)

logger = logging.getLogger("pulse.agent.reasoning")


@dataclass
class AgentResponse:
    text: str
    sources_cited: list[str] = field(default_factory=list)
    tools_used: list[dict] = field(default_factory=list)
    choices: list[str] = field(default_factory=list)  # clarification options for widget
    confidence: float = 0.8
    llm_calls: int = 0
    total_tokens: int = 0
    model: str = ""
    synthesis: object = None    # SynthesizedAnswer | None — avoids circular import
    query_plan: object = None   # QueryPlan | None — Stage 7 multi-turn context update
    # Rich response fields (Phase B)
    response_type: str = "inferred"  # data_grounded | inferred | cached | clarification
    confidence_label: str = ""       # high | medium | low | uncertain
    summary: str = ""                # one-sentence TL;DR
    citations: list[dict] = field(default_factory=list)  # [{id, source, detail, data_preview}]
    follow_ups: list[str] = field(default_factory=list)   # 3 suggested follow-up questions
    caveats: list[str] = field(default_factory=list)       # important warnings/disclaimers
    reasoning_steps: list[str] = field(default_factory=list)  # what agent did


class PulseAgent:
    def __init__(self, llm_client, knowledge_store, memory_manager=None, executor=None, mode="normal", query_planner=None):
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.executor = executor
        self.mode = mode  # "normal" | "deep"
        self.query_planner = query_planner  # optional QueryPlanner (Stage 3)
        self.budget_tracker = None  # P3.4: set by runner before run()

    # ── think() was deleted in BE-AUDIT-FIX (FIX-5) ──────────────────────
    # All reasoning now flows through cognition/turn/runner.py → TurnPipelineRunner.run().
    # _fast_respond is preserved for simple conversational messages.

    async def _fast_respond(
        self,
        user_message: str,
        instance_id: str,
        instance_config: dict | None,
        page_context: str,
        user_info: dict | None,
        conversation_history: list[dict] | None,
        stream_callback,
        progress_callback,
        conversation_id: str,
    ) -> AgentResponse:
        """Ultra-fast path for conversational messages — no tools, no knowledge, minimal prompt."""
        model = get_model_for_task("chat")
        config = instance_config or {}
        persona = config.get("persona", {})
        platform = config.get('display_name', 'the platform')
        domain_noun = persona.get("domain_noun", "the connected host system")
        audience = persona.get("audience", "platform users")
        system_prompt = (
            f"You are Pulse, the AI operations copilot for {platform}. "
            "Be warm, professional, and concise (2-4 sentences). "
            "Never mention technical details (SQL, APIs, models, libraries, algorithms, features, SHAP values). "
            f"You ONLY discuss {platform} and {domain_noun} operations. "
            "If the user asks anything off-topic (general knowledge, coding, etc.), "
            f"give a friendly one-liner redirecting them to {platform} topics. "
            f"You help {audience} with {domain_noun} on {platform}."
        )
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history[-4:])  # light history window
        messages.append({"role": "user", "content": user_message})

        try:
            router_result = await route_chat(
                task="chat",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=messages,
                temperature=0.5,
            )
            if router_result["finish_reason"] == "budget_exceeded":
                logger.warning(
                    "Fast-respond budget exceeded for instance=%s conv=%s",
                    instance_id, conversation_id[:8],
                )
                text = router_result["content"]
                _tokens = 0
                model = router_result["model"]
            else:
                text = router_result["content"] or "Hello! How can I help you today?"
                _tokens = router_result["input_tokens"] + router_result["output_tokens"]
                model = router_result["model"]
        except Exception as e:
            logger.error(f"Fast respond failed: {e}")
            text = "Hello! I'm Pulse, your AI operations copilot. How can I help you today?"
            _tokens = 0

        logger.info(f"Fast respond  conv={conversation_id[:8]}  chars={len(text)}")

        # Flush to widget for typing effect
        if stream_callback and text:
            if progress_callback:
                try:
                    await progress_callback("Composing response…")
                except Exception:
                    pass
            _pos = 0
            while _pos < len(text):
                _end = min(_pos + 80, len(text))
                try:
                    await stream_callback(text[_pos:_end])
                except Exception:
                    break
                _pos = _end

        return AgentResponse(
            text=text,
            confidence=1.0,
            llm_calls=1,
            total_tokens=_tokens,
            model=model,
            response_type="inferred",
            confidence_label="high",
        )

    @staticmethod
    def _cap_tool_result_for_context(result, max_chars: int = 12000) -> str:
        """Serialize a tool result for injection into the LLM context, capping
        oversized row-bearing payloads so a large read (e.g. a full hourly
        forecast) cannot overflow the model's context window (HTTP 413).

        Strategy: serialize as-is; if it fits, return it. Otherwise trim the
        longest embedded record list (keeping the first rows) and annotate the
        truncation so the model knows more rows exist. As a last resort, hard
        truncate the serialized string.
        """
        raw = json.dumps(result, default=str)
        if len(raw) <= max_chars:
            return raw

        if isinstance(result, dict):
            trimmed = dict(result)
            # Search top-level and one nesting level for the biggest list of rows.
            containers = [trimmed]
            inner = trimmed.get("data")
            if isinstance(inner, dict):
                inner = dict(inner)
                trimmed["data"] = inner
                containers.append(inner)
            list_keys = ("results", "records", "predictions", "summaries", "rows", "entities", "data")
            best = None  # (container, key, list)
            for cont in containers:
                for key in list_keys:
                    val = cont.get(key) if isinstance(cont, dict) else None
                    if isinstance(val, list) and (best is None or len(val) > len(best[2])):
                        best = (cont, key, val)
            if best is not None:
                cont, key, rows = best
                total = len(rows)
                keep = max(1, total)
                # Shrink the kept row count until it fits the budget.
                while keep > 1:
                    cont[key] = rows[:keep]
                    cont[f"_{key}_truncated"] = (
                        f"showing first {keep} of {total} rows; {total - keep} more omitted "
                        "to fit context — ask for a narrower date range or specific rows if needed"
                    )
                    candidate = json.dumps(trimmed, default=str)
                    if len(candidate) <= max_chars:
                        return candidate
                    keep = keep // 2
                cont[key] = rows[:1]
                cont[f"_{key}_truncated"] = (
                    f"showing first 1 of {total} rows; {total - 1} more omitted to fit context"
                )
                candidate = json.dumps(trimmed, default=str)
                if len(candidate) <= max_chars:
                    return candidate

        # Last resort: hard-truncate the serialized string.
        return raw[:max_chars] + ' ...[truncated to fit context]"'

    @staticmethod
    def _is_empty_read(result: dict) -> bool:
        """True when a successful read-style tool result contains zero records.

        Handles the executor wrapper ({"status_code", "data"}), DRF pagination
        ({"results", "count"}), plain lists, and the knowledge-tool shapes.
        Confirmation prompts, navigation actions, and errors are NOT 'empty reads'.
        """
        if not isinstance(result, dict):
            return False
        if any(k in result for k in ("requires_confirmation", "action", "error", "type")):
            return False
        # Knowledge tools
        if "entities" in result:
            return not result.get("entities")
        if "entity" in result:
            return result.get("entity") is None
        # API executor wrapper
        if "status_code" in result:
            sc = result.get("status_code")
            if isinstance(sc, int) and sc >= 400:
                return False  # an HTTP error is handled elsewhere, not an empty read
            inner = result.get("data", None)
            if inner is None:
                return True
            if isinstance(inner, list):
                return len(inner) == 0
            if isinstance(inner, dict):
                if "results" in inner:
                    return not inner.get("results")
                if "count" in inner:
                    return not inner.get("count")
                # A summaries-style payload with an explicit empty collection
                for key in ("summaries", "predictions", "data"):
                    if key in inner and isinstance(inner[key], list):
                        return len(inner[key]) == 0
                return False
        return False

    def _summarize_tool_result(self, result: dict) -> str:
        """Create a brief summary of a tool result."""
        if "requires_confirmation" in result:
            return f"requires_confirmation: execution_id={result.get('execution_id', '')}"
        if "action" in result and result["action"] == "navigate":
            return f"Navigate: {result.get('route', '')}"
        if "row_count" in result:
            return f"Returned {result['row_count']} rows"
        if "status_code" in result:
            data = result.get("data")
            if data:
                preview = json.dumps(data, default=str)[:300]
                return f"API returned {result['status_code']}: {preview}"
            return f"API returned {result['status_code']}"
        if "entities" in result:
            return f"Found {result.get('count', len(result['entities']))} entities"
        if "entity" in result:
            name = result["entity"].get("name", "unknown") if result["entity"] else "not found"
            return f"Entity: {name}"
        # Catch-all for error dicts and unexpected shapes
        if "error" in result:
            err = str(result["error"])[:100]
            return f"Error: {err}"
        return f"Result: {json.dumps(result, default=str)[:100]}"

    def _build_data_fallback(self, tools_used: list[dict], user_message: str) -> str:
        """Build a meaningful fallback when the LLM returned empty text.

        Instead of the generic 'I found some data but couldn't summarize' message,
        extract actual data from tool results and present it.
        """
        data_sections = []
        for t in tools_used:
            raw = t.get("raw_result", "")
            if not raw:
                continue
            try:
                result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            # Extract meaningful data from API responses
            data = result.get("data") if isinstance(result, dict) else result
            if not data:
                continue

            # Format lists as summary
            if isinstance(data, dict) and "results" in data:
                items = data["results"]
            elif isinstance(data, list):
                items = data
            else:
                items = [data]

            if items:
                api_name = t.get("args", {}).get("api_name", t.get("name", "data"))
                section = f"**{api_name}** ({len(items)} item{'s' if len(items) != 1 else ''}):\n"
                for item in items[:10]:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("title") or item.get("id", "")
                        status = item.get("status", "")
                        line = f"- {name}"
                        if status:
                            line += f" — {status}"
                        section += line + "\n"
                    else:
                        section += f"- {str(item)[:200]}\n"
                data_sections.append(section)

        if data_sections:
            return "Here's what I found:\n\n" + "\n".join(data_sections)

        # Truly nothing useful — keep it honest
        return "I retrieved data from the system but couldn't process it into a summary. Could you try rephrasing your question?"

    async def _build_knowledge_context(
        self,
        store,
        user_message: str,
        instance_id: str,
    ) -> tuple[str, object]:
        """
        Stage 3 knowledge retrieval pipeline.

        Returns (context_string, query_plan_or_None).
        Uses the QueryPlanner if available; falls back to assemble_context prose.
        """
        from ai.engine.knowledge_graph.context import assemble_context
        from ai.engine.llm.prompts import build_sql_prompt, build_fallback_prompt

        plan = None

        if self.query_planner is not None:
            try:
                plan = await self.query_planner.plan(
                    user_message, instance_id
                )
                if plan.confidence >= 0.3:
                    # Build importance map for display
                    entity_importances: dict[str, float] = {}
                    for entity_name in plan.target_entities:
                        nodes = await store.get_nodes_by_type("ENTITY", instance_id)
                        for n in nodes:
                            if n.name == entity_name and n.properties:
                                import json as _json
                                try:
                                    props = _json.loads(n.properties)
                                    score = props.get("importance_score")
                                    if score is not None:
                                        entity_importances[entity_name] = score
                                except Exception:
                                    pass
                    # Fetch approved golden pairs for few-shot injection (Phase C2)
                    _golden = []
                    try:
                        _golden = await self._fetch_golden_pairs(instance_id)
                    except Exception as _gp_err:
                        logger.debug(f"Golden pair fetch failed: {_gp_err}")

                    context = build_sql_prompt(
                        plan, user_message,
                        entity_importances=entity_importances,
                        golden_pairs=_golden,
                    )
                    logger.debug(
                        f"query plan used  instance={instance_id}  "
                        f"intent={plan.intent}  confidence={plan.confidence:.2f}  "
                        f"entities={plan.target_entities}"
                    )
                    return context, plan
                else:
                    logger.debug(
                        f"plan confidence {plan.confidence:.2f} < 0.3, falling back to prose  "
                        f"instance={instance_id}"
                    )
            except Exception as _pe:
                logger.warning(f"QueryPlanner failed (non-fatal), falling back to prose: {_pe}")

        # Fall back to Stage 2 assemble_context prose
        prose = await assemble_context(store, user_message, instance_id)
        if self.query_planner is not None:
            from ai.engine.llm.prompts import build_fallback_prompt
            prose = build_fallback_prompt(prose, user_message)
        return prose, plan

    async def _execute_and_synthesize(
        self,
        text: str,
        messages: list[dict],
        model: str,
        instance_id: str,
        user_message: str,
        plan,                    # QueryPlan | None
    ) -> tuple[str, object]:    # (answer_text, SynthesizedAnswer | None)
        """
        Stage 5+6: Extract SQL from the LLM response text, execute it against
        the host DB with error-driven retry, then synthesize a structured answer.

        Returns (answer_text, SynthesizedAnswer).
        answer_text may be the LLM-enriched version grounded in real data.
        SynthesizedAnswer carries rows, shape, viz_hint, provenance, etc.
        """
        import re
        from ai.engine.knowledge_graph.engine import ExecutionEngine
        from ai.engine.knowledge_graph.retry import QueryRetryLoop
        from ai.engine.knowledge_graph.synthesis import ResponseSynthesizer

        # Extract SQL block from response text
        sql_match = (
            re.search(r"```sql\s*(.*?)```", text, re.I | re.S)
            or re.search(r"```\s*(SELECT.*?)```", text, re.I | re.S)
        )
        sql = sql_match.group(1).strip() if sql_match else ""
        if not sql:
            bare = re.search(r"\b(SELECT\s+.+?)(?:\n\n|$)", text, re.I | re.S)
            sql = bare.group(1).strip() if bare else ""

        if not sql:
            logger.debug("_execute_and_synthesize: no SQL found in response text")
            return text, None

        # ── Stage 9: Layer 1 SQL cache check ─────────────────────────────────
        _db = (
            self.knowledge_store.db
            if self.knowledge_store and hasattr(self.knowledge_store, "db")
            else None
        )
        if _db is not None:
            try:
                from ai.engine.knowledge_graph.cache_store import QueryCacheStore
                _cache = QueryCacheStore()
                _cached = await _cache.get_query(sql=sql, instance_id=instance_id, db=_db)
                if _cached is not None:
                    logger.info(
                        "_execute_and_synthesize: Layer-1 cache HIT  instance=%s  rows=%d",
                        instance_id, _cached.row_count,
                    )
                    return _cached.answer_text or text, _cached
            except Exception as _ce:
                logger.debug("cache Layer-1 check skipped: %s", _ce)

        # Execute with retry loop
        engine     = ExecutionEngine(instance_id)
        retry_loop = QueryRetryLoop(
            engine=engine,
            llm_client=self.llm_client,
            model=model,
            messages=messages,
        )
        outcome = await retry_loop.run(sql, plan)

        # Persist feedback if enabled
        await self._persist_query_feedback(outcome, instance_id, user_message)

        # Synthesize structured answer
        synthesizer = ResponseSynthesizer(
            llm_client=self.llm_client,
            model=model,
        )
        synthesis = await synthesizer.synthesize(
            answer_text=text,
            outcome=outcome,
            question=user_message,
            plan=plan,
            enrich=not get_settings().AGENT_UNIFIED_FINALIZE,
        )

        logger.info(
            f"_execute_and_synthesize  instance={instance_id}  "
            f"succeeded={outcome.succeeded}  retries={outcome.retry_count}  "
            f"shape={synthesis.shape}  rows={synthesis.row_count}"
        )

        # ── Stage 9: populate Layer 1 and Layer 2 caches on success ──────────
        if outcome.succeeded and _db is not None:
            try:
                from ai.engine.knowledge_graph.cache_store import QueryCacheStore as _QCS
                _cs = _QCS()
                await _cs.set_query(
                    sql=sql, instance_id=instance_id,
                    synthesis=synthesis, db=_db, utterance=user_message,
                )
                await _cs.set_semantic(
                    utterance=user_message, instance_id=instance_id,
                    synthesis=synthesis, db=_db, sql_executed=sql,
                )
            except Exception as _se:
                logger.debug("cache set skipped: %s", _se)

        return synthesis.answer_text, synthesis

    async def _persist_query_feedback(
        self,
        outcome,           # QueryOutcome
        instance_id: str,
        question: str,
    ) -> None:
        """Write a KgQueryFeedback row for analytics (non-fatal, best-effort)."""
        from ai.engine.core.config import get_settings
        settings = get_settings()
        if not settings.KG_FEEDBACK_ENABLED:
            return
        try:
            from ai.engine.knowledge_graph.models import KgQueryFeedback
            final = outcome.final_result
            fb = KgQueryFeedback(
                instance_id=instance_id,
                question=question[:500],
                sql_final=(final.sql_executed if final else "")[:2000],
                succeeded=outcome.succeeded,
                retry_count=outcome.retry_count,
                error_category=(
                    final.error.category.value
                    if final and final.error
                    else ""
                ),
                duration_ms=sum(
                    a.result.duration_ms for a in outcome.attempts
                ),
                row_count=final.row_count if final else 0,
            )
            # Write via the store's session (best-effort — ignore on failure)
            if self.knowledge_store and hasattr(self.knowledge_store, "db"):
                self.knowledge_store.db.add(fb)
                await self.knowledge_store.db.commit()
        except Exception as exc:
            logger.debug(f"_persist_query_feedback skipped: {exc}")

    async def _persist_recovery_log(
        self,
        recovery_outcome,     # RecoveryOutcome
        original_sql: str,
        instance_id: str,
        question: str,
    ) -> None:
        """Write a KgRecoveryLog row for the audit trail (best-effort, non-fatal)."""
        from ai.engine.core.config import get_settings
        if not get_settings().KG_RECOVERY_AUDIT_ENABLED:
            return
        if not recovery_outcome or not recovery_outcome.error_type:
            return  # no recovery attempt was triggered
        try:
            from ai.engine.knowledge_graph.models import KgRecoveryLog
            row = KgRecoveryLog(
                instance_id=instance_id,
                question=question[:500],
                error_type=recovery_outcome.error_type,
                recovery_type=recovery_outcome.recovery_type,
                original_sql=original_sql[:2000],
                repaired_sql=(recovery_outcome.final_sql or "")[:2000],
                succeeded=recovery_outcome.succeeded,
                correction_description=recovery_outcome.correction_description[:500],
                retry_count=recovery_outcome.retry_count,
            )
            if self.knowledge_store and hasattr(self.knowledge_store, "db"):
                self.knowledge_store.db.add(row)
                await self.knowledge_store.db.commit()
        except Exception as exc:
            logger.debug("_persist_recovery_log skipped: %s", exc)

    async def _finalize_response(
        self,
        draft_text: str,
        user_message: str,
        relevant_memories: str,
        tool_results: list[str] | None,
        synthesis: object,   # SynthesizedAnswer | None
        model: str,
        instance_id: str = "",
        conversation_id: str = "",
        instance_config: dict | None = None,
    ) -> tuple[str, list[str]]:
        """
        Lightweight post-draft finalization — single LLM call for:
          - _enrich_answer: ground answer in actual SQL rows when available
          - _generate_follow_ups: 3 suggested questions

        RULE 1-5 guardrails are intentionally NOT included here; _wisdom_review
        runs separately on the returned answer so content-stripping stays
        in its own PASS/rewrite pass.

        Returns (answer, follow_ups[:3]).
        On any exception or JSON parse failure: returns (draft_text, []) — fail open.
        """
        config = instance_config or {}
        persona = config.get("persona", {})
        domain_noun = persona.get("domain_noun", "the connected system")

        # Data preview from synthesis rows (mirrors _enrich_answer)
        data_section = ""
        if synthesis is not None and hasattr(synthesis, "rows") and synthesis.rows:
            data_preview = json.dumps(synthesis.rows[:10], default=str, indent=2)
            row_count = getattr(synthesis, "row_count", len(synthesis.rows))
            data_section = (
                f"Actual query result ({row_count} rows — first 10 shown):\n"
                f"{data_preview}\n\n"
            )

        prompt = (
            f"User question: {user_message}\n\n"
            f"Draft answer: {draft_text}\n\n"
            f"{data_section}"
            "Task 1 — Grounding: If query result data is shown above, rewrite the "
            "answer to accurately reflect those actual values. Use the real numbers "
            "and values. Do not mention SQL, queries, or database internals. "
            "If no data is shown, or if the draft is already accurate and specific, "
            "return it unchanged.\n\n"
            "Task 2 — Follow-ups: Suggest exactly 3 short follow-up questions the "
            "user might ask next. Questions should be specific, actionable, and "
            f"relevant to {domain_noun}.\n\n"
            "OUTPUT CONTRACT — ABSOLUTE. Return ONLY this JSON object and nothing else:\n"
            "{\"answer\": \"<grounded or unchanged answer>\", "
            "\"follow_ups\": [\"<question 1>\", \"<question 2>\", \"<question 3>\"]}\n"
        )

        try:
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            if router_result["finish_reason"] == "budget_exceeded":
                logger.debug("_finalize_response: budget exceeded, returning draft")
                return draft_text, []
            raw = (router_result["content"] or "").strip()
            # Strip ``` fences leniently
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw).strip()
            parsed = json.loads(raw)
            answer = str(parsed.get("answer", draft_text))
            follow_ups = [str(q) for q in parsed.get("follow_ups", [])[:3]]
            return answer, follow_ups
        except Exception as exc:
            logger.debug(f"_finalize_response failed, returning draft: {exc}")
            return draft_text, []

    async def _wisdom_review(
        self,
        response_text: str,
        original_question: str,
        relevant_memories: str = "",
        tool_results: list[str] | None = None,
        instance_id: str = "",
        conversation_id: str = "",
        instance_config: dict | None = None,
    ) -> str:
        """
        Wisdom loop: lightweight critic pass before returning to user.
        Uses the fast model to detect and strip technical internals or filler language.
        Also enforces mandatory business rules from memory.
        Protocol: reviewer replies with PASS (no violations) or a clean rewrite (violations fixed).
        """
        settings = get_settings()
        config = instance_config or {}
        persona = config.get("persona", {})

        audience = persona.get("audience", "platform users")
        domain_noun = persona.get("domain_noun", "the connected system")

        # Build forbidden terms list
        forbidden_sql_tables = persona.get("forbidden_sql_tables", [])
        forbidden_terms = persona.get("forbidden_terms", [])
        data_units = persona.get("data_units", [])
        all_forbidden = forbidden_sql_tables + forbidden_terms

        forbidden_terms_str = ", ".join(all_forbidden) if all_forbidden else "(none configured)"
        data_units_str = ", ".join(data_units) if data_units else "all values"

        # Build valid routes from navigation_routes
        navigation_routes = config.get("navigation_routes", [])
        valid_routes = [r.get("path", r.get("route", "/")) for r in navigation_routes]
        routes_str = ", ".join(valid_routes[:25]) if valid_routes else "(configured in instance)"

        # Build constraints block from memory if available
        constraints_block = ""
        if relevant_memories and "MANDATORY CONSTRAINTS" in relevant_memories:
            constraints_block = (
                "RULE 4 — MANDATORY BUSINESS RULES\n"
                "  The copilot has learned these rules from the user. The response MUST comply:\n"
                f"  {relevant_memories}\n"
                "  If the draft response lists or presents data that violates a mandatory constraint, "
                "you MUST rewrite the response to exclude the violating data. Do NOT just mention the rule "
                "as a caveat — actually remove or filter the data that should not be shown.\n\n"
            )

        review_prompt = (
            f"You are an editor for an AI copilot that serves {audience}.\n"
            "Your only job is to enforce these hard rules on the DRAFT RESPONSE:\n\n"
            "RULE 1 — NO TECHNICAL INTERNALS\n"
            f"  The response must NOT contain: SQL table names (e.g. {forbidden_terms_str}), "
            "column names, SQL keywords (SELECT, FROM, WHERE, JOIN), database schema details, "
            "API endpoint paths, HTTP method names, JSON field names, or any software/framework internals.\n"
            "  → Replace with business language relevant to the domain.\n\n"
            "RULE 2 — NO EXECUTION MECHANICS + NO INVENTED DATA\n"
            "  Remove any mention of: inference run duration, trigger type, "
            "approval timestamps, run IDs (UUIDs), model version numbers, "
            "'approved by', 'created_at', 'started_at', 'completed_at'. "
            "These are internal execution details irrelevant to end users.\n"
            f"  → CRITICAL: Do NOT add or invent any numerical values ({data_units_str}) that are "
            "not already present in the draft response. If the draft lacks specific data, "
            "keep that acknowledgment as-is — never replace it with made-up numbers.\n\n"
            "RULE 3 — NO AI FILLER PHRASES\n"
            "  Remove: 'As an AI', 'It's worth noting', 'I should mention', 'Please note that', "
            "'It's important to', 'Let me know if you need any clarification or have additional questions', "
            "'Would you like me to elaborate on any specific aspect'\n\n"
            "RULE 4 — NO INVENTED NAVIGATION LINKS\n"
            f"  Only these routes are valid: {routes_str}\n"
            "  NEVER remove or modify navigation links already in the draft. "
            "NEVER add new navigation links that are not in the draft.\n\n"
            f"{constraints_block}"
            "RULE 5 — DATA ACCURACY\n"
            f"  The following tool results contain the ACTUAL data the agent fetched:\n"
            f"---TOOL RESULTS---\n{chr(10).join((tool_results or [])[-6:])[:3000]}\n---END---\n"
            f"  ALL specific numbers in the response ({data_units_str}) "
            "MUST appear in the tool results above. Any number not found there is a hallucination — "
            "remove it and replace with the actual value from the tool results, or mark as 'data unavailable'.\n\n"
            "RULE 6 — NO INVENTED SYSTEM BEHAVIOUR\n"
            "  The draft must NOT assert how the platform stores, retains, expires, limits, or caps data "
            "unless that claim is supported by the tool results above. Specifically flag and REMOVE invented "
            "policy claims about retention windows, data caps, expiry rules, or storage limits. "
            "If the draft says data could not be found, that is fine — but it must NOT fabricate a REASON "
            "(a retention rule, a window, a limit) that is not present in the tool results. Replace any such "
            "invented explanation with a plain statement that the value could not be retrieved, optionally "
            "offering to look it up another way. Do not invent a number for N either.\n\n"
            "OUTPUT RULES — ABSOLUTE:\n"
            "- If the draft has NO violations: output exactly the single word PASS and nothing else.\n"
            "- If the draft HAS violations: output ONLY the fully corrected response text with zero preamble.\n"
            "  Do NOT output: rule violation lists, numbered findings, 'Corrected response:', "
            "'Here is the corrected...', 'The draft contains...', or any meta-commentary.\n"
            "  Your entire output must be the corrected response that the user will read directly.\n\n"
            f"Original question: {original_question}\n\n"
            f"Draft response:\n{response_text}"
        )

        try:
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=[{"role": "user", "content": review_prompt}],
                temperature=0.0,
            )
            revised = (router_result["content"] or "").strip()
            if revised.upper() == "PASS" or not revised:
                return response_text
            # Strip any meta-commentary the reviewer may have prepended
            # (e.g. "The draft response does not contain violations. Here is...")
            revised = self._strip_reviewer_preamble(revised)
            logger.info(
                "wisdom_review revised response before_chars=%d after_chars=%d",
                len(response_text),
                len(revised),
            )
            return revised
        except Exception as e:
            logger.warning(f"Wisdom review skipped: {e}")
            return response_text

    @staticmethod
    def _strip_reviewer_preamble(text: str) -> str:
        """Remove meta-commentary lines a reviewer LLM may prepend before the real response."""
        import re

        # If the reviewer used "Corrected response:" separator, take everything after it
        corrected_marker = re.search(
            r'^corrected response\s*:\s*', text, re.IGNORECASE | re.MULTILINE
        )
        if corrected_marker:
            return text[corrected_marker.end():].strip()

        # Strip leading lines that look like rule-violation lists or meta-commentary
        preamble_patterns = [
            r'^\d+\.\s*(rule|violation|issue|problem|error).*',  # "1. Rule 2 (...):"
            r'^The (draft |original )?response (does not |doesn.t |contains? ).*',
            r'^(Here is|Below is|I have|No violations|The following|Therefore).*',
            r'^(I corrected|I fixed|I removed|I replaced|Corrected|Updated).*',
            r'^violations?\s*found.*',
        ]
        lines = text.split('\n')
        stripped = 0
        while lines and stripped < 8:  # allow stripping up to 8 preamble lines
            stripped_line = lines[0].strip()
            if not stripped_line:  # skip blank lines in preamble too
                lines.pop(0)
                stripped += 1
                continue
            if any(re.match(p, stripped_line, re.IGNORECASE) for p in preamble_patterns):
                lines.pop(0)
                stripped += 1
            else:
                break
        return '\n'.join(lines).strip() if lines else text

    # ── Phase B: Response enrichment helpers ──────────────────────────────

    @staticmethod
    def _compute_confidence(
        tools_used: list[dict],
        synthesis,
        iterations: int,
    ) -> float:
        """
        Dynamic confidence score based on:
        - Whether data was retrieved (tools used with real results)
        - Whether SQL execution succeeded (synthesis present)
        - Number of iterations (fewer = simpler chain = higher confidence)
        - Whether cache was used
        """
        score = 0.7  # base: clean LLM answer

        # Data grounding boosts confidence
        data_tools = [t for t in tools_used if t["name"] in ("query_host_db", "call_host_api")]
        if data_tools:
            # Check if any succeeded (no error in summary)
            ok_tools = [t for t in data_tools if "error" not in str(t.get("result_summary", "")).lower()]
            # An empty read is NOT real grounding — a tool that returned zero
            # records must not inflate confidence (this is the Apr-21 "no data"
            # confabulation trap). Only non-empty successes count as grounding.
            grounded_tools = [t for t in ok_tools if not t.get("empty")]
            if grounded_tools:
                score += 0.15  # got live data with actual records
            elif ok_tools:
                # Ran cleanly but every read came back empty — low certainty
                # about whether the data truly does not exist vs. wasn't found.
                score -= 0.2
            else:
                score -= 0.15  # all data tools failed

        # Successful SQL synthesis = strong grounding
        if synthesis is not None and hasattr(synthesis, "row_count"):
            if synthesis.row_count > 0:
                score += 0.1
            if getattr(synthesis, "cached", False):
                score += 0.05  # cache hit = validated previously

        # Retry penalty
        if synthesis and hasattr(synthesis, "retry_count"):
            score -= min(synthesis.retry_count * 0.05, 0.15)

        # Many iterations = complex chain = slight penalty
        if iterations > 3:
            score -= 0.05

        return max(0.1, min(1.0, round(score, 2)))

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.6:
            return "medium"
        if score >= 0.35:
            return "low"
        return "uncertain"

    @staticmethod
    def _classify_response_type(
        tools_used: list[dict],
        synthesis,
    ) -> str:
        """Classify response as data_grounded, cached, inferred, or clarification."""
        if synthesis and getattr(synthesis, "cached", False):
            return "cached"
        data_tools = {"query_host_db", "call_host_api"}
        if any(t["name"] in data_tools for t in tools_used):
            return "data_grounded"
        if any(t["name"] == "ask_clarification" for t in tools_used):
            return "clarification"
        return "inferred"

    @staticmethod
    def _build_citations(tools_used: list[dict]) -> list[dict]:
        """Build numbered citations from tool calls — user-friendly labels."""
        _FRIENDLY_NAMES = {
            "call_host_api": "Platform data",
            "query_host_db": "Database query",
            "search_knowledge": "Knowledge base",
            "get_entity_details": "Entity lookup",
        }
        citations = []
        for i, tool in enumerate(tools_used, 1):
            name = tool["name"]
            if name in ("learn_fact", "navigate_to", "open_entity", "ask_clarification"):
                continue
            friendly = _FRIENDLY_NAMES.get(name, name)
            # Build a concise human-readable detail
            args = tool.get("args", {})
            if name == "call_host_api":
                api = args.get("api_name", "")
                expl = args.get("explanation", "")
                detail = expl or api.replace("_", " ").title()
            elif name == "query_host_db":
                detail = args.get("explanation", "Custom analysis")
            elif name == "search_knowledge":
                detail = args.get("query", "")
            elif name == "get_entity_details":
                detail = args.get("entity_name", "")
            else:
                detail = args.get("explanation", "")
            citation = {
                "id": i,
                "source": friendly,
                "detail": detail[:120] if detail else None,
            }
            summary = tool.get("result_summary", "")
            if summary:
                # Extract just the status, not raw JSON
                if "returned" in summary.lower():
                    status = summary.split("|")[0].strip() if "|" in summary else summary
                    citation["data_preview"] = status[:80]

            # ── Freshness indicator ──
            raw = tool.get("raw_result", "")
            if raw:
                import re as _re
                from datetime import datetime as _dt, timezone as _tz
                _date_pat = _re.compile(r"(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?)")
                _dates = _date_pat.findall(raw[:1000])  # scan first 1000 chars
                _latest = None
                for _d in _dates:
                    try:
                        _p = _dt.fromisoformat(_d.replace("T", " ")).replace(tzinfo=_tz.utc)
                        if _latest is None or _p > _latest:
                            _latest = _p
                    except (ValueError, TypeError):
                        continue
                if _latest:
                    _age = (_dt.now(_tz.utc) - _latest).total_seconds() / 3600
                    if _age < 6:
                        citation["freshness"] = "live"
                    elif _age < 36:
                        citation["freshness"] = "recent"
                    else:
                        citation["freshness"] = "stale"
                        citation["data_date"] = _latest.strftime("%Y-%m-%d")

            citations.append(citation)
        return citations

    @staticmethod
    def _detect_caveats(synthesis, tools_used: list[dict]) -> list[str]:
        """Detect data quality caveats to surface alongside the response."""
        import re
        from datetime import datetime, timedelta, timezone

        caveats = []
        if synthesis and hasattr(synthesis, "truncated") and synthesis.truncated:
            caveats.append(
                f"Results were truncated to {getattr(synthesis, 'row_count', 'N')} rows. "
                "The full dataset may contain more records."
            )
        if synthesis and hasattr(synthesis, "retry_count") and synthesis.retry_count > 0:
            caveats.append(
                f"Query required {synthesis.retry_count} correction(s) before succeeding."
            )
        # Check for failed tools
        failed = [t for t in tools_used if "error" in str(t.get("result_summary", "")).lower()]
        if failed:
            caveats.append("Some data sources returned errors — results may be incomplete.")

        # ── Empty-read awareness ──
        # If every data lookup came back empty (and none returned records), the
        # answer rests on absence-of-evidence, not evidence. Surface that so the
        # reader knows "not found" may mean "not queried right", not "does not exist".
        data_tools = [t for t in tools_used if t["name"] in ("query_host_db", "call_host_api")]
        if data_tools and all(t.get("empty") for t in data_tools):
            caveats.append(
                "The data lookups returned no records. This may mean the item does not exist, "
                "or that it was not found with the parameters used — it is not proof the data is unavailable."
            )

        # ── Temporal staleness detection ──
        # Look for date patterns in tool results and flag if data is old
        now_utc = datetime.now(timezone.utc)
        stale_threshold = timedelta(hours=36)  # flag if data is >36h old
        date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?)")
        latest_data_date = None

        for tool in tools_used:
            raw = str(tool.get("raw_result", ""))
            dates_found = date_pattern.findall(raw)
            for d in dates_found:
                try:
                    parsed = datetime.fromisoformat(d.replace("T", " "))
                    parsed = parsed.replace(tzinfo=timezone.utc)
                    if latest_data_date is None or parsed > latest_data_date:
                        latest_data_date = parsed
                except (ValueError, TypeError):
                    continue

        if latest_data_date and (now_utc - latest_data_date) > stale_threshold:
            age_days = (now_utc - latest_data_date).days
            age_hours = int((now_utc - latest_data_date).total_seconds() // 3600)
            if age_days > 0:
                age_str = f"{age_days} day{'s' if age_days > 1 else ''}"
            else:
                age_str = f"{age_hours} hour{'s' if age_hours > 1 else ''}"
            caveats.append(
                f"Data freshness warning: latest data is from {latest_data_date.strftime('%Y-%m-%d %H:%M')} "
                f"({age_str} ago). Results may not reflect current system state."
            )

        return caveats

    @staticmethod
    def _build_reasoning_steps(tools_used: list[dict]) -> list[str]:
        """Build a human-readable list of what the agent did."""
        steps = []
        for tool in tools_used:
            name = tool["name"]
            args = tool.get("args", {})
            summary = tool.get("result_summary", "")
            if name == "query_host_db":
                expl = args.get("explanation", "")
                steps.append(expl or "Ran custom data analysis")
            elif name == "call_host_api":
                expl = args.get("explanation", "")
                api = args.get("api_name", "").replace("_", " ")
                steps.append(expl or f"Retrieved {api}")
            elif name == "search_knowledge":
                q = args.get("query", "")
                steps.append(f"Searched knowledge: {q}" if q else "Searched knowledge base")
            elif name == "get_entity_details":
                entity = args.get("entity_name", "")
                steps.append(f"Looked up {entity}" if entity else "Looked up entity")
            elif name == "open_entity":
                expl = args.get("explanation", "Opened page")
                steps.append(expl)
            elif name == "navigate_to":
                expl = args.get("explanation", "Navigated")
                steps.append(expl)
            elif name == "learn_fact":
                steps.append("Learned a new fact from you")
        return steps

    async def _generate_follow_ups(
        self,
        user_message: str,
        response_text: str,
        model: str,
        instance_id: str = "",
        conversation_id: str = "",
        instance_config: dict | None = None,
    ) -> list[str]:
        """
        Generate 3 follow-up question suggestions based on the conversation.
        Uses the fast model, short prompt, low token cost.
        """
        settings = get_settings()
        fast_model = settings.LLM_NORMAL_MODEL
        config = instance_config or {}
        persona = config.get("persona", {})
        domain_noun = persona.get("domain_noun", "the connected system")
        example_questions = persona.get("example_questions", [
            "What is the latest status?",
            "Show me more details",
            "What are the trends?",
        ])
        example_str = json.dumps(example_questions[:3])

        prompt = (
            "Based on this Q&A exchange, suggest exactly 3 short follow-up questions "
            "the user might ask next. Questions should be specific, actionable, and "
            f"relevant to {domain_noun}.\n\n"
            f"User asked: {user_message[:300]}\n\n"
            f"Assistant answered: {response_text[:500]}\n\n"
            "Return ONLY a JSON array of 3 strings, nothing else. Example:\n"
            f"{example_str}"
        )

        try:
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=conversation_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            raw = (router_result["content"] or "").strip()
            # Parse JSON array
            follow_ups = json.loads(raw)
            if isinstance(follow_ups, list) and len(follow_ups) >= 1:
                return [str(q) for q in follow_ups[:3]]
        except Exception as e:
            logger.debug(f"Follow-up generation parse failed: {e}")
        return []

    async def _fetch_golden_pairs(
        self,
        instance_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Fetch approved golden NL→SQL pairs for few-shot prompt injection.
        Closes the feedback loop: corrections → golden pairs → better SQL generation.
        """
        from ai.engine.core.database import get_session_factory
        from sqlalchemy import select
        from ai.engine.knowledge_graph.models import KgGoldenPair

        session_factory = get_session_factory()
        async with session_factory() as db:
            stmt = (
                select(KgGoldenPair)
                .where(
                    KgGoldenPair.instance_id == instance_id,
                    KgGoldenPair.review_status == "approved",
                )
                .order_by(KgGoldenPair.reviewed_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    "natural_language": r.natural_language,
                    "corrected_sql": r.corrected_sql,
                }
                for r in rows
            ]
