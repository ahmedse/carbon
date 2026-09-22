"""Detect a write request answered with "go do it yourself, somewhere else".

On **Agent/plan** surfaces, writes are confirmation-gated by calling the
tool (stages → confirm card). Models sometimes refuse and point elsewhere;
``_should_force_action`` detects that dead end.

On **Chat** (ADR-0046 / G2), the product answer is an Agent/My handoff — not
a forced ``submit_my_*`` tool call. ``engine_runtime`` uses the same
detection to synthesize handoff CTAs instead of re-prompting CALL THE TOOL.
"""
from __future__ import annotations

import re

#: "I can't do this" / "you must do it yourself, over there".
_DENIAL_OR_HANDOFF = re.compile(
    r"\bi\s+(?:can'?t|cannot|am\s+unable\s+to|'?m\s+not\s+able\s+to)\b"
    r"|\b(?:unable|not\s+able)\s+to\s+(?:submit|create|request|file|record)\b"
    r"|\b(?:through|via|in)\s+the\s+(?:appropriate|proper|relevant)\s+channel\b"
    r"|\b(?:directly\s+)?in\s+the\s+system\s+(?:yourself|first)\b"
    r"|\byou\s+(?:will\s+)?(?:need|have)\s+to\s+(?:submit|do|complete)\b"
    # "the system requires a confirmation from you" — a handoff dressed up as
    # a fact about the platform.
    r"|\brequires?\s+(?:an?\s+|additional\s+|further\s+|extra\s+)*confirmation\b"
    r"|لا\s+(?:يمكنني|أستطيع|استطيع|يمكن)"
    r"|(?:يتطلب|تتطلب)\s+تأكيد"
    r"|(?:بنفسك|النظام\s+الأساسي|القناة\s+المناسبة)",
    re.IGNORECASE,
)

#: "…first, then try again" / "complete the confirmation steps".
_RETRY_OR_ELSEWHERE = re.compile(
    r"\btry\s+again\b"
    r"|\bcomplete\s+the\s+confirmation\b"
    r"|\bconfirmation\s+(?:process|steps?)\b"
    r"|\bthen\s+(?:come\s+back|retry|resubmit)\b"
    r"|أعد\s+المحاولة|حاول\s+مرة\s+أخرى|المحاولة\s+مرة\s+أخرى"
    r"|(?:إكمال|اكمال|أكمل|اكمل)\s+(?:خطوات|عملية|عمليه|إجراءات)?\s*(?:التأكيد|التاكيد)"
    r"|(?:خطوات|عملية)\s+(?:التأكيد|التاكيد)"
    r"|أولا?ً?\s*،?\s*ثم",
    re.IGNORECASE,
)


def is_action_deflection(text: str) -> bool:
    """True when the answer refuses a write and points the user elsewhere."""
    body = (text or "").strip()
    if not body:
        return False
    return bool(_DENIAL_OR_HANDOFF.search(body) and _RETRY_OR_ELSEWHERE.search(body))


def build_forced_action_message(user_message: str, deflected_reply: str = "") -> str:
    """Re-issue the user's request with the propose→confirm contract spelled out."""
    lines = [
        "Carry out this request now by CALLING the matching platform action "
        "tool. The tool call does not execute anything: it stages the action "
        "and shows the user a confirm/decline card, which is exactly how a "
        "write is meant to be proposed here.",
        "",
        "You must not reply that you cannot do it, that the user should do it "
        "in the system themselves, that they should complete confirmation "
        "steps first and retry, or that they should use another channel — "
        "there is no other channel. If one detail is genuinely missing, ask "
        "ONE short question for that detail and nothing else.",
        "",
        "The user's request:",
        (user_message or "").strip(),
    ]
    return "\n".join(lines)
