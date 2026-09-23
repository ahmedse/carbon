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
from ai.engine.core.resolution import payload_status
from ai.engine.cognition.turn.witnesses import (
    TurnLedger,
)

logger = logging.getLogger("pulse.cognition.turn.runner")

# Lazy import — avoids circular dependency with notifier
broadcast_run_event = None


def _signal(ledger: TurnLedger, gate: str, fired: bool, **detail) -> None:
    if ledger.decision_signals is None:
        ledger.decision_signals = []
    ledger.decision_signals.append(
        {"gate": gate, "fired": fired, "detail": detail or {}}
    )


# Stages whose LLM calls are background / fire-and-forget — excluded from
# the foreground ``llm_calls`` budget (PV2-2C deterministic accounting).
_BACKGROUND_LLM_STAGES = frozenset({"auto_memory"})


def _finalize_meter(ledger: TurnLedger, meter, decision: str) -> None:
    from ai.engine.llm.call_meter import CallMeter

    ledger.turn_decision = decision
    if not isinstance(meter, CallMeter):
        return
    by_stage = meter.by_stage()
    background = sum(by_stage.get(s, 0) for s in _BACKGROUND_LLM_STAGES)
    foreground = max(0, int(meter.total) - int(background))
    ledger.llm_calls_by_stage = by_stage
    ledger.llm_calls_measured = foreground
    ledger.llm_calls_background = background
    fired_gates = [
        s["gate"] for s in (ledger.decision_signals or []) if s.get("fired")
    ]
    logger.info(
        "[turn-decision] conv=%s decision=%s llm=%d bg=%d by_stage=%s fired=%s",
        ledger.conversation_id,
        decision,
        foreground,
        background,
        by_stage,
        fired_gates,
    )


def _audience_from_user_info(user_info: dict | None) -> list[str]:
    if not isinstance(user_info, dict):
        return ["ess"]
    aud = user_info.get("audience")
    if isinstance(aud, (list, tuple, set)) and aud:
        return [str(a) for a in aud]
    return ["ess"]


def _scoped_api_catalog(instance_config: dict | None, user_info: dict | None) -> list:
    from ai.engine.cognition.context_pack import filter_catalog_by_audience

    return filter_catalog_by_audience(
        (instance_config or {}).get("api_catalog") or [],
        _audience_from_user_info(user_info),
    )


def _scoped_navigation_routes(instance_config: dict | None, user_info: dict | None) -> list:
    from ai.engine.cognition.context_pack import filter_catalog_by_audience

    return filter_catalog_by_audience(
        (instance_config or {}).get("navigation_routes") or [],
        _audience_from_user_info(user_info),
    )


def _audience_persona(instance_config: dict | None, user_info: dict | None) -> str:
    from ai.engine.cognition.context_pack import compose_persona_for_audience

    return compose_persona_for_audience(
        instance_config,
        _audience_from_user_info(user_info),
    )


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


# ── G5 text-transformation meta-task guard ────────────────────────────────
# A turn whose ACTUAL ask is to transform quoted text (correct spelling/grammar,
# proofread, rephrase, rewrite, translate, fix typos) must NEVER be re-routed
# into live weather fetching just because the quoted sentence happens to name
# "weather"/"forecast". Regex-only and engine-local (the engine cannot import
# ``ai.plugins.web_research`` — RULE_20), so it lives here beside the routing.
_TEXT_TRANSFORM_RE = re.compile(
    r"\b(?:"
    r"correct(?:\s+the)?\s+spelling|"
    r"fix(?:\s+the)?\s+spelling|"
    r"check(?:\s+the)?\s+spelling|"
    r"spell(?:-|\s)?check|"
    r"correct(?:\s+the)?\s+grammar|"
    r"fix(?:\s+the)?\s+grammar|"
    r"check(?:\s+the)?\s+grammar|"
    r"proofread|"
    r"rephrase|"
    r"rewrite(?:\s+(?:the|this))?|"
    r"fix(?:\s+the)?\s+typos?|"
    r"typo\b|"
    r"translate(?:\s+(?:this|the|to|into)\b)?"
    r")\b",
    re.IGNORECASE,
)


def _is_text_transform_request(text: str) -> bool:
    """True when the user's ask is to transform quoted text, not to act on it."""
    if not text:
        return False
    return bool(_TEXT_TRANSFORM_RE.search(text))


# ── F-LIVE-5: fan-out probe gate ──────────────────────────────────────────
# The orchestrator decision is a full LLM call that almost always declines.
# Only long, analytical, non-self-service turns are worth probing.
_ESS_TOPIC_RE = re.compile(
    r"(?i)\b(?:leave|loan|attendance|vacation|payslip|salary|absence|overtime|"
    r"time\s*off)s?\b"
    r"|إجاز|اجاز|قرض|راتب|رواتب|حضور|غياب|قسيم|استئذان|سلف"
)
_FIRST_PERSON_RE = re.compile(
    r"(?i)\b(?:i|i'm|i've|i'd|my|me|mine)\b"
    r"|(?:^|\s)(?:أنا|انا|عندي|لدي|أريد|اريد|طلبت)(?:\s|$)"
    r"|(?:راتب|إجازت|اجازت|قرض|حضور|رصيد|قسيمت)ي"
)
_MY_ENDPOINT_RE = re.compile(r"(?:^|_)my(?:_|$)")


def _history_has_active_process(conversation_history: list[dict] | None) -> bool:
    """True when a recent message names a governed process id (brief/dial)."""
    from ai.engine.cognition.turn.process_brief import KNOWN_PROCESS_IDS

    for msg in (conversation_history or [])[-6:]:
        content = str((msg or {}).get("content") or "")
        if any(pid in content for pid in KNOWN_PROCESS_IDS):
            return True
    return False


def _fanout_skip_reason(
    user_message: str,
    intent_resolution,
    conversation_history: list[dict] | None,
    *,
    min_tokens: int,
) -> str | None:
    """Return why the fan-out probe should be skipped, or ``None`` to probe."""
    text = (user_message or "").strip()
    if len(text.split()) < min_tokens:
        return "short_utterance"
    if intent_resolution is not None:
        action = getattr(intent_resolution, "action", "")
        if action == "navigate":
            return "nav"
        if action in ("clarify", "disambiguate"):
            return "clarify"
        candidates = getattr(intent_resolution, "candidates", None) or []
        if candidates and _MY_ENDPOINT_RE.search(str(candidates[0].name)):
            return "ess"
    try:
        from ai.engine.agent.chat_surface import is_ess_write_intent

        if is_ess_write_intent(text):
            return "ess"
    except Exception:  # noqa: BLE001 — classification only
        pass
    if _ESS_TOPIC_RE.search(text) and _FIRST_PERSON_RE.search(text):
        return "ess"
    if _history_has_active_process(conversation_history):
        return "active_process"
    return None


# ── F-LIVE-1: scope refusal ───────────────────────────────────────────────
_DEFAULT_REFUSAL_EN = (
    "I'm not able to help with that request. "
    "If you have a question about your platform data, emissions, "
    "or data quality, I'm here to help."
)
_DEFAULT_REFUSAL_AR = (
    "لا أستطيع المساعدة في هذا الطلب. "
    "إذا كان لديك سؤال عن بيانات منصتك، فأنا هنا للمساعدة."
)
# Wording that keeps a refusal even when the ask names an in-scope topic.
_SCOPE_BYPASS_RE = re.compile(
    r"(?i)\b(?:ignore|disregard|bypass|override|jailbreak|pretend|"
    r"system\s+prompt|developer\s+mode|you\s+are\s+now|"
    r"passwords?|credentials?|api\s*keys?|secret\s+keys?|access\s+controls?)\b"
    r"|تجاهل|تجاوز\s*(?:ال)?(?:صلاحيات|قيود|حماي)|"
    r"كلمة\s*المرور|كلمات\s*المرور|كلمات\s*مرور|كلمة\s*السر|"
    r"موجه\s*النظام|صلاحيات\s*المدير"
)


def _is_declared_in_scope(user_message: str, instance_config: dict | None) -> bool:
    """True when the ask names a topic in ``topic_guard.in_scope`` (EN/AR).

    Used to narrow the classifier's ``off_limits`` refusal: an in-scope HR ask
    («أريد قرض طارئ») must not be scope-refused. Bypass / credential wording
    is never treated as in scope.
    """
    from ai.engine.cognition.turn.navigation import normalize_text

    declared = ((instance_config or {}).get("topic_guard") or {}).get("in_scope") or {}
    if isinstance(declared, list):
        declared = {"en": declared}
    keywords = [
        normalize_text(str(k))
        for lang in ("en", "ar")
        for k in (declared.get(lang) or [])
        if str(k).strip()
    ]
    if not keywords:
        return False
    raw = user_message or ""
    if _SCOPE_BYPASS_RE.search(raw):
        return False
    norm = normalize_text(raw)
    for kw in keywords:
        if re.search(r"[\u0600-\u06FF]", kw):
            if kw in norm:
                return True
        elif re.search(r"\b" + re.escape(kw), norm):
            return True
    return False


def _refusal_text(instance_config: dict | None, user_message: str) -> str:
    """Instance refusal in the user's language (``refusal`` / ``refusal_ar``)."""
    from ai.engine.cognition.turn.language import detect_reply_language

    guard = (instance_config or {}).get("topic_guard") or {}
    if detect_reply_language(user_message) == "ar":
        return (guard.get("refusal_ar") or "").strip() or _DEFAULT_REFUSAL_AR
    return (guard.get("refusal") or "").strip() or _DEFAULT_REFUSAL_EN


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
#: When ``ECF_ENABLED``, ``resolve_entity`` / ``aggregate_entity`` join the
#: allow-set dynamically (see ``_chat_tool_allowlist``) — otherwise name
#: lookups fall through to ``search_knowledge`` and false-miss live People rows.
_CHAT_STATIC_TOOLS = frozenset({
    "search_knowledge", "get_entity_details",
    "learn_fact", "forget_fact",
    # call_host_api reaches REST host endpoints listed in the system prompt.
    # ECF resolve/aggregate are separate function tools (not REST) and are
    # gated in ``_chat_tool_allowlist`` when ECF_ENABLED.
    "call_host_api",
})

_ECF_CHAT_TOOLS = frozenset({"resolve_entity", "aggregate_entity"})


def _chat_tool_allowlist() -> frozenset[str]:
    """Chat planner allow-set: spine ∪ chat-visible plugins ∪ ECF (when on)."""
    from ai.engine.agent.plugins import chat_tool_names
    from ai.engine.core.config import get_settings

    allow = _CHAT_STATIC_TOOLS | chat_tool_names()
    if getattr(get_settings(), "ECF_ENABLED", False):
        allow = allow | _ECF_CHAT_TOOLS
    return allow


async def _write_trajectory_own_session(run_id: str) -> None:
    """Write the trajectory on a DEDICATED session (fire-and-forget safe).

    Must not reuse the turn session: the caller may close it while this
    background task is still running, which triggers an asyncpg
    "another operation is in progress" race (seen in evals, where the
    harness closes the session immediately after the turn).
    """
    from ai.engine.core.database import get_store
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

        # Unwrap the host executor envelope — keep authz signals on the payload
        # so synthesis never paraphrases CBAC deny as "no data" (B5).
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            authz_meta = {
                k: data[k]
                for k in (
                    "unauthorized", "capability", "message",
                    "unauthorized_fields", "status_code",
                )
                if k in data and data[k] is not None
            }
            inner = data["data"]
            if authz_meta and isinstance(inner, dict):
                data = {**inner, **{k: v for k, v in authz_meta.items() if k not in inner}}
            elif authz_meta:
                data = {"data": inner, **authz_meta}
            else:
                data = inner

        if isinstance(data, dict) and data.get("unauthorized"):
            deny = {
                "unauthorized": True,
                "capability": data.get("capability"),
                "message": data.get("message"),
                "unauthorized_fields": data.get("unauthorized_fields"),
                "status_code": data.get("status_code"),
            }
            header = f"### {name}\n"
            body = _json.dumps(deny, ensure_ascii=False, indent=2, default=str)
            section = header + body
            if used + len(section) > max_chars:
                remaining = max_chars - used
                section = section[:remaining] + "\n…(truncated)"
            sections.append(section)
            used += len(section)
            if used >= max_chars:
                break
            continue

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
        "present the data as a Markdown table so it is readable. "
        "End with one natural next step."
    ),
    "analyze": (
        "The user wants insight — surface the extremes (highest/lowest), the "
        "groupings, and patterns. Lead with the finding, then support it with "
        "a Markdown table."
    ),
    "compare": (
        "The user wants a side-by-side comparison — contrast the entries on the "
        "dimensions that matter using a Markdown table."
    ),
    "summarize": (
        "The user wants a roll-up — give headline numbers and a compact table "
        "of the main groups, no exhaustive list."
    ),
}


def _no_match_hints(no_matches: list[dict]) -> list[str]:
    """Extract unique, non-empty hints from ``no_match`` tool results."""
    import json as _json

    hints: list[str] = []
    for tr in no_matches or []:
        raw = tr.get("result")
        data = raw
        if isinstance(data, str):
            try:
                data = _json.loads(data)
            except (TypeError, ValueError):
                data = raw
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            continue
        hint = str(data.get("hint") or "").strip() or str(data.get("reason") or "").strip()
        if hint and hint not in hints:
            hints.append(hint)
    return hints


async def _normalize_weather_location(
    *,
    instance_id: str,
    conversation_id: str,
    original_question: str,
    user_reply: str,
    conversation_history: list[dict] | None = None,
    model: str | None = None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> str:
    """LLM-normalize a location answer into a geocoder-ready ``City, Country``.

    Open-Meteo's keyless geocoder is an exact-match gazetteer: it fails on
    typos ("alamien") and region names ("north coast egypt"). This uses the
    LLM's geographic knowledge — *grounded in the conversation so far* — to
    resolve the user's short reply to the exact place they meant. The most
    important context is the assistant's own prior clarifying question (which
    typically listed the candidate cities the user is now choosing between),
    so recent turns are threaded into the prompt. Corrects spelling and
    resolves a region to its most prominent city. Falls back to the raw reply
    on any failure (never blocks the turn).
    """
    from ai.engine.cognition.context_pack import (
        TASK_WEATHER_LOCATION,
        build_context_pack,
    )
    from ai.engine.llm.router import route_chat

    # Thread the recent turns (the pending question + the assistant's
    # clarification with its offered candidates) so the model resolves the
    # reply IN CONTEXT instead of guessing in a vacuum.
    transcript_lines: list[str] = []
    for turn in (conversation_history or [])[-6:]:
        role = (turn.get("role") or "").strip() or "user"
        content = (turn.get("content") or "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    user_parts = []
    if transcript:
        user_parts.append(f"Conversation so far:\n{transcript}")
    user_parts.append(f"Original weather question: {original_question}")
    user_parts.append(f"User's location answer: {user_reply}")
    user_parts.append("Canonical 'City, Country':")
    pack = build_context_pack(
        state,
        surface="chat",
        stage="weather_normalize",
        user_info=user_info,
        instance_config=instance_config,
        conversation_history=conversation_history,
        language=language,
        task_body=TASK_WEATHER_LOCATION,
        user_body="\n".join(user_parts),
        include_knowledge=False,
        include_memory=False,
        include_history=False,
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"geo-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.0,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("Weather location normalization failed", exc_info=True)
        return user_reply

    text = (result.get("content") or "").strip().splitlines()[0].strip()
    text = text.strip(" .\"'`")
    # Sanity guard: a place name is short. Anything sentence-like → keep raw.
    if not text or len(text) > 60:
        return user_reply
    return text


def _weather_location_fallback(weather_extractor, question: str) -> str:
    """Return the host's deterministic location extractor result.

    When no host extractor is injected (or it raises), return the raw question
    unchanged — a safe no-op that never blocks the turn.
    """
    if weather_extractor is None:
        return question
    fn = getattr(weather_extractor, "extract_weather_location", None)
    if fn is None:
        return question
    try:
        return fn(question)
    except Exception:  # noqa: BLE001 - fallback must never raise
        return question


async def _normalize_weather_question(
    *,
    instance_id: str,
    conversation_id: str,
    question: str,
    conversation_history: list[dict] | None = None,
    model: str | None = None,
    weather_extractor=None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> str:
    """LLM-extract the canonical ``City, Country`` from a FULL weather question.

    The question can carry a greeting ("hi"), a misspelling ("toay"), a region
    name ("north cost egypt"), or a trailing advisory sub-question ("is it
    suitable for beach swimming?"). The LLM's geographic knowledge resolves all
    of that to the single place the user means. Falls back to the host's
    deterministic regex extractor on any failure (never blocks the turn).
    """
    from ai.engine.cognition.context_pack import (
        TASK_WEATHER_QUESTION,
        build_context_pack,
    )
    from ai.engine.llm.router import route_chat

    transcript_lines: list[str] = []
    for turn in (conversation_history or [])[-6:]:
        role = (turn.get("role") or "").strip() or "user"
        content = (turn.get("content") or "").strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)

    user_parts = []
    if transcript:
        user_parts.append(f"Conversation so far:\n{transcript}")
    user_parts.append(f"Weather question: {question}")
    user_parts.append("Canonical 'City, Country':")
    pack = build_context_pack(
        state,
        surface="chat",
        stage="weather_normalize",
        user_info=user_info,
        instance_config=instance_config,
        conversation_history=conversation_history,
        language=language,
        task_body=TASK_WEATHER_QUESTION,
        user_body="\n".join(user_parts),
        include_knowledge=False,
        include_memory=False,
        include_history=False,
    )

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"geo-q-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.0,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("Weather question normalization failed", exc_info=True)
        return _weather_location_fallback(weather_extractor, question)

    text = (result.get("content") or "").strip().splitlines()[0].strip()
    text = text.strip(" .\"'`")
    if not text or len(text) > 60:
        # LLM returned something unusable — fall back to the regex extractor.
        return _weather_location_fallback(weather_extractor, question)
    return text


async def _clarify_no_matches(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    hints: list[str],
    model: str | None = None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> dict | None:
    """Route a ``no_match`` escalation into ONE disambiguating question."""
    from ai.engine.cognition.context_pack import build_context_pack
    from ai.engine.llm.router import route_chat

    pack = build_context_pack(
        state,
        surface="chat",
        stage="escalate",
        user_info=user_info,
        instance_config=instance_config,
        language=language,
        escalate_hints=hints,
        user_body=f"User's question: {user_message}",
        include_history=False,
        include_knowledge=False,
        include_memory=False,
    )
    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"clarify-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.3,
            model=model,
            tools=None,
        )
    except Exception:
        logger.warning("No-match clarification LLM call failed", exc_info=True)
        return None

    text = (result.get("content") or "").strip()
    if not text:
        return None

    tokens = int(result.get("input_tokens", 0) or 0) + int(result.get("output_tokens", 0) or 0)
    return {"text": text, "tokens": tokens, "model": result.get("model", "")}


def _append_evidence_footer(synthesized: str, usable: list[dict]) -> str:
    """No-op — technical tool names are not surfaced to end users."""
    return synthesized


def _render_tool_tables(usable: list[dict]) -> str:
    """Deterministically render GFM markdown tables from structured tool results.

    Covers the known platform data shapes so the synthesis LLM never has to
    format a table itself — it only writes prose around the pre-built tables.
    Returns an empty string when no tabular structure is found.
    """
    import json as _json

    _SCOPE_NAMES = {1: "Scope 1 — Direct", 2: "Scope 2 — Indirect Energy", 3: "Scope 3 — Value Chain"}

    parts: list[str] = []
    for tr in usable:
        result = tr.get("result")
        if result is None:
            continue
        data = result
        if isinstance(result, str):
            try:
                data = _json.loads(result)
            except (TypeError, ValueError):
                continue
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            continue

        by_scope = data.get("by_scope") or {}
        if isinstance(by_scope, dict) and by_scope:
            rows = []
            for k, v in by_scope.items():
                if isinstance(v, dict):
                    name = _SCOPE_NAMES.get(int(k), f"Scope {k}")
                    co2e = float(v.get("total_co2e_kg") or 0)
                    count = v.get("count", 0)
                    rows.append(f"| {name} | {co2e:,.1f} | {count} |")
            if rows:
                parts.append(
                    "| Scope | CO₂e (kg) | Calculations |\n"
                    "|---|---|---|\n" + "\n".join(rows)
                )

        by_module = data.get("by_module") or []
        if isinstance(by_module, list) and by_module:
            rows = []
            for m in by_module[:30]:
                if isinstance(m, dict):
                    name = m.get("module_name") or m.get("module") or "—"
                    co2e = float(m.get("total_co2e_kg") or 0)
                    count = m.get("count", 0)
                    rows.append(f"| {name} | {co2e:,.1f} | {count} |")
            if rows:
                parts.append(
                    "| Module / Branch | CO₂e (kg) | Calculations |\n"
                    "|---|---|---|\n" + "\n".join(rows)
                )

        # Generic list-of-dicts shapes (rows / results / items / records)
        if not parts:
            for key in ("rows", "results", "items", "records"):
                items = data.get(key)
                if isinstance(items, list) and items and isinstance(items[0], dict):
                    cols = list(items[0].keys())[:8]
                    header = "| " + " | ".join(str(c).replace("_", " ").title() for c in cols) + " |"
                    sep = "|" + "|".join(["---"] * len(cols)) + "|"
                    rows = [
                        "| " + " | ".join(str(row.get(c, "")) for c in cols) + " |"
                        for row in items[:50]
                    ]
                    if rows:
                        parts.append("\n".join([header, sep] + rows))
                    break

    return "\n\n".join(parts)


def _wants_visual(user_message: str) -> bool:
    """True when the user explicitly asked for a chart / graph / visual."""
    if not user_message:
        return False
    import re
    return bool(re.search(
        r"\b(chart|charts|graph|graphs|visual|visuals|visualise|visualize|"
        r"plot|plots|diagram|diagrams|pie|bar\s*chart|trend|trends|infographic|figure|figures)\b",
        user_message, re.IGNORECASE))


def _render_tool_charts(usable: list[dict]) -> str:
    """Deterministic Mermaid charts from structured tool results.

    Pie for the scope split (parts of a whole); a bar chart for per-branch
    magnitudes. Mermaid line rules are strict — the fence and every directive
    each sit on their own line. Returns '' when no chartable structure exists.
    """
    import json as _json

    _SCOPE_NAMES = {1: "Scope 1", 2: "Scope 2", 3: "Scope 3"}
    have_pie = False
    have_bar = False
    charts: list[str] = []
    for tr in usable:
        result = tr.get("result")
        if result is None:
            continue
        data = result
        if isinstance(result, str):
            try:
                data = _json.loads(result)
            except (TypeError, ValueError):
                continue
        if isinstance(data, dict) and "status_code" in data and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            continue

        by_scope = data.get("by_scope") or {}
        if isinstance(by_scope, dict) and by_scope and not have_pie:
            slices = []
            for k, v in by_scope.items():
                if isinstance(v, dict):
                    co2e = float(v.get("total_co2e_kg") or 0)
                    if co2e > 0:
                        try:
                            name = _SCOPE_NAMES.get(int(k), f"Scope {k}")
                        except (TypeError, ValueError):
                            name = f"Scope {k}"
                        slices.append(f'    "{name}" : {round(co2e, 1)}')
            if slices:
                charts.append(
                    "```mermaid\npie showData title Emissions by scope (CO2e kg)\n"
                    + "\n".join(slices) + "\n```"
                )
                have_pie = True

        by_module = data.get("by_module") or []
        if isinstance(by_module, list) and by_module and not have_bar:
            labels: list[str] = []
            values: list[float] = []
            for m in by_module[:12]:
                if isinstance(m, dict):
                    name = str(m.get("module_name") or m.get("module") or "-")
                    name = name.replace('"', "'").replace("—", "-").strip()[:20]
                    labels.append(f'"{name}"')
                    values.append(round(float(m.get("total_co2e_kg") or 0), 1))
            if labels and any(values):
                ymax = int(max(values) * 1.1) or 1
                charts.append(
                    "```mermaid\nxychart-beta\n"
                    '    title "Emissions by branch (CO2e kg)"\n'
                    f"    x-axis [{', '.join(labels)}]\n"
                    f'    y-axis "CO2e (kg)" 0 --> {ymax}\n'
                    f"    bar [{', '.join(str(v) for v in values)}]\n```"
                )
                have_bar = True

    return "\n\n".join(charts)


def _envelope_to_markdown(envelope) -> str:
    """Build a clean markdown fallback from a typed envelope.

    Used for copy/export and any non-envelope surface. Renders headline + prose
    + well-formed GFM tables from the typed blocks — never the model's ad-hoc
    markdown — so even the fallback text is structurally valid.
    """
    parts: list[str] = []
    headline = (getattr(envelope, "headline", "") or "").strip()
    if headline:
        parts.append(headline)
    for para in getattr(envelope, "prose", None) or []:
        text = (para or "").strip()
        if text:
            parts.append(text)
    for table in getattr(envelope, "tables", None) or []:
        title = (getattr(table, "title", "") or "").strip()
        columns = list(getattr(table, "columns", None) or [])
        rows = list(getattr(table, "rows", None) or [])
        if not columns:
            continue
        if title:
            parts.append(f"### {title}")
        lines = [
            "| " + " | ".join(str(c) for c in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        parts.append("\n".join(lines))
    for caveat in getattr(envelope, "caveats", None) or []:
        text = (getattr(caveat, "text", "") or "").strip()
        if text:
            parts.append(f"> {text}")
    return "\n\n".join(parts).strip()


async def _stream_final_text(text: str, *, stream_callback, progress_callback) -> None:
    """Stream a finished answer to the UI in 80-char chunks.

    Emits the ``Composing response…`` thinking cue first, then streams the
    text progressively so the user sees movement during the final render.
    Shared by BOTH the markdown-synthesis path and the typed-envelope path so
    data answers also stream and show the thinking indicator.
    """
    if not stream_callback or not text:
        return
    if progress_callback:
        try:
            await progress_callback("Composing response…")
        except Exception:
            pass
    pos = 0
    while pos < len(text):
        end = min(pos + 80, len(text))
        try:
            await stream_callback(text[pos:end])
        except Exception:
            break
        pos = end


def _failed_tools_for_recovery(completed_tools: list[dict]) -> list[dict]:
    """Tools that failed (top-level error or host non-2xx envelope)."""
    import json as _json

    failed: list[dict] = []
    for tr in completed_tools or []:
        if not isinstance(tr, dict):
            continue
        if tr.get("error"):
            failed.append(tr)
            continue
        if tr.get("requires_confirmation"):
            continue
        raw = tr.get("result")
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("error"):
            failed.append(tr)
            continue
        try:
            code = int(data.get("status_code")) if data.get("status_code") is not None else None
        except (TypeError, ValueError):
            code = None
        if code is not None and code >= 400:
            failed.append(tr)
    return failed


def _render_tool_failures_for_recovery(failed_tools: list[dict]) -> str:
    """Compact, outcome-oriented failure payload for recovery synthesis."""
    import json as _json

    sections: list[str] = []
    for tr in failed_tools:
        name = str(tr.get("tool_name") or "tool")
        args = tr.get("tool_args") if isinstance(tr.get("tool_args"), dict) else {}
        api = str(args.get("api_name") or args.get("api") or "")
        if ":" in name and not api:
            api = name.split(":", 1)[1]
        err = str(tr.get("error") or "").strip()
        raw = tr.get("result")
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            data = None
        payload: dict = {"tool": name}
        if api:
            payload["api_name"] = api
        if err:
            payload["error"] = err[:400]
        if isinstance(data, dict):
            inner = data.get("data") if isinstance(data.get("data"), dict) else data
            if isinstance(inner, dict):
                for key in ("detail", "error_kind", "hints", "remaining", "message"):
                    if key in inner and inner[key] is not None:
                        payload[key] = inner[key]
            if data.get("status_code") is not None:
                payload["status_code"] = data.get("status_code")
        sections.append(_json.dumps(payload, default=str, ensure_ascii=False))
    return "\n".join(sections)


def _deterministic_failure_reply(failed_tools: list[dict], user_message: str = "") -> str:
    """RULE_23 fallback when recovery LLM is unavailable."""
    import json as _json

    from ai.engine_runtime import fail_reply_when_all_tools_failed

    details: list[str] = []
    for tr in failed_tools:
        err = str(tr.get("error") or "").strip()
        raw = tr.get("result")
        try:
            data = _json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            data = None
        detail = err
        kind = ""
        suggestion = ""
        if isinstance(data, dict):
            inner = data.get("data") if isinstance(data.get("data"), dict) else data
            if isinstance(inner, dict):
                detail = str(inner.get("detail") or detail or "").strip()
                kind = str(inner.get("error_kind") or "").strip()
                hints = inner.get("hints") if isinstance(inner.get("hints"), dict) else {}
                suggestion = str(hints.get("suggestion") or "").strip()
        if detail:
            details.append(detail)
        if suggestion and suggestion not in details:
            details.append(suggestion)
        elif kind == "overlap" and "Pick another day" not in " ".join(details):
            details.append("Pick another day that is free.")
        elif kind == "insufficient_balance" and "another leave type" not in " ".join(details).lower():
            details.append("Pick another leave type or a shorter period.")
        elif kind == "invalid_leave_type" and "allowed" not in " ".join(details).lower():
            details.append("Use a recognised leave type (for example emergency for عارضة).")

    base = fail_reply_when_all_tools_failed(failed_tools)
    if not details:
        return base
    # Prefer the host outcome; keep one clear next step.
    body = details[0]
    extra = details[1] if len(details) > 1 else ""
    if extra:
        return f"{body} {extra}"
    # If we only have a detail, still invite a next step for mutations.
    if "try again" not in body.lower() and "pick" not in body.lower():
        return f"{body} What would you like to change?"
    return body


async def _synthesize_tool_failures(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    completed_tools: list[dict],
    model: str | None = None,
    stream_callback=None,
    progress_callback=None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> dict | None:
    """ADR-0021 failure branch — turn host/tool errors into grounded guidance.

    Does NOT auto-retry mutations (RULE_21). Does NOT invent success (anti-
    fabrication). Prefer host ``detail`` / ``error_kind`` over generic refuse.
    """
    failed = _failed_tools_for_recovery(completed_tools)
    if not failed:
        return None

    if progress_callback:
        try:
            await progress_callback("Working out what went wrong…")
        except Exception:
            pass

    failures_text = _render_tool_failures_for_recovery(failed)
    from ai.engine.cognition.context_pack import build_context_pack

    pack = build_context_pack(
        state,
        surface="chat",
        stage="recovery",
        user_info=user_info,
        instance_config=instance_config,
        language=language,
        user_body=(
            f"User's message: {user_message}\n\n"
            f"Tool failures (JSON lines):\n{failures_text}"
        ),
        include_history=False,
        include_knowledge=False,
        include_memory=False,
    )
    try:
        from ai.engine.llm.router import route_chat

        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"recovery-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
            ],
            temperature=0.2,
            model=model,
            tools=None,
        )
        synthesized = (result.get("content") or "").strip()
        if synthesized:
            # Strip accidental success claims / invention meta.
            low = synthesized.lower()
            if any(p in low for p in (
                "successfully submitted", "has been submitted",
                "was created", "no answer was invented",
            )):
                synthesized = ""
            if synthesized:
                await _stream_final_text(
                    synthesized,
                    stream_callback=stream_callback,
                    progress_callback=progress_callback,
                )
                tokens = int(result.get("input_tokens", 0) or 0) + int(
                    result.get("output_tokens", 0) or 0
                )
                return {
                    "text": synthesized,
                    "tokens": tokens,
                    "model": result.get("model", ""),
                    "is_recovery": True,
                }
    except Exception:
        logger.warning("Tool-failure recovery LLM call failed", exc_info=True)

    fallback = _deterministic_failure_reply(failed, user_message)
    await _stream_final_text(
        fallback,
        stream_callback=stream_callback,
        progress_callback=progress_callback,
    )
    return {"text": fallback, "tokens": 0, "model": model or "", "is_recovery": True}


async def _synthesize_tool_results(
    *,
    instance_id: str,
    conversation_id: str,
    user_message: str,
    completed_tools: list[dict],
    draft_text: str,
    model: str | None = None,
    delivery: str = "explain",
    envelope_synthesizer=None,
    stream_callback=None,
    progress_callback=None,
    user_info: dict | None = None,
    instance_config: dict | None = None,
    language: str = "",
    state=None,
) -> dict | None:
    """Ask the LLM to write a grounded final answer from executed tool results.

    Fires only when tools returned usable data AND the draft prose is empty or
    a short "promise to fetch" (the common tool-only turn where the model
    writes "I'll fetch …" and the fetched data is otherwise discarded).

    ``no_match`` results are never data: they are escalated — either into a
    single disambiguating question (when nothing usable remains) or into an
    honesty directive appended to the synthesis prompt (when usable data also
    exists) — instead of being handed to the LLM as if they were found values.

    Returns ``{"text", "tokens", "model"}`` on success, or ``None`` when
    synthesis is unnecessary or the call fails (callers keep the original).
    """
    usable: list[dict] = []
    no_matches: list[dict] = []
    for tr in completed_tools or []:
        if tr.get("error"):
            continue
        if tr.get("requires_confirmation"):
            continue
        if tr.get("result") is None:
            continue
        if payload_status(tr.get("result")) == "no_match":
            no_matches.append(tr)
            continue
        usable.append(tr)

    # B5: compensation CBAC deny → fixed prose (never LLM soft-empty mix).
    try:
        from ai.engine.agent.tools import compensation_authz_deny_message

        _deny_text = compensation_authz_deny_message(completed_tools)
    except Exception:  # noqa: BLE001
        _deny_text = None
    if _deny_text:
        await _stream_final_text(
            _deny_text,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        return {"text": _deny_text, "tokens": 0, "model": model or ""}

    hints = _no_match_hints(no_matches)

    # Precedence 1: nothing usable but some no_match → the tool could not
    # resolve the user's entities. Ask ONE clarifying question instead of
    # falling through to the deterministic summary with a raw no_match payload
    # (which would otherwise read like city-history-as-weather). This fires
    # even when the draft prose is non-empty (a bare "I'll fetch …" promise).
    if no_matches and not usable:
        result = await _clarify_no_matches(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            hints=hints,
            model=model,
            user_info=user_info,
            instance_config=instance_config,
            language=language,
            state=state,
        )
        if result is not None:
            result["is_clarification"] = True
            result["clarification_hints"] = hints
            result["clarification_user_message"] = user_message
        return result

    if not usable:
        # ADR-0021 failure branch — grounded recovery from tool errors
        # (leave validation deny, boundary refuse, …). Never invent success;
        # never auto-retry mutations (RULE_21).
        return await _synthesize_tool_failures(
            instance_id=instance_id,
            conversation_id=conversation_id,
            user_message=user_message,
            completed_tools=completed_tools,
            model=model,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
            user_info=user_info,
            instance_config=instance_config,
            language=language,
            state=state,
        )

    results_text = _render_tool_results_for_synthesis(usable)
    if not results_text.strip():
        return None

    # [PAQ-2A/2B] Typed Answer Envelope. When enabled and the tools returned
    # structured data, synthesize the envelope FIRST — even when the model
    # already wrote a long markdown draft — so data answers render as typed
    # blocks (deterministic tables/charts) instead of ad-hoc markdown the model
    # frequently malforms. Fail-open: any error folds to ``None`` and the
    # markdown path below runs unchanged.
    envelope = None
    if progress_callback:
        try:
            await progress_callback("Analysing data…")
        except Exception:
            pass
    if get_settings().PULSE_ENVELOPE_ENABLED and envelope_synthesizer is not None:
        try:
            envelope = await envelope_synthesizer(
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message=user_message,
                usable_tools=usable,
                model=model,
            )
        except Exception:  # noqa: BLE001 - envelope must never break the turn
            logger.warning("Envelope synthesis failed", exc_info=True)
            envelope = None

    # When the envelope carries data blocks it BECOMES the answer, regardless of
    # draft length: the frontend renders the typed blocks and the markdown
    # fallback (copy/export/non-envelope surfaces) is built from the envelope's
    # own headline + prose + clean GFM tables — never the model's ad-hoc tables.
    if envelope is not None and (envelope.tables or envelope.charts):
        _env_text = _envelope_to_markdown(envelope)
        if _wants_visual(user_message) and "```mermaid" not in _env_text:
            _charts = _render_tool_charts(usable)
            if _charts:
                _env_text = f"{_env_text}\n\n{_charts}"
        await _stream_final_text(
            _env_text,
            stream_callback=stream_callback,
            progress_callback=progress_callback,
        )
        return {
            "text": _env_text,
            "tokens": 0,
            "model": model or "",
            "envelope": envelope.model_dump(),
        }

    stripped = (draft_text or "").strip()
    # No usable envelope data blocks — keep the existing markdown behaviour: a
    # substantial prose answer already exists → don't re-synthesize.
    #
    # EXCEPTION (no-data hallucination net): when the draft falsely claims
    # "no data" while the executed tools actually returned data, the draft is a
    # history-poisoned hallucination and MUST be re-synthesized from the real
    # tool results. The synthesis prompt below carries a hard NON-EMPTY GUARD
    # (never say "no data" when usable tools returned data), so forcing this
    # path guarantees a factual answer instead of silently keeping "no data".
    if len(stripped) >= 300:
        from ai.engine.cognition.turn.verify import detect_no_data_contradiction

        draft_contradicts_data = bool(
            detect_no_data_contradiction(stripped, usable)
        )
        if not draft_contradicts_data:
            # Even when the model's own draft is kept, honour an explicit
            # request for visuals by appending deterministic charts it omitted.
            if _wants_visual(user_message) and "```mermaid" not in stripped:
                _charts = _render_tool_charts(usable)
                if _charts:
                    delta = "\n\n" + _charts
                    if stream_callback:
                        try:
                            await stream_callback(delta)
                        except Exception:
                            pass
                    return {"text": draft_text.rstrip() + delta,
                            "tokens": 0, "model": model or ""}
            return None

    from ai.engine.cognition.context_pack import build_context_pack
    from ai.engine.llm.router import route_chat

    delivery_guide = _DELIVERY_SYNTHESIS.get(delivery or "explain", _DELIVERY_SYNTHESIS["explain"])
    pack = build_context_pack(
        state,
        surface="chat",
        stage="synthesis",
        user_info=user_info,
        instance_config=instance_config,
        language=language,
        delivery_guide=delivery_guide,
        hints=hints or None,
        user_body=(
            f"User's question: {user_message}\n\n"
            f"Tool results (JSON):\n{results_text}"
        ),
        include_history=False,
        include_knowledge=False,
        include_memory=False,
    )

    pre_tables = _render_tool_tables(usable)
    pre_charts = _render_tool_charts(usable) if _wants_visual(user_message) else ""

    try:
        result = await route_chat(
            task="cognition",
            instance_id=instance_id,
            conversation_id=f"synthesis-{conversation_id}",
            messages=[
                {"role": "system", "content": pack.system_prompt()},
                {"role": "user", "content": pack.user_prompt()},
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

    # Inject deterministically-rendered tables after the LLM prose.
    if pre_tables:
        synthesized = synthesized + "\n\n" + pre_tables
    if pre_charts and "```mermaid" not in synthesized:
        synthesized = synthesized + "\n\n" + pre_charts

    # Stream the synthesized text so the UI shows progress.
    await _stream_final_text(
        synthesized,
        stream_callback=stream_callback,
        progress_callback=progress_callback,
    )

    tokens = int(result.get("input_tokens", 0) or 0) + int(result.get("output_tokens", 0) or 0)
    synthesized_result = {"text": synthesized, "tokens": tokens, "model": result.get("model", "")}
    if envelope is not None:
        synthesized_result["envelope"] = envelope.model_dump()
    return synthesized_result


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
        weather_extractor=None,
        envelope_synthesizer=None,
        domain_context_assembler=None,
    ):
        self.llm_client = llm_client
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager
        self.executor = executor
        self.db = db
        # P2-03: host-provided services. ``weather_extractor`` exposes
        # ``is_weather_query`` / ``extract_weather_location``; None means the
        # feature degrades to a no-op (weather rewrite never fires). The
        # engine never imports ``ai.plugins.web_research`` / ``ai.envelope_service``.
        self.weather_extractor = weather_extractor
        self.envelope_synthesizer = envelope_synthesizer
        self.domain_context_assembler = domain_context_assembler
        # Curated tool set exposed to the S3 planner when an executor is
        # wired. Mutation/confirmation tools (create_dq_rule) plus read tools
        # that ground answers, including call_host_api so the planner can reach
        # the live host endpoints listed in the system prompt.
        self._draft_tools: list[dict] | None = None
        if executor is not None:
            try:
                from ai.engine.agent.tools import get_tool_definitions

                # Chat-visible tool set = spine ∪ chat-visible plugins ∪ ECF
                # tools when ECF_ENABLED (name resolve must not fall to KG).
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
        """Execute one turn under a turn-scoped LLM call meter.

        PV2-1A: the durable ConversationState is loaded before the pipeline
        and saved after it — every ``return`` in :meth:`_run_metered` exits
        through here, so state is written on every completed turn.

        Returns (AgentResponse, TurnLedger). See :meth:`_run_metered`.
        """
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
            )
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
        # P4-02 — host-supplied applicability-first curated knowledge.  The
        # S2 retrieval witness consumes these directly (optional; None keeps
        # the graph semantic path only).
        knowledge_items: list | None = None,
        scope: dict | None = None,
        process_state: dict | None = None,
        *,
        meter=None,
        state_ctx=None,
    ) -> tuple:
        """Execute one turn. Returns (AgentResponse, TurnLedger)."""
        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor

        settings = get_settings()

        # Apply per-instance tool exclusions (e.g. an instance hides create_dq_rule).
        excluded_tools = set((instance_config or {}).get("excluded_tools") or [])
        if excluded_tools and self._draft_tools is not None:
            self._draft_tools = [
                d for d in self._draft_tools
                if d.get("function", {}).get("name") not in excluded_tools
            ]
        from ai.engine.llm.call_meter import stage

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
        _pending_fired = False
        try:
            from ai.engine.cognition.dialogue.pending_action import (
                get_pending_action_store,
            )
            _pending_store = get_pending_action_store()
            _pending = _pending_store.check_confirmation(conversation_id, user_message)
            if _pending and self.executor is not None and instance_id:
                _pending_fired = True
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
                _signal(ledger, "pending_confirm", True, action="memory_confirm")
                _finalize_meter(ledger, meter, "memory_confirm")
                return response, ledger
        except Exception:  # noqa: BLE001 - memory hook must never block the turn
            logger.warning(
                "[%s] Pending-confirmation short-circuit failed; "
                "continuing normal pipeline",
                turn_id[:8], exc_info=True,
            )
        _signal(ledger, "pending_confirm", _pending_fired)

        # ── [NAV-GATE] Deterministic zero-token navigation fast path ──
        # The canonical comprehension path is the LLM intent classifier, but
        # this exact-match fast path is free and injection-proof for the common
        # case. Both paths converge on the same grounding + propose→confirm.
        # Agent→Discuss threads must never short-circuit to "open Payroll"
        # (or any app) — the brief often names a module the user is planning,
        # not a place they want to navigate.
        from ai.engine.cognition.plan.planner import (
            _history_has_discuss_markers,
            _is_agent_discuss_context,
            _is_agent_discuss_turn,
            _is_discuss_apply_turn,
        )
        _discuss_ctx = _is_agent_discuss_context(
            user_message, conversation_history,
        )
        _discuss_thread = (
            _discuss_ctx
            or _is_agent_discuss_turn(user_message)
            or _history_has_discuss_markers(conversation_history)
        )
        _nav_fast_fired = False
        if settings.NAVIGATION_RESOLVER_ENABLED and not _discuss_thread:
            try:
                from ai.engine.cognition.turn.process_brief import (
                    is_deliverable_request,
                    is_process_briefing,
                )
                from ai.engine.cognition.turn.navigation import resolve_navigation

                # Process / lifecycle briefing mentions place nouns ("leave",
                # "payroll") but must NEVER short-circuit to open-app propose.
                # Deliverable asks ("تقرير عن المرتبات … word") likewise.
                if is_process_briefing(user_message):
                    logger.info(
                        "[%s] Skipping navigation fast-path (process briefing)",
                        turn_id[:8],
                    )
                    _signal(ledger, "nav_fast_path", False, reason="process_briefing")
                elif is_deliverable_request(user_message):
                    logger.info(
                        "[%s] Skipping navigation fast-path (deliverable request)",
                        turn_id[:8],
                    )
                    _signal(ledger, "nav_fast_path", False, reason="deliverable_request")
                else:
                    _nav = resolve_navigation(user_message, instance_config)
                    if _nav.action in ("navigate", "disambiguate"):
                        _nav_fast_fired = True
                        total_latency = (time.monotonic() - t0) * 1000
                        await self._write_ledger_row(
                            turn_id, instance_id, conversation_id, host_user_id,
                            "final", 5,
                            {
                                "total_latency_ms": total_latency,
                                "total_tokens": 0,
                                "total_llm_calls": 0,
                                "navigation_shortcircuit": _nav.action,
                                "navigation_source": "deterministic_fast_path",
                                "navigation_targets": [t.route for t in _nav.targets],
                            },
                            total_latency, verdict="pass",
                        )
                        if self.db is not None:
                            await self.db.commit()

                        ledger.final_response = _navigation_text(_nav)[:500]
                        ledger.total_latency_ms = total_latency
                        ledger.intent_zone = "platform"

                        response = _navigation_response(_nav)
                        await _broadcast_run(instance_id, "run.completed", {
                            "run_id": turn_id,
                            "total_latency_ms": total_latency,
                            "total_tokens": 0,
                            "total_llm_calls": 0,
                            "navigation_shortcircuit": _nav.action,
                        })
                        _signal(ledger, "nav_fast_path", True, action=_nav.action)
                        _finalize_meter(ledger, meter, "navigate")
                        return response, ledger
                    _signal(
                        ledger, "nav_fast_path", False,
                        action=getattr(_nav, "action", "none"),
                    )
            except Exception:  # noqa: BLE001 - navigation gate must never block the turn
                logger.warning(
                    "[%s] Navigation short-circuit failed; continuing normal pipeline",
                    turn_id[:8], exc_info=True,
                )
                _signal(ledger, "nav_fast_path", False, error="exception")
        elif _discuss_thread and settings.NAVIGATION_RESOLVER_ENABLED:
            logger.info(
                "[%s] Skipping navigation short-circuit (Agent discuss thread)",
                turn_id[:8],
            )
            _signal(ledger, "nav_fast_path", False, reason="discuss_thread")
        elif not settings.NAVIGATION_RESOLVER_ENABLED:
            _signal(ledger, "nav_fast_path", False, reason="disabled")
        if not _nav_fast_fired and ledger.decision_signals is not None:
            if not any(
                s.get("gate") == "nav_fast_path" for s in ledger.decision_signals
            ):
                _signal(ledger, "nav_fast_path", False)

        # Also run process briefing *before* salience when nav was skipped —
        # zero-token concept answer for governed process ids.
        _process_brief_early_fired = False
        if not _discuss_thread:
            try:
                from asgiref.sync import sync_to_async
                from ai.engine.cognition.turn.process_brief import try_process_briefing

                _early_brief = await sync_to_async(
                    try_process_briefing, thread_sensitive=True,
                )(user_message)
                if _early_brief is not None:
                    _process_brief_early_fired = True
                    _pid, _brief_text = _early_brief
                    total_latency = (time.monotonic() - t0) * 1000
                    ledger.intent_zone = "concept"
                    ledger.final_response = _brief_text[:500]
                    ledger.total_latency_ms = total_latency
                    response = AgentResponse(
                        text=_brief_text,
                        sources_cited=[],
                        tools_used=[],
                        confidence=1.0,
                        total_tokens=0,
                        llm_calls=0,
                        model="",
                        response_type="inferred",
                        actions=[],
                    )
                    await _broadcast_run(instance_id, "run.completed", {
                        "run_id": turn_id,
                        "process_briefing": _pid,
                        "navigation_source": "skipped_for_process_brief",
                    })
                    _signal(ledger, "process_brief_early", True, process_id=_pid)
                    _finalize_meter(ledger, meter, "process_brief")
                    return response, ledger
            except Exception:  # noqa: BLE001
                logger.warning(
                    "[%s] Process briefing early gate failed; continuing",
                    turn_id[:8], exc_info=True,
                )
        _signal(ledger, "process_brief_early", _process_brief_early_fired)

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
        _signal(
            ledger, "salience", False,
            domain=salience.domain, route=salience.route,
        )
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

        # [WEATHER-FT] If the previous turn stored a pending weather intent,
        # and the user's current message looks like a bare location answer
        # (no weather keywords), rewrite it so the weather tool re-fires.
        _is_wq = self._is_weather_query
        _wm_focus_now = _wm.get_focus(conversation_id)
        _is_weather_rewrite_turn = False
        if (
            _wm_focus_now is not None
            and _wm_focus_now.entity_type == "pending_weather"
            and not _is_wq(user_message)
        ):
            _pending_weather_query = _wm_focus_now.entity
            # Normalize the location answer (correct typos, region → city) so the
            # keyless exact-match geocoder resolves it instead of no-matching.
            # Grounded in the conversation so far (the assistant's prior
            # clarification listed the candidate cities the user is choosing).
            with stage("weather_normalize"):
                _normalized_location = await _normalize_weather_location(
                    instance_id=instance_id,
                    conversation_id=conversation_id,
                    original_question=_pending_weather_query,
                    user_reply=user_message.strip(),
                    conversation_history=conversation_history,
                    model=model,
                    user_info=user_info,
                    instance_config=instance_config,
                    state=state_ctx.state if state_ctx is not None else None,
                )
            user_message = f"weather in {_normalized_location}"
            logger.info(
                "[WEATHER-FT] Rewrote bare location reply to: %r", user_message
            )
            _is_weather_rewrite_turn = True
            # Clear the pending intent — it's been consumed.
            _wm.set_focus(conversation_id, user_message, "weather_resolution")

        _entity = EntityExtractor().extract(user_message)
        if _entity:
            _wm.set_focus(conversation_id, _entity.name, _entity.entity_type)
        _pref_store = get_session_preference_store()
        if host_user_id:
            try:
                from asgiref.sync import sync_to_async as _pref_s2a

                await _pref_s2a(_pref_store.update, thread_sensitive=True)(
                    host_user_id, PreferenceClassifier().classify(user_message)
                )
            except Exception as _e:  # noqa: BLE001 - preference persist is best-effort
                logger.warning(
                    "[GAP-4] preference persist failed user=%s: %s",
                    host_user_id, _e,
                )

        # Track C (ux-07): deixis gate BEFORE intent/tools — "check that one"
        # must ask confirm, never invent a KG search Answer. Always on (not
        # tied to INTENT_RESOLVER_ENABLED).
        try:
            from ai.engine.cognition.dialogue.deixis import should_gate_deixis

            _deixis_q = should_gate_deixis(
                user_message, conversation_history=conversation_history
            )
            if _deixis_q:
                try:
                    from ai.pulse_ux_telemetry import emit_ux
                    emit_ux("chat.deixis_gate", has_topic="**" in _deixis_q)
                except Exception:  # noqa: BLE001
                    pass
                total_latency = (time.monotonic() - t0) * 1000
                await self._write_ledger_row(
                    turn_id, instance_id, conversation_id, host_user_id,
                    "final", 5,
                    {
                        "total_latency_ms": total_latency,
                        "total_tokens": total_tokens,
                        "total_llm_calls": total_llm_calls,
                        "intent_shortcircuit": "deixis",
                    },
                    total_latency, verdict="pass",
                )
                if self.db is not None:
                    await self.db.commit()
                ledger.final_response = _deixis_q[:500]
                ledger.total_latency_ms = total_latency
                ledger.total_tokens = total_tokens
                ledger.total_llm_calls = total_llm_calls
                response = AgentResponse(
                    text=_deixis_q,
                    sources_cited=[],
                    tools_used=[],
                    confidence=0.75,
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
                    "intent_shortcircuit": "deixis",
                })
                _signal(ledger, "deixis", True)
                _finalize_meter(ledger, meter, "clarify")
                return response, ledger
        except Exception:
            logger.warning(
                "[%s] Deixis gate failed; continuing",
                turn_id[:8], exc_info=True,
            )
        _signal(ledger, "deixis", False)

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
                with stage("intent"):
                    _intent_resolution = await IntentResolver().resolve(
                        user_message=_resolved_for_intent,
                        api_catalog=_scoped_api_catalog(instance_config, user_info),
                        navigation_routes=_scoped_navigation_routes(
                            instance_config, user_info,
                        ),
                        tenant_org=(instance_config or {}).get("tenant_org"),
                        conversation_history=conversation_history,
                        instance_id=instance_id,
                        conversation_id=conversation_id,
                        db=self.db,
                        model=settings.INTENT_RESOLVER_MODEL or None,
                        min_confidence=settings.INTENT_RESOLVER_MIN_CONFIDENCE,
                        ambiguity_gap=settings.INTENT_RESOLVER_AMBIGUITY_GAP,
                        user_info=user_info,
                        instance_config=instance_config,
                        state=state_ctx.state if state_ctx is not None else None,
                    )
            except Exception:
                logger.warning(
                    "[%s] Intent resolution failed; continuing without it",
                    turn_id[:8], exc_info=True,
                )

        if state_ctx is not None:
            state_ctx.intent = _intent_resolution
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

            # [PROCESS BRIEF] Explain governed process / lifecycle steps —
            # never a navigate short-circuit to People & Payroll (P0).
            if not _discuss_thread:
                from asgiref.sync import sync_to_async
                from ai.engine.cognition.turn.process_brief import try_process_briefing

                _brief = await sync_to_async(
                    try_process_briefing, thread_sensitive=True,
                )(user_message)
                if _brief is not None:
                    _pid, _brief_text = _brief
                    total_latency = (time.monotonic() - t0) * 1000
                    await self._write_ledger_row(
                        turn_id, instance_id, conversation_id, host_user_id,
                        "final", 5,
                        {
                            "total_latency_ms": total_latency,
                            "total_tokens": total_tokens,
                            "total_llm_calls": total_llm_calls,
                            "process_briefing": _pid,
                        },
                        total_latency, verdict="pass",
                    )
                    if self.db is not None:
                        await self.db.commit()
                    ledger.final_response = _brief_text[:500]
                    ledger.total_latency_ms = total_latency
                    ledger.total_tokens = total_tokens
                    ledger.total_llm_calls = total_llm_calls
                    response = AgentResponse(
                        text=_brief_text,
                        sources_cited=[],
                        tools_used=[],
                        confidence=1.0,
                        total_tokens=total_tokens,
                        llm_calls=total_llm_calls,
                        model="",
                        response_type="inferred",
                        actions=[],
                    )
                    await _broadcast_run(instance_id, "run.completed", {
                        "run_id": turn_id,
                        "total_latency_ms": total_latency,
                        "total_tokens": total_tokens,
                        "total_llm_calls": total_llm_calls,
                        "process_briefing": _pid,
                    })
                    _signal(ledger, "process_brief", True, process_id=_pid)
                    _signal(ledger, "intent_short_circuit", False, action="process_brief")
                    _signal(ledger, "nav_ground", False)
                    _signal(ledger, "off_limits", False)
                    _finalize_meter(ledger, meter, "process_brief")
                    return response, ledger

            # [NAV] LLM-recognised navigation: ground the target *concept*
            # against the enumerated routes and propose→confirm (RULE_21 — no
            # auto-jump). The LLM's comprehension drives this; grounding is the
            # deterministic guard that prevents the "People (HRMS)" hallucination.
            # Skip entirely during Agent→Discuss threads (brief often names a
            # module; user is refining a plan, not asking to open an app).
            # Also skip when the utterance is a deliverable ask (report/Word/…)
            # that merely mentions a place noun — LLM may still emit navigate.
            from ai.engine.cognition.turn.process_brief import is_deliverable_request as _is_deliv
            if (
                not _discuss_thread
                and not _is_deliv(user_message)
                and _intent_resolution.action == "navigate"
                and _intent_resolution.navigate_target
            ):
                from ai.engine.cognition.turn.navigation import ground_navigation
                _nav = ground_navigation(_intent_resolution.navigate_target, instance_config)
                if _nav.action in ("navigate", "disambiguate"):
                    total_latency = (time.monotonic() - t0) * 1000
                    await self._write_ledger_row(
                        turn_id, instance_id, conversation_id, host_user_id,
                        "final", 5,
                        {
                            "total_latency_ms": total_latency,
                            "total_tokens": total_tokens,
                            "total_llm_calls": total_llm_calls,
                            "navigation_shortcircuit": _nav.action,
                            "navigation_source": "llm_intent",
                            "navigation_targets": [t.route for t in _nav.targets],
                        },
                        total_latency, verdict="pass",
                    )
                    if self.db is not None:
                        await self.db.commit()

                    ledger.final_response = _navigation_text(_nav)[:500]
                    ledger.total_latency_ms = total_latency
                    ledger.total_tokens = total_tokens
                    ledger.total_llm_calls = total_llm_calls

                    response = _navigation_response(
                        _nav, total_tokens=total_tokens, total_llm_calls=total_llm_calls,
                    )
                    await _broadcast_run(instance_id, "run.completed", {
                        "run_id": turn_id,
                        "total_latency_ms": total_latency,
                        "total_tokens": total_tokens,
                        "total_llm_calls": total_llm_calls,
                        "navigation_shortcircuit": _nav.action,
                    })
                    _signal(ledger, "nav_ground", True, action=_nav.action)
                    _signal(ledger, "process_brief", False)
                    _signal(ledger, "intent_short_circuit", False, action="navigate")
                    _signal(ledger, "off_limits", False)
                    _finalize_meter(ledger, meter, "navigate")
                    return response, ledger
                _signal(ledger, "nav_ground", False, action="navigate")
                # else: navigation intent but the concept didn't ground to any
                # declared destination → fall through to the normal pipeline.
            else:
                _signal(ledger, "nav_ground", False)

            # [S1.5-zone] Hard refuse — off_limits (jailbreak/PII/security) is a
            # GATE layered on top of any zone. Mirrors the clarify/disambiguate
            # shortcircuit exactly: a proper persisted assistant message, never
            # an HTTP error.
            # Confirm replies ("yes" / "نعم") must never hard-refuse: they
            # continue a prior in-scope turn (leave submit, memory, deixis).
            # Mis-classifying them as off_limits produced Carbon-branded refuse
            # copy on Nibras Arabic leave confirmations.
            if _intent_resolution.zone == "off_limits":
                from ai.engine.cognition.dialogue.deixis import is_confirm_reply
                if is_confirm_reply(user_message):
                    _intent_resolution.zone = "platform"
                    logger.info(
                        "[%s] Confirm reply reclassified off_limits → platform",
                        turn_id[:8],
                    )
            # An ask naming a declared in-scope topic (loan/leave/payroll/…)
            # is a misclassification, not a scope violation (F-LIVE-1).
            _off_limits_override = ""
            if (
                _intent_resolution.zone == "off_limits"
                and _is_declared_in_scope(user_message, instance_config)
            ):
                _intent_resolution.zone = "platform"
                ledger.intent_zone = "platform"
                _off_limits_override = "declared_in_scope"
                logger.info(
                    "[%s] In-scope ask reclassified off_limits → platform",
                    turn_id[:8],
                )
            if _intent_resolution.zone == "off_limits":
                _refuse_text = _refusal_text(instance_config, user_message)
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
                _signal(ledger, "off_limits", True, zone="off_limits")
                _signal(ledger, "intent_short_circuit", True, action="off_limits")
                _signal(ledger, "process_brief", False)
                _finalize_meter(ledger, meter, "refuse")
                return response, ledger
            if _off_limits_override:
                _signal(
                    ledger, "off_limits", False,
                    zone=_intent_resolution.zone, override=_off_limits_override,
                )
            else:
                _signal(ledger, "off_limits", False, zone=_intent_resolution.zone)

            # Confidence ladder short-circuits: ask / offer options instead of
            # guessing. These return before S2/S3 so no hallucinated tool runs.
            # [WEATHER-FT] Skip the shortcircuit if this turn is a pending-weather
            # resolution — let the rewritten message reach tool execution instead.
            if _intent_resolution.action in ("clarify", "disambiguate") and not _is_weather_rewrite_turn:
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
                # [WEATHER-FT] Store pending_weather so the next turn (location
                # confirmation) re-routes into web_research._weather.
                if _is_wq(user_message):
                    _wm.set_focus(conversation_id, user_message, "pending_weather")
                    logger.info(
                        "[WEATHER-FT] Intent shortcircuit — stored pending_weather: %r",
                        user_message,
                    )
                _signal(
                    ledger, "intent_short_circuit", True,
                    action=_intent_resolution.action,
                )
                _signal(ledger, "process_brief", False)
                _finalize_meter(ledger, meter, "clarify")
                return response, ledger
            _signal(
                ledger, "intent_short_circuit", False,
                action=_intent_resolution.action,
            )
            _signal(ledger, "process_brief", False)
        else:
            _signal(ledger, "intent_short_circuit", False, action="none")
            _signal(ledger, "process_brief", False)
            _signal(ledger, "nav_ground", False)
            _signal(ledger, "off_limits", False)

        # [PROCESS BRIEF] Fallback when intent resolver was disabled / None —
        # still never navigate for lifecycle explanations.
        if not _discuss_thread:
            from asgiref.sync import sync_to_async
            from ai.engine.cognition.turn.process_brief import try_process_briefing

            _brief_fb = await sync_to_async(
                try_process_briefing, thread_sensitive=True,
            )(user_message)
            if _brief_fb is not None:
                _pid, _brief_text = _brief_fb
                total_latency = (time.monotonic() - t0) * 1000
                ledger.intent_zone = "concept"
                ledger.final_response = _brief_text[:500]
                ledger.total_latency_ms = total_latency
                response = AgentResponse(
                    text=_brief_text,
                    sources_cited=[],
                    tools_used=[],
                    confidence=1.0,
                    total_tokens=total_tokens,
                    llm_calls=total_llm_calls,
                    model="",
                    response_type="inferred",
                    actions=[],
                )
                await _broadcast_run(instance_id, "run.completed", {
                    "run_id": turn_id,
                    "process_briefing": _pid,
                })
                _signal(ledger, "process_brief", True, process_id=_pid)
                _finalize_meter(ledger, meter, "process_brief")
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
            knowledge_items=knowledge_items,
            scope=scope,
            process_state=process_state,
            host_user_id=str(host_user_id) if host_user_id else None,
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

        # ── PV2-3B: Chat write handoff (before fan-out / ReAct) ────────────
        # ESS write with enough bound slots → handoff_agent; never stage.
        # Incomplete slots seed ConversationState and fall through to clarify.
        _chat_handoff = await self._try_chat_write_handoff(
            user_message=user_message,
            conversation_history=conversation_history,
            state_ctx=state_ctx,
            instance_config=instance_config,
        )
        if _chat_handoff is not None:
            return await self._return_chat_handoff(
                outcome=_chat_handoff,
                ledger=ledger,
                meter=meter,
                turn_id=turn_id,
                instance_id=instance_id,
                conversation_id=conversation_id,
                host_user_id=host_user_id,
                t0=t0,
            )

        # ── P3.2: Orchestrator fan-out gate (after S2, before PR-20) ──────
        # If an orchestrator agent is active and the user message warrants
        # parallel decomposition, fan out to workers and synthesize results.
        fan_out_result = None
        _fanout_skip = None
        if settings.AGENT_ORCHESTRATOR_ENABLED and self.db is not None:
            _fanout_skip = _fanout_skip_reason(
                user_message, _intent_resolution, conversation_history,
                min_tokens=settings.FANOUT_PROBE_MIN_TOKENS,
            )
            if _fanout_skip:
                logger.info(
                    "[%s] fanout_skipped reason=%s", turn_id[:8], _fanout_skip,
                )
                _signal(ledger, "fanout_probe", False, reason=_fanout_skip)
        if (
            settings.AGENT_ORCHESTRATOR_ENABLED
            and self.db is not None
            and not _fanout_skip
        ):
            try:
                with stage("fanout"):
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
            _signal(ledger, "skill_router", False)
            _signal(ledger, "chat_handoff", False)
            _signal(ledger, "weather_force", False)
            _finalize_meter(ledger, meter, "answer")
            return response, ledger

        # ── Pulse v2 Phase 1: adaptive ReAct loop gate (before PR-20) ─────
        # The pulse loop is the default path for TOOL-BEARING chat turns: it
        # runs a single-step plan through ReActLoop so the _observe stage can
        # synthesize a grounded answer from a successfully executed tool. PR-20
        # (KG multi-step) takes precedence when enabled.
        #
        # It must NOT fire for general/concept/real_time reasoning turns or
        # when the intent resolver failed (zone unknown) — those belong to the
        # single-pass path, which owns zone-aware grounding, knowledge-gap
        # escalation, and confidence surfacing. Only a positive "platform"
        # zone (tool-bearing) routes here; otherwise we would waste an LLM
        # draft and corrupt the single-pass "first draft" semantics (which
        # reason-lane escalation and confidence surfacing depend on).
        pulse_loop_result = None
        _pulse_is_platform_zone = (
            _intent_resolution is not None
            and _intent_resolution.zone in ("platform", "off_limits")
        )
        if (
            settings.PULSE_LOOP_ENABLED
            and self.db is not None
            and self._draft_tools
            and not settings.KG_MULTI_STEP_ENABLED
            and _pulse_is_platform_zone
        ):
            try:
                with stage("pulse_loop"):
                    pulse_loop_result = await self._try_pulse_loop(
                        instance_id=instance_id, conversation_id=conversation_id,
                        user_message=user_message, host_user_id=host_user_id,
                        page_context=page_context, conversation_history=conversation_history,
                        instance_config=instance_config, user_info=user_info,
                        retrieval=retrieval, progress_callback=progress_callback,
                        stream_callback=stream_callback, turn_id=turn_id,
                        intent_resolution=_intent_resolution,
                    )
            except Exception:
                logger.exception("[%s] Pulse loop attempt failed; falling back to single-pass", turn_id[:8])

        if pulse_loop_result is not None:
            # ── ReAct path: skip S3→S5 single-pass, go straight to S6 ──────
            final_text = pulse_loop_result.final_response
            total_tokens = 0  # ReAct loop tracks its own token usage
            total_llm_calls = pulse_loop_result.replans_used + len(pulse_loop_result.step_results)

            for i, sr in enumerate(pulse_loop_result.step_results):
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
                len(pulse_loop_result.step_results), pulse_loop_result.replans_used, pulse_loop_result.succeeded,
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
                    "critic_verdict": "pass" if pulse_loop_result.succeeded else "veto",
                    "pulse_loop_path": True,
                },
                s6_latency, verdict="pass" if pulse_loop_result.succeeded else "veto",
            )
            await self.db.commit()

            # P4.1: Write trajectory (fire-and-forget, own session)
            _ = asyncio.ensure_future(_write_trajectory_own_session(turn_id))
            with stage("auto_memory"):
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
                for i, sr in enumerate(pulse_loop_result.step_results)
                if getattr(sr, "executed", True)
            ]
            if ledger.execution is not None:
                ledger.execution.completed_tools = _react_completed_tools
            else:
                from types import SimpleNamespace
                ledger.execution = SimpleNamespace(completed_tools=_react_completed_tools)

            try:
                from ai.engine.memory.working import update_focus_from_resolve_results

                update_focus_from_resolve_results(
                    _wm, conversation_id, _react_completed_tools
                )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "[%s] resolve_entity focus update skipped (pulse_loop)",
                    turn_id[:8],
                    exc_info=True,
                )

            ledger.final_response = final_text[:500]
            ledger.total_latency_ms = total_latency
            ledger.total_tokens = total_tokens
            ledger.total_llm_calls = total_llm_calls

            response = AgentResponse(
                text=final_text,
                sources_cited=[],
                tools_used=[],
                confidence=0.8 if pulse_loop_result.succeeded else 0.3,
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
            _signal(ledger, "skill_router", False)
            _signal(ledger, "chat_handoff", False)
            _signal(ledger, "weather_force", False)
            _finalize_meter(ledger, meter, "tool_answer")
            return response, ledger

        # ── PR-20: Multi-step planning gate (after S2, before S3) ──────────
        # If a multi-step plan is needed, run ReActLoop instead of single-pass S3→S5.
        # PV2-3B: mutating host plans return ChatHandoffOutcome (never ReAct).
        react_result = None
        if settings.KG_MULTI_STEP_ENABLED and self.db is not None:
            try:
                with stage("multi_step_plan"):
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
                        state_ctx=state_ctx,
                    )
            except Exception:
                logger.exception("Multi-step plan attempt failed; falling back to single-pass")

        from ai.engine.cognition.turn.handoff_agent import ChatHandoffOutcome

        if isinstance(react_result, ChatHandoffOutcome):
            return await self._return_chat_handoff(
                outcome=react_result,
                ledger=ledger,
                meter=meter,
                turn_id=turn_id,
                instance_id=instance_id,
                conversation_id=conversation_id,
                host_user_id=host_user_id,
                t0=t0,
            )

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
            with stage("auto_memory"):
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

            try:
                from ai.engine.memory.working import update_focus_from_resolve_results

                update_focus_from_resolve_results(
                    _wm, conversation_id, _react_completed_tools
                )
            except Exception:  # noqa: BLE001
                logger.debug(
                    "[%s] resolve_entity focus update skipped (react)",
                    turn_id[:8],
                    exc_info=True,
                )

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
            _signal(ledger, "skill_router", False)
            _signal(ledger, "chat_handoff", False)
            _signal(ledger, "weather_force", False)
            _finalize_meter(ledger, meter, "tool_answer")
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

        # ── Pulse v2 Phase 6: inject domain business context ──────────────
        # Only injected when the instance declares domain_context_enabled: true
        # (instance.yaml). Falls back to the legacy PULSE_DOMAIN_CONTEXT_ENABLED
        # setting for the default instance.
        _domain_ctx_enabled = (
            config.get("domain_context_enabled", None)
            if config.get("domain_context_enabled") is not None
            else settings.PULSE_DOMAIN_CONTEXT_ENABLED
        )
        if _domain_ctx_enabled:
            try:
                if self.domain_context_assembler is not None:
                    _domain_context = await self.domain_context_assembler().assemble(
                        app_identifier=config.get("app_identifier"),
                    )
                    if _domain_context:
                        system_prompt = f"{system_prompt}\n{_domain_context}"
            except Exception:
                logger.warning(
                    f"[{turn_id[:8]}] Domain context assembly failed", exc_info=True
                )

        # Tool-aware drafting: when an executor is wired, expose the curated
        # tool set to the LLM and append the anti-fabrication grounding rules.
        draft_tools = self._draft_tools if self.executor is not None else None
        # [GAP-M7] Salience guard: only surface list_my_capabilities when the
        # user is asking about identity/access, never as a confusion fallback.
        draft_tools = _filter_draft_tools(draft_tools, user_message, salience.domain)
        # Agent → Discuss: strip tools for prose refine (seed + follow-ups).
        # Apply turns (go/proceed/replan) keep tools so edit_plan can fire.
        _discuss_turn = _discuss_ctx
        _discuss_apply = (
            _history_has_discuss_markers(conversation_history)
            and _is_discuss_apply_turn(user_message)
        )
        if _discuss_turn:
            draft_tools = None
        # Zone-aware grounding: the anti-fabrication GROUNDING RULES are for
        # Zone 1 (platform-grounded) only. Zones concept/real_time/general get
        # a lighter directive (or the web_research mandate) instead.
        _is_platform_zone = (
            _intent_resolution is None             # resolver didn't run → safe default
            or _intent_resolution.zone in ("platform", "off_limits")
        )
        if _discuss_turn:
            system_prompt = (
                f"{system_prompt}\n\n"
                "AGENT DISCUSS MODE — follow exactly:\n"
                "- The user is refining or discussing an existing Agent plan in Chat.\n"
                "- Reply in prose only: improved brief and/or numbered steps.\n"
                "- Keep the step list multi-step when the brief has multiple "
                "actions (compute, validate, compare rates, report, do-not-commit). "
                "Never collapse to a single vague step.\n"
                "- Do NOT call any tools (no invoke_skill, call_host_api, "
                "resolve_entity, aggregate_entity, plan_task, edit_plan, "
                "approve_plan, web_research, export_document).\n"
                "- Do NOT re-run the prior analysis or fetch live data.\n"
                "- Do NOT navigate the user to an app (Payroll, People, …).\n"
                "- Do NOT mutate the Agent plan. Wait until the user says "
                "Fork, Replan, or explicitly asks to convert/run.\n"
            )
        elif _discuss_apply:
            import re as _re_plan
            _plan_id_match = None
            for _msg in (conversation_history or [])[-12:]:
                if not isinstance(_msg, dict):
                    continue
                _plan_id_match = _re_plan.search(
                    r"plan\s+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                    r"[0-9a-f]{4}-[0-9a-f]{12})",
                    (_msg.get("content") or ""),
                    _re_plan.I,
                )
                if _plan_id_match:
                    break
            if not _plan_id_match:
                _plan_id_match = _re_plan.search(
                    r"plan\s+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                    r"[0-9a-f]{4}-[0-9a-f]{12})",
                    user_message or "",
                    _re_plan.I,
                )
            _plan_id_hint = (
                _plan_id_match.group(1) if _plan_id_match else ""
            )
            system_prompt = (
                f"{system_prompt}\n\n"
                "AGENT DISCUSS APPLY — follow exactly:\n"
                "- The user confirmed a Chat refine of an EXISTING Agent plan.\n"
                "- Call edit_plan on that plan"
                + (f" (plan_id={_plan_id_hint})" if _plan_id_hint else "")
                + ".\n"
                "- If the ask is small and additive (add a chart, embed visuals, "
                "add one export step), pass step_deltas with action=add — do NOT "
                "rewrite the whole brief. Rewriting the brief forces a full replan "
                "and often regresses the graph into duplicate vague steps.\n"
                "- Only pass a full replacement brief when the user asked to "
                "rebuild the plan from scratch.\n"
                "- Do NOT call plan_task (that creates a NEW plan).\n"
                "- Do NOT navigate to Payroll or any app.\n"
                "- Do NOT collapse the brief into a single invoke_skill step — "
                "the brief's multiple actions must remain multiple steps.\n"
                "- After edit_plan succeeds, tell the user the plan was updated "
                "and still awaits approval in Tasks — nothing has run yet.\n"
            )
        elif draft_tools and _is_platform_zone:
            # PV2-3B / ADR-0046: Chat grounding must not say CALL THE TOOL for
            # host writes — IdentityBlock autonomy + this block hand off instead.
            from ai.engine.cognition.turn.handoff_agent import chat_grounding_rules_block

            system_prompt = f"{system_prompt}\n\n{chat_grounding_rules_block()}"

        # [GAP-3] Resolve anaphora: substitute pronouns with active entity
        from ai.engine.cognition.dialogue.anaphora import AnaphoraResolver
        _resolved_user_message = AnaphoraResolver(_wm).resolve(
            conversation_id, user_message
        )

        # [GAP-2] Inject active entity context into system prompt
        _wm_fragment = _wm.to_prompt_fragment(conversation_id)
        if _wm_fragment:
            system_prompt = f"{system_prompt}\n\n{_wm_fragment}"

        # [PV2-1A / PV2-2A] StateBlock lives in ContextPack.state (own budget),
        # not appended onto the draft task_body (which is TASK_BLOCK-clipped).
        # Kept here as a no-op marker so callers searching for StateBlock land
        # on the pack construction below.
        _state_for_pack = state_ctx.state if state_ctx is not None else None

        # [GAP-4] Inject session preference constraints into system prompt
        _pref_constraints = ""
        if host_user_id:
            try:
                from asgiref.sync import sync_to_async as _pref_s2a

                _pref_constraints = await _pref_s2a(
                    _pref_store.to_prompt_constraints, thread_sensitive=True
                )(host_user_id)
            except Exception as _e:  # noqa: BLE001 - preference read is best-effort
                logger.warning(
                    "[GAP-4] preference read failed user=%s: %s",
                    host_user_id, _e,
                )
        if _pref_constraints:
            system_prompt = f"{system_prompt}\n\n{_pref_constraints}"

        # [GAP-5/6] Load skill terminology + route query to matching skills
        _skill_terminology: dict[str, str] = {}
        _skill_router_fired = False
        if self.db is not None:
            try:
                from ai.engine.skills.registry import SkillRegistry
                from ai.engine.skills.router import SkillRouter
                _registry = SkillRegistry(self.db)
                _promoted_skills = await _registry.list_promoted(instance_id)
                _router = SkillRouter()
                _matched_skills = _router.find_matching_skills(user_message, _promoted_skills)
                _skill_terminology = _router.get_terminology(_matched_skills)
                _skill_router_fired = bool(_matched_skills)
            except Exception:
                logger.warning(
                    "Skill routing failed; continuing without terminology injection",
                    exc_info=True,
                )
        _signal(
            ledger, "skill_router", _skill_router_fired,
            matched=len(_skill_terminology),
        )
        if _skill_terminology:
            from ai.engine.knowledge.terminology import TerminologyResolver
            system_prompt = TerminologyResolver().inject(system_prompt, _skill_terminology)

        # [S1.5] Inject the intent resolver's matched endpoint into S3 so the
        # planner *confirms* the tool instead of lecturing from memory. This is
        # the mechanism that stops "tell me about the live data here" from
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

        with stage("draft"):
            from ai.engine.cognition.context_pack import build_context_pack

            _draft_lang = ""
            if state_ctx is not None:
                _draft_lang = str(getattr(state_ctx.state, "language", "") or "")
            draft_pack = build_context_pack(
                _state_for_pack,
                surface="chat",
                stage="draft",
                user_info=user_info,
                instance_config=config,
                conversation_history=conversation_history,
                retrieval=retrieval,
                language=_draft_lang,
                task_body=system_prompt,
                include_state=True,
                include_knowledge=False,
                include_memory=False,
                include_history=False,
            )
            draft = await draft_witness.draft(
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message=_resolved_user_message,
                system_prompt="",
                conversation_history=conversation_history,
                instance_config=instance_config,
                user_info=user_info,
                budget_tracker=budget,
                model=_draft_model,
                tools=draft_tools,
                temperature=temperature,
                pack=draft_pack,
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
        with stage("critic"):
            critic = await critic_witness.review(
                draft,
                retrieval,
                enable_llm_critic=True,
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message=_resolved_user_message,
                salience=salience,
                user_info=user_info,
                instance_config=instance_config,
                conversation_history=conversation_history,
                state=state_ctx.state if state_ctx is not None else None,
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
                with stage("escalate"):
                    draft = await draft_witness.draft(
                        instance_id=instance_id,
                        conversation_id=conversation_id,
                        user_message=_resolved_user_message,
                        system_prompt="",
                        conversation_history=conversation_history,
                        instance_config=instance_config,
                        user_info=user_info,
                        budget_tracker=budget,
                        model=escalation_model,
                        tools=draft_tools,
                        temperature=temperature,
                        pack=draft_pack,
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
        # ── FAIL-CLOSED GATE (P1-02): a critic veto MUST block execution ───
        # Previously the S4 veto was advisory only: the runner fell through to
        # S5 and dispatched the (unconfirmed) mutation anyway. Strip the tool
        # calls so S5 runs zero tools, and surface the veto reason as the
        # user-facing answer. The ledger write below still records the veto
        # verdict + flags.
        if critic.verdict == "veto":
            _veto_msg = (
                (critic.veto_reason or "").strip()
                or "This action was blocked pending review."
            )
            logger.warning(
                "[%s] S4 veto (%s) — blocking %d tool call(s): %s",
                turn_id[:8],
                ", ".join(critic.flags) or "unspecified",
                len(draft.tool_calls or []),
                _veto_msg[:160],
            )
            draft = _dc.replace(draft, tool_calls=[], text=_veto_msg)
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

        # [WEATHER-DETERMINISTIC] Guarantee live weather for weather queries.
        # Deep fix: the intent classifier's ``zone`` is an LLM guess that
        # frequently mislabels "weather in X" (especially with a greeting + a
        # trailing suitability question) as general/concept, which injects
        # "answer from knowledge, no tool call" and the draft replies "I can't
        # fetch weather data". The web_research plugin ships an authoritative
        # ``_is_weather_query`` detector — wire it into routing so a live
        # weather request ALWAYS reaches the weather tool, independent of the
        # draft LLM's tool choice. This is a routing-layer fix, not a regex
        # patch on the user's phrasing.
        # NOTE: skipped when S4 vetoed (P1-02) — re-forcing a tool call here
        # would defeat the fail-closed gate that stripped ``draft.tool_calls``.
        _weather_force_fired = False
        if (
            self.executor is not None
            and _is_wq(_resolved_user_message)
            and not _is_text_transform_request(_resolved_user_message)
            and critic.verdict != "veto"
        ):
            _has_weather_call = any(
                (tc.get("function") or {}).get("name") == "web_research"
                for tc in (draft.tool_calls or [])
            )
            if not _has_weather_call:
                _weather_force_fired = True
                import json as _json
                with stage("weather_normalize"):
                    _place = await _normalize_weather_question(
                        instance_id=instance_id,
                        conversation_id=conversation_id,
                        question=_resolved_user_message,
                        conversation_history=conversation_history,
                        model=model,
                        weather_extractor=self.weather_extractor,
                        user_info=user_info,
                        instance_config=instance_config,
                        state=state_ctx.state if state_ctx is not None else None,
                    )
                draft = _dc.replace(
                    draft,
                    tool_calls=[{
                        "id": f"call_weather_{turn_id[:8]}",
                        "function": {
                            "name": "web_research",
                            "arguments": _json.dumps({"query": f"weather in {_place}"}),
                        },
                    }],
                    text="",  # clear "I can't fetch weather" prose → synthesis writes the live answer
                    confidence=0.6,
                )
                # Force the synthesis path (empty text < 300 chars) and mark
                # the turn as tool-backed so the deterministic summary fallback
                # also applies if LLM synthesis is unavailable.
                final_text = ""
                _draft_text_was_empty = True
                ledger.intent_zone = "real_time"
                logger.info(
                    "[WEATHER-DETERMINISTIC] Forced web_research for %r -> %r",
                    _resolved_user_message, _place,
                )
        _signal(ledger, "weather_force", _weather_force_fired)

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
            # B5: resolve_entity / compensation stamping need the turn utterance
            # (tool query may be only a name like "Abrar").
            "user_message": _resolved_user_message,
            # ADR-0046: TurnPipelineRunner is the Chat advisory path — never
            # stage host mutations. Agent/plan runners set surface=agent|plan.
            "surface": "chat",
        }
        execute_witness = ExecuteWitness(
            executor=self.executor,
            hook_pipeline=hook_pipeline,
            hook_ctx_defaults=hook_ctx_defaults,
            run_id=turn_id,
            instance_id=instance_id,
            knowledge_store=self.knowledge_store,
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

        # [C7] Promote resolve_entity matches into working-memory focus with a
        # stable id (employee_no) + name aliases so "Back to Abrar" can restore.
        try:
            from ai.engine.memory.working import update_focus_from_resolve_results

            update_focus_from_resolve_results(
                _wm, conversation_id, execution.completed_tools
            )
        except Exception:  # noqa: BLE001 — focus update must never block the turn
            logger.debug(
                "[%s] resolve_entity focus update skipped",
                turn_id[:8],
                exc_info=True,
            )

        # [GAP-W8/W9] Tool-result grounding: when the planner executed tools, the
        # pre-tool draft is either empty or a short "I'll fetch …" promise — the
        # fetched data is otherwise discarded. Re-synthesize the final answer from
        # the ACTUAL tool results (GAP-W9, LLM → clean prose + real values), then
        # fall back to a deterministic summary (GAP-W8) only when synthesis is
        # unavailable. Order matters: the LLM synthesis produces the values the
        # user asked for; the deterministic summary is the "never blank" net.
        # B5: stamp CBAC deny onto empty payslip / profile soft-empties before
        # synthesis so the LLM cannot paraphrase absence for salary asks.
        try:
            from ai.engine.agent.tools import stamp_compensation_deny_on_soft_empty

            _caps = frozenset()
            if self.executor is not None and hasattr(self.executor, "user_capabilities"):
                try:
                    _caps = frozenset(self.executor.user_capabilities() or ())
                except Exception:  # noqa: BLE001
                    _caps = frozenset()
            execution.completed_tools = stamp_compensation_deny_on_soft_empty(
                execution.completed_tools,
                user_message=_resolved_user_message,
                caps=_caps,
            )
        except Exception:  # noqa: BLE001 — never block synthesis
            logger.debug("B5 compensation soft-empty stamp skipped", exc_info=True)

        with stage("synthesis"):
            _synth = await _synthesize_tool_results(
                instance_id=instance_id,
                conversation_id=conversation_id,
                user_message=_resolved_user_message,
                completed_tools=execution.completed_tools,
                draft_text=final_text,
                model=draft.model_used or model,
                delivery=_intent_resolution.delivery if _intent_resolution else "explain",
                envelope_synthesizer=self.envelope_synthesizer,
                stream_callback=stream_callback,
                progress_callback=progress_callback,
                user_info=user_info,
                instance_config=instance_config,
                state=state_ctx.state if state_ctx is not None else None,
            )
        if _synth and _synth.get("text"):
            final_text = _synth["text"]
            total_tokens += int(_synth.get("tokens") or 0)
            total_llm_calls += 1
            logger.info(
                "[%s] Tool-result synthesis — final answer written from %d tool result(s) (%d tokens)",
                turn_id[:8], len(execution.completed_tools), int(_synth.get("tokens") or 0),
            )
            # [WEATHER-FT] If this was a no_match clarification for a weather
            # query, store pending_weather so the next user turn (a bare
            # location confirmation) is re-routed into web_research._weather.
            if _synth.get("is_clarification"):
                _clarif_msg = _synth.get("clarification_user_message") or _resolved_user_message
                _is_wq2 = self._is_weather_query
                # Loop guard: if this turn was ALREADY a normalization retry and
                # still no-matched, clarify once but do NOT re-arm pending_weather
                # (otherwise a stubbornly-unresolvable place loops forever).
                if _is_wq2(_clarif_msg) and not _is_weather_rewrite_turn:
                    _wm.set_focus(conversation_id, _clarif_msg, "pending_weather")
                    logger.info(
                        "[WEATHER-FT] Stored pending_weather intent for conv %s: %r",
                        conversation_id[:8], _clarif_msg,
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

        # ── Pulse v2 Phase 7: post-result verification ───────────────────
        # When enabled and tools actually ran, verify that the synthesized
        # answer's factual claims are supported by the tool results.
        # Fail-closed: a verification error records passed=False + error in the
        # ledger so an outage is visible; the answer itself is left uncorrected
        # (no corrected_text) so the user still gets their response.
        if settings.PULSE_VERIFY_ENABLED and execution.completed_tools and final_text:
            try:
                from ai.engine.cognition.turn.verify import VerificationWitness
                from ai.engine.llm.router import model_for_profile
                _vw = VerificationWitness()
                with stage("verify"):
                    _vr = await _vw.verify(
                        answer=final_text,
                        tool_results=execution.completed_tools,
                        user_message=_resolved_user_message,
                        instance_id=instance_id,
                        conversation_id=conversation_id,
                        model=model_for_profile("verify") or draft.model_used or model,
                        user_info=user_info,
                        instance_config=instance_config,
                        state=state_ctx.state if state_ctx is not None else None,
                    )
                if not _vr.passed and _vr.corrected_text:
                    final_text = _vr.corrected_text
                    logger.info(
                        "[%s] Verification corrected answer: unsupported=%s",
                        turn_id[:8], _vr.unsupported_claims,
                    )
                total_tokens += _vr.tokens_used
                total_llm_calls += 1
                ledger.verification_passed = _vr.passed
                ledger.verification_unsupported = _vr.unsupported_claims
                ledger.verification_error = _vr.error
            except Exception as e:
                logger.warning(
                    "[%s] Verification step failed", turn_id[:8], exc_info=True
                )
                ledger.verification_passed = False
                ledger.verification_error = str(e)

        # S-TRACE-01: concept/general turns ground their answer through S2
        # retrieval (RetrievalWitness), not a ReAct tool call — so no tool
        # lands in ``completed_tools`` and the "why this answer" trace came
        # back empty even for fully grounded answers. Surface that retrieval
        # as a synthetic ``search_knowledge`` tool step (the literal thing that
        # grounded the answer) so the trace is non-empty for grounded
        # single-pass turns. Only fires when NO real tool ran AND retrieval
        # actually found chunks — never fabricates a trace for empty retrieval.
        if not execution.completed_tools and retrieval.knowledge_chunks:
            execution.completed_tools.append({
                "tool_name": "search_knowledge",
                "tool_args": {"query": user_message},
                "result": {"count": len(retrieval.knowledge_chunks)},
                "error": None,
                "latency_ms": s2_latency,
            })

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
                "verification_passed": ledger.verification_passed,
                "verification_unsupported": ledger.verification_unsupported,
                "verification_error": ledger.verification_error,
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
            envelope=_synth.get("envelope") if _synth else None,
        )
        with stage("auto_memory"):
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

        _chat_handoff_fired = False
        for _tool in execution.completed_tools or []:
            _raw = _tool.get("result") if isinstance(_tool, dict) else None
            _parsed = _raw
            if isinstance(_raw, str):
                try:
                    import json as _json_handoff
                    _parsed = _json_handoff.loads(_raw)
                except (TypeError, ValueError):
                    _parsed = None
            if isinstance(_parsed, dict) and _parsed.get("action") == "chat_handoff":
                _chat_handoff_fired = True
                break
        _signal(ledger, "chat_handoff", _chat_handoff_fired)
        if _chat_handoff_fired:
            _turn_decision = "handoff_agent"
        elif execution.completed_tools:
            _turn_decision = "tool_answer"
        else:
            _turn_decision = "answer"
        _finalize_meter(ledger, meter, _turn_decision)
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
            plan = Plan(
                pattern="single_step",
                steps=[PlanStep(
                    step_id=0,
                    intent=user_message,
                    tool_name=None,
                    tool_args={},
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

    async def _try_chat_write_handoff(
        self,
        *,
        user_message: str,
        conversation_history: list[dict] | None,
        state_ctx,
        instance_config: dict | None,
    ):
        """PV2-3B: ESS write with enough slots → ChatHandoffOutcome; else seed state.

        Returns None when Chat should keep clarifying (incomplete slots) or the
        utterance is not an ESS write. Never stages host mutations.
        """
        from ai.engine.cognition.turn.handoff_agent import (
            build_chat_write_handoff,
            combine_user_brief,
            enough_slots_for_chat_handoff,
            is_ess_write_utterance,
            merge_slots,
            resolve_ess_write_from_brief,
            seed_slots_into_state,
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
        # Already handed off — do not re-fire on meta follow-ups
        # ("is the handoff complete?", "thank you").
        if prior_enough and not current_is_write:
            return None
        active_write = prior_api.startswith("submit_my_")
        # Fresh write ask, or slot continuation while a write is open.
        if not current_is_write and not active_write:
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
                "seed state, fall through (no ReAct mutation)",
                api_name,
            )
            return None
        logger.info(
            "TurnPipelineRunner: Chat handoff_agent api=%s slots=%s",
            api_name, sorted(slots.keys()),
        )
        return build_chat_write_handoff(
            api_name=api_name,
            slots=slots,
            user_message=user_message,
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
    ):
        """Finalize a ChatHandoffOutcome as handoff_agent (0 host staging)."""
        from types import SimpleNamespace

        from ai.engine.agent.reasoning import AgentResponse
        from ai.engine.cognition.notifier import broadcast_run_event as _broadcast_run

        final_text = outcome.text
        total_latency = (time.monotonic() - t0) * 1000
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
                        "handoff_agent": True,
                        "api_name": outcome.api_name,
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
            envelope=outcome.envelope,
        )
        await _broadcast_run(instance_id, "run.completed", {
            "run_id": turn_id,
            "total_latency_ms": total_latency,
            "total_tokens": 0,
            "total_llm_calls": 0,
            "handoff_agent": True,
        })
        _signal(ledger, "skill_router", False)
        _signal(ledger, "chat_handoff", True, api=outcome.api_name)
        _signal(ledger, "weather_force", False)
        ledger.turn_decision = "handoff_agent"
        _finalize_meter(ledger, meter, "handoff_agent")
        return response, ledger

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
        state_ctx=None,
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
        from ai.engine.cognition.plan.planner import (
            _is_agent_discuss_context,
            _wants_explicit_task_creation,
        )
        if _is_agent_discuss_context(user_message, conversation_history):
            logger.info("TurnPipelineRunner: Agent discuss turn — skip ReAct")
            return None
        # "I need a task…" → Chat PLAN FIRST + plan_task, not silent ReAct.
        if _wants_explicit_task_creation(user_message):
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
            None,
            surface="chat",
            stage="fanout",
            user_info=user_info,
            instance_config=config,
            conversation_history=conversation_history,
            retrieval=retrieval,
            task_body=f"{task_body}\n\n{TASK_FANOUT}",
            include_state=False,
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
                None,
                surface="chat",
                stage="fanout_synthesis",
                user_info=user_info,
                instance_config=instance_config,
                task_body=(
                    f"{system_prompt}\n\n{TASK_FANOUT_SYNTHESIS}\n\n"
                    f"User request: {user_message}"
                ),
                user_body=_json.dumps(fan_out_result.artifact_refs, indent=2),
                include_state=False,
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
