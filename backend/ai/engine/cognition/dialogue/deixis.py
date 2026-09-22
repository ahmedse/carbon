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


def has_deixis(message: str) -> bool:
    return bool(_DEIXIS.search((message or "").strip()))


def is_confirm_reply(message: str) -> bool:
    """True when the user is agreeing with the previous turn.

    Delegates to the canonical affirmation module so every surface (deixis,
    pending memory cards, consent resume) reads the same Arabic spellings.
    """
    return starts_with_affirmation(message)


def _topic_from_content(content: str) -> str | None:
    if not isinstance(content, str) or not content.strip():
        return None
    m = _HEADING.search(content)
    if m:
        return m.group(1).strip()[:80]
    m = _BOLD.search(content)
    if m:
        return m.group(1).strip()[:80]
    for line in content.splitlines():
        cleaned = line.strip().lstrip("#*- ").strip()
        if 3 <= len(cleaned) <= 60 and not cleaned.endswith("?"):
            return cleaned[:80]
    return None


def collect_topic_stack(
    conversation_history: list[dict[str, Any]] | None,
    *,
    limit: int = _TOPIC_STACK_MAX,
) -> list[str]:
    """Recent distinct assistant topics (newest first), capped at ``limit``."""
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


def infer_prior_topic(conversation_history: list[dict[str, Any]] | None) -> str | None:
    """Best-effort topic from the last assistant turn (heading or bold)."""
    stack = collect_topic_stack(conversation_history, limit=1)
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
    stack = collect_topic_stack(conversation_history)
    return build_deixis_confirm(
        prior_topic=stack[0] if stack else None,
        topic_stack=stack,
    )
