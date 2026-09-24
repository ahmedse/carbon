"""Shared turn-runner utilities extracted for L7 runner_lines meter."""
from __future__ import annotations

import logging
import re

from ai.engine.cognition.turn.runner_util_i18n import (
    ESS_TOPIC_AR,
    FIRST_PERSON_AR,
    SCOPE_BYPASS_AR,
    any_needle,
)
from ai.engine.text.word_match import contains_any_phrase, has_any_word

logger = logging.getLogger("pulse.cognition.turn.runner_util")


_CAPABILITY_PHRASES = (
    "what can you do",
    "what do you have access to",
    "what features",
    "show me capabilities",
    "your capabilities",
    "what are you able to do",
    "what can i use",
)

def _is_capability_query(text: str) -> bool:
    """True if the user explicitly asks about capabilities/access."""
    if not text:
        return False
    return contains_any_phrase(text, _CAPABILITY_PHRASES)

# ── G5 text-transformation meta-task guard ────────────────────────────────
# A turn whose ACTUAL ask is to transform quoted text (correct spelling/grammar,
# proofread, rephrase, rewrite, translate, fix typos) must NEVER be re-routed
# into live weather fetching just because the quoted sentence happens to name
# "weather"/"forecast". Regex-only and engine-local (the engine cannot import
# ``ai.plugins.web_research`` — RULE_20), so it lives here beside the routing.
_TEXT_TRANSFORM_PHRASES = (
    "correct the spelling", "correct spelling",
    "fix the spelling", "fix spelling",
    "check the spelling", "check spelling",
    "spell check", "spell-check",
    "correct the grammar", "correct grammar",
    "fix the grammar", "fix grammar",
    "check the grammar", "check grammar",
    "proofread", "rephrase", "rewrite",
    "fix the typos", "fix typos", "fix the typo", "fix typo",
)
_TEXT_TRANSFORM_WORDS = ("typo", "translate")

def _is_text_transform_request(text: str) -> bool:
    """True when the user's ask is to transform quoted text, not to act on it."""
    if not text:
        return False
    return (
        has_any_word(text, _TEXT_TRANSFORM_WORDS)
        or contains_any_phrase(text, _TEXT_TRANSFORM_PHRASES)
    )

# ── F-LIVE-5: fan-out probe gate ──────────────────────────────────────────
# The orchestrator decision is a full LLM call that almost always declines.
# Only long, analytical, non-self-service turns are worth probing.
def _ess_topic(text: str) -> bool:
    return bool(
        has_any_word(
            text,
            (
                "leave", "loan", "attendance", "vacation", "payslip", "salary",
                "absence", "overtime",
            ),
        )
        or "time off" in (text or "").casefold()
        or "time-off" in (text or "").casefold()
        or any_needle(text, ESS_TOPIC_AR)
    )


def _first_person(text: str) -> bool:
    return bool(
        has_any_word(text, ("i", "i'm", "i've", "i'd", "my", "me", "mine"))
        or any_needle(text, FIRST_PERSON_AR)
    )
def _is_my_endpoint(name: str) -> bool:
    token = str(name or "")
    return token == "my" or token.startswith("my_") or token.endswith("_my") or "_my_" in token

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
        if candidates and _is_my_endpoint(str(candidates[0].name)):
            return "ess"
    try:
        from ai.engine.agent.chat_surface import is_ess_write_intent

        if is_ess_write_intent(text):
            return "ess"
    except Exception:  # noqa: BLE001 — classification only
        pass
    if _ess_topic(text) and _first_person(text):
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
_SCOPE_BYPASS_WORDS = (
    "ignore", "disregard", "bypass", "override", "jailbreak", "pretend",
    "password", "passwords", "credential", "credentials", "access",
)
_SCOPE_BYPASS_PHRASES = (
    "system prompt", "developer mode", "you are now", "api key", "api keys",
    "secret key", "secret keys", "access control", "access controls",
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
    if (
        has_any_word(raw, _SCOPE_BYPASS_WORDS)
        or contains_any_phrase(raw, _SCOPE_BYPASS_PHRASES)
        or any_needle(raw, SCOPE_BYPASS_AR)
    ):
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
    process_mode: str = "ask",
    conversation_history: list | None = None,
) -> list[dict] | None:
    """Exclude ``list_my_capabilities`` unless the user explicitly asked about
    capabilities/access or the turn is an identity-domain turn (GAP-M7).

    Ask mode also strips ``plan_task`` / plan mutators — answers only; user
    switches the Plan dial when a reviewable plan is required.
    """
    tools = draft_tools
    if (
        tools
        and not _is_capability_query(user_message)
        and salience_domain != "identity"
    ):
        tools = [
            d for d in tools
            if d.get("function", {}).get("name") != "list_my_capabilities"
        ]
    # Process mode is structured transport metadata. Prefix support remains
    # only for replaying pre-migration transcripts, inside ``Surface.resolve``.
    from ai.engine.agent.surface import Surface

    # Only Ask withholds the planning tools. Plan drafts them, and Agent runs
    # them — an "anything that is not plan is ask" test wrongly caught Agent.
    resolved = Surface.resolve(
        process_mode=process_mode, user_message=user_message or "",
    )
    if tools and resolved is Surface.CHAT_ASK:
        _ask_block = frozenset({"plan_task", "approve_plan", "edit_plan"})
        tools = [
            d for d in tools
            if d.get("function", {}).get("name") not in _ask_block
        ]
    elif tools and resolved is Surface.CHAT_PLAN:
        # Plan drafts a task. Live host reads would answer the brief in the
        # bubble and skip acceptance. plan_task creates the task, so it stays
        # unavailable until the user accepts a plan already shown.
        _plan_block = frozenset({
            "call_host_api",
            "resolve_entity",
            "aggregate_entity",
            "export_document",
            "invoke_skill",
        })
        if not _user_accepted_shown_plan(user_message, conversation_history):
            _plan_block = _plan_block | {"plan_task"}
        tools = [
            d for d in tools
            if d.get("function", {}).get("name") not in _plan_block
        ]
    return tools


_PLAN_ACCEPT = frozenset({
    "yes", "ok", "okay", "accept", "accepted", "approve", "approved",
    "go", "proceed", "confirm", "do it", "create it", "create the task",
})


def _user_accepted_shown_plan(
    user_message: str,
    conversation_history: list | None,
) -> bool:
    """True when a numbered plan is already in the thread and this turn accepts it."""
    import re

    text = (user_message or "").strip().lower().rstrip(".!")
    if text not in _PLAN_ACCEPT and not text.startswith("accept"):
        return False
    for msg in reversed(conversation_history or []):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or msg.get("type") or ""
        if role not in ("assistant", "ai"):
            continue
        content = msg.get("content") or ""
        if re.search(r"(?m)^\s*\d+[\.\)]\s+\S", content):
            return True
        return False
    return False

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

def _completed_tools_from_react(step_results) -> list[dict]:
    """Flatten ReAct ``StepResult.tool_output`` into host completed_tools.

    StepResult stores ``{tool_name, tool_args, result}``. Stuffing that dict
    into ``item['result']`` hid ``api_name`` and the host payload from
    ``build_tool_digest``, so the next turn re-fetched instead of recalling.
    """
    out: list[dict] = []
    for i, sr in enumerate(step_results or []):
        if not getattr(sr, "executed", True):
            continue
        raw = getattr(sr, "tool_output", None)
        if raw is None:
            raw = getattr(sr, "tool_result", None)
        payload = raw if isinstance(raw, dict) else {}
        nested = payload.get("result") if "result" in payload else payload
        out.append({
            "tool_name": (
                payload.get("tool_name")
                or getattr(sr, "tool_name", None)
                or f"react_step_{i}"
            ),
            "tool_args": (
                payload.get("tool_args")
                if isinstance(payload.get("tool_args"), dict)
                else {}
            ),
            "result": nested,
            "error": getattr(sr, "error", None),
            "latency_ms": getattr(sr, "latency_ms", 0.0) or 0.0,
            "guardrail_flags": list(getattr(sr, "critic_flags", None) or []),
        })
    return out

