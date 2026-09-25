"""Shared turn-runner utilities extracted for L7 runner_lines meter."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V


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


_CAPABILITY_PHRASES = T("turn/runner_util.py::_CAPABILITY_PHRASES")

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
_TEXT_TRANSFORM_PHRASES = T("turn/runner_util.py::_TEXT_TRANSFORM_PHRASES")
_TEXT_TRANSFORM_WORDS = T("turn/runner_util.py::_TEXT_TRANSFORM_WORDS")

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
                V("t_leave"), V("t_loan_2"), V("t_attendance"), V("t_vacation"), V("t_payslip_2"), V("t_salary"),
                "absence", V("t_overtime"),
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
    from ai.engine.cognition.turn.process_brief import process_ids

    for msg in (conversation_history or [])[-6:]:
        content = str((msg or {}).get("content") or "")
        if any(pid in content for pid in process_ids()):
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
_DEFAULT_REFUSAL_EN = T("turn/runner_util.py::_DEFAULT_REFUSAL_EN")
_DEFAULT_REFUSAL_AR = T("turn/runner_util.py::_DEFAULT_REFUSAL_AR")
# Wording that keeps a refusal even when the ask names an in-scope topic.
_SCOPE_BYPASS_WORDS = T("turn/runner_util.py::_SCOPE_BYPASS_WORDS")
_SCOPE_BYPASS_PHRASES = T("turn/runner_util.py::_SCOPE_BYPASS_PHRASES")

def _is_declared_in_scope(user_message: str, instance_config: dict | None) -> bool:
    V("t_true_when_the_ask_names_a")
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
        # bubble instead. The plan itself is created deterministically from
        # the brief, so the draft never calls plan_task either.
        _plan_block = frozenset({
            "call_host_api",
            "resolve_entity",
            "aggregate_entity",
            "export_document",
            "invoke_skill",
            "search_knowledge",
            "web_research",
            "plan_task",
            "get_entity_details",
        })
        tools = [
            d for d in tools
            if d.get("function", {}).get("name") not in _plan_block
        ]
    return tools


def plan_created_receipt(completed_tools: list[dict] | None) -> str | None:
    """Trusted plan_task receipt; avoids LLM synthesis and verification."""
    import json

    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("tool_name") != "plan_task":
            continue
        if item.get("error"):
            return None
        data = item.get("result")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (TypeError, ValueError):
                data = None
        if not isinstance(data, dict) or data.get("action") != "plan_created":
            continue
        message = str(data.get("message") or "").strip()
        if message:
            return message
        count = len(data.get("steps") or [])
        return (
            f"Task created with {count} steps. Nothing has run yet. "
            "Review and approve it in Tasks."
        )
    return None


def plan_task_error_receipt(completed_tools: list[dict] | None) -> str | None:
    """Return a plan_task failure verbatim; never let synthesis reinterpret it."""
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("tool_name") != "plan_task":
            continue
        error = str(item.get("error") or "").strip()
        if error:
            return error
    return None


def last_user_brief(conversation_history: list | None) -> str | None:
    """The most recent substantive user brief in the thread."""
    for msg in reversed(conversation_history or []):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or msg.get("type") or ""
        if role not in ("user", "human"):
            continue
        content = (msg.get("content") or "").strip()
        if len(content) >= 40:
            return content[:4000]
    return None


def plan_followup_context(
    user_message: str,
    conversation_history: list | None,
) -> str | None:
    """Brief a short Plan reply refers to (``both``, ``1,2,3``, ``the first``).

    Without it the draft treats the reply as a brand-new subject and asks the
    user what they mean, losing the task they already described.
    """
    raw = (user_message or "").strip()
    if not raw or len(raw) > 40:
        return None
    return last_user_brief(conversation_history)

#: Spine static tools ALWAYS exposed to the chat planner. Registry plugins
#: contribute the rest via ``chat_tool_names()`` (G-C: freeze the spine, grow
#: the periphery — new chat tools need zero edits to this module).
#: When ``ECF_ENABLED``, ``resolve_entity`` / ``aggregate_entity`` join the
#: allow-set dynamically (see ``_chat_tool_allowlist``) — otherwise name
#: lookups fall through to ``search_knowledge`` and false-miss live People rows.
_CHAT_STATIC_TOOLS = T("turn/runner_util.py::_CHAT_STATIC_TOOLS")

_ECF_CHAT_TOOLS = T("turn/runner_util.py::_ECF_CHAT_TOOLS")

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

