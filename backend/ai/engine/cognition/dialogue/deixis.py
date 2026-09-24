"""Deterministic deixis / anaphora gate for Chat (Track C — ux-07).

Before tools run, if the user points with \"that one\" / \"this one\" / etc.,
ask a short confirmation (or name the inferred prior topic) instead of
guessing into search_knowledge and dumping empty-tool prose as the Answer.

Track D — topic stack: when several recent assistant topics exist, list
them so the user can pick instead of silently taking only the latest.
"""
from __future__ import annotations

import re
from typing import Any

_DEIXIS = re.compile(
    r"("
    r"\b(that|this)\s+one\b"
    r"|\bthose(\s+ones?)?\b"
    r"|\bthe\s+last\s+(one|thing)\b"
    r"|\bcheck\s+that\b"
    r"|\blook\s+(at|into)\s+that\b"
    r"|\bthat\s+thing\b"
    r")",
    re.IGNORECASE,
)

from ai.engine.cognition.dialogue.affirmation import starts_with_affirmation

_HEADING = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
_BOLD = re.compile(r"\*\*([^*]{2,80})\*\*")

_TOPIC_STACK_MAX = 4

_KNOWN_TOOL_IDENTIFIERS = frozenset({
    "call_host_api",
    "resolve_entity",
    "search_knowledge",
    "export_document",
    "code_execute",
    "web_research",
    "get_my_leave_balance",
    "list_leave_entitlements",
    "list_my_leave",
    "list_my_loans",
    "list_my_payslips",
    "list_attendance",
    "list_my_attendance_permissions",
})

_API_TOPIC_PHRASES: dict[str, str] = {
    "get_my_leave_balance": "leave balance",
    "list_leave_entitlements": "leave balance",
    "list_my_leave": "leave requests",
    "list_my_loans": "loans",
    "list_my_payslips": "payslips",
    "list_attendance": "attendance",
    "list_my_attendance_permissions": "attendance permissions",
    "get_my_profile": "profile",
}


def has_deixis(message: str) -> bool:
    return bool(_DEIXIS.search((message or "").strip()))


def is_confirm_reply(message: str) -> bool:
    """True when the user is agreeing with the previous turn.

    Delegates to the canonical affirmation module so every surface (deixis,
    pending memory cards, consent resume) reads the same Arabic spellings.
    """
    return starts_with_affirmation(message)


def _api_to_domain_phrase(name: str) -> str:
    """Map a host API name to an operator-facing domain phrase."""
    api = str(name or "").strip()
    if not api:
        return ""
    if api in _API_TOPIC_PHRASES:
        return _API_TOPIC_PHRASES[api]
    for prefix in ("list_", "get_", "search_", "query_", "fetch_"):
        if api.startswith(prefix):
            api = api[len(prefix):]
            break
    return api.replace("_", " ").strip()


def _looks_like_tool_identifier(text: str) -> bool:
    topic = (text or "").strip()
    if not topic:
        return True
    if "_" in topic:
        return True
    folded = topic.casefold()
    return folded in {name.casefold() for name in _KNOWN_TOOL_IDENTIFIERS}


def _topics_from_last_results(
    last_results: list[dict[str, Any]] | None,
    *,
    limit: int = _TOPIC_STACK_MAX,
) -> list[str]:
    if not last_results:
        return []
    seen: set[str] = set()
    stack: list[str] = []
    for row in reversed(last_results):
        if not isinstance(row, dict):
            continue
        api = str(row.get("api") or "").strip()
        topic = _api_to_domain_phrase(api)
        if not topic:
            continue
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        stack.append(topic)
        if len(stack) >= limit:
            break
    return stack


_SKIP_LINE_PREFIXES = (
    "here's what i found",
    "i retrieved your records",
    "retrieved ",
)


def _topic_from_content(content: str) -> str | None:
    if not isinstance(content, str) or not content.strip():
        return None
    m = _HEADING.search(content)
    if m:
        return m.group(1).strip()[:80]
    for m in _BOLD.finditer(content):
        bold = m.group(1).strip()[:80]
        if not _looks_like_tool_identifier(bold):
            return bold
    for line in content.splitlines():
        cleaned = line.strip().lstrip("#*- ").strip()
        if cleaned.startswith("**") and cleaned.endswith("**"):
            inner = cleaned.strip("*").strip()
            if _looks_like_tool_identifier(inner):
                continue
        if 3 <= len(cleaned) <= 120 and not cleaned.endswith("?"):
            lowered = cleaned.casefold()
            if any(lowered.startswith(prefix) for prefix in _SKIP_LINE_PREFIXES):
                continue
            if _looks_like_tool_identifier(cleaned) or " retrieved " in f" {lowered} ":
                continue
            return cleaned[:80]
    return None


def collect_topic_stack(
    conversation_history: list[dict[str, Any]] | None,
    *,
    limit: int = _TOPIC_STACK_MAX,
    last_results: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Recent distinct assistant topics (newest first), capped at ``limit``."""
    from_state = _topics_from_last_results(last_results, limit=limit)
    if from_state:
        return from_state

    if not conversation_history:
        return []
    seen: set[str] = set()
    stack: list[str] = []
    for turn in reversed(conversation_history):
        if (turn.get("role") or "") != "assistant":
            continue
        content = turn.get("content") or turn.get("text") or ""
        topic = _topic_from_content(content)
        if not topic:
            continue
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        stack.append(topic)
        if len(stack) >= limit:
            break
    return stack


def resolve_deixis_subject(
    message: str,
    *,
    last_results: list[dict[str, Any]] | None,
) -> str | None:
    """I6: when the user points ("those", "that one") and durable state holds
    exactly one subject, return the message normalized with that subject so
    the bound self-read path can act. Return None when there is nothing to
    point at, or when several subjects exist (then a question is legitimate).

    Normalization only (ADR-0049): the subject comes from ``last_results``,
    never from prose, and no turn exits here.
    """
    text = (message or "").strip()
    if not text or not has_deixis(text) or is_confirm_reply(text):
        return None
    topics = _topics_from_last_results(last_results, limit=2)
    if len(topics) != 1:
        return None
    subject = topics[0]
    if subject.casefold() in text.casefold():
        return None
    return f"{text.rstrip('?!؟ ')} — {subject}"


def infer_prior_topic(
    conversation_history: list[dict[str, Any]] | None,
    *,
    last_results: list[dict[str, Any]] | None = None,
) -> str | None:
    """Best-effort topic from durable state or the last assistant turn."""
    stack = collect_topic_stack(
        conversation_history,
        limit=1,
        last_results=last_results,
    )
    return stack[0] if stack else None


def build_deixis_confirm(
    *,
    focus_label: str | None = None,
    prior_topic: str | None = None,
    topic_stack: list[str] | None = None,
) -> str:
    """Operator-facing confirm question (RULE_23 — no tool/engine jargon)."""
    topics = [t.strip() for t in (topic_stack or []) if (t or "").strip()]
    if len(topics) >= 2:
        bullets = "\n".join(f"- **{t}**" for t in topics[:_TOPIC_STACK_MAX])
        return (
            "Which of these did you mean?\n"
            f"{bullets}\n"
            "Reply with the name, or **yes** for the first one."
        )
    topic = (focus_label or prior_topic or (topics[0] if topics else "")).strip()
    if topic:
        return (
            f"Did you mean **{topic}**? "
            "Reply **yes** to continue with that, or name the item you meant."
        )
    return (
        "Which item do you mean? "
        "Please name it specifically (I don't want to guess)."
    )


def should_gate_deixis(
    message: str,
    *,
    conversation_history: list[dict[str, Any]] | None = None,
    last_results: list[dict[str, Any]] | None = None,
) -> str | None:
    """Return a clarification question, or None if the turn may proceed.

    Skips when the user is confirming a prior clarify, or when there is no
    deixis marker in the message.
    """
    text = (message or "").strip()
    if not text or not has_deixis(text):
        return None
    if is_confirm_reply(text):
        return None
    stack = collect_topic_stack(
        conversation_history,
        last_results=last_results,
    )
    return build_deixis_confirm(
        prior_topic=stack[0] if stack else None,
        topic_stack=stack,
    )
