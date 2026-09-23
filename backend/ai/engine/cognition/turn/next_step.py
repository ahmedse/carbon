"""L4 — next ESS action from ConversationState (0 LLM).

Status labels stay in ``plan_status``. This module names the verb the
user must take next (switch to Agent / Approve / Run / Confirm). Chat
never submits (ADR-0046).
"""
from __future__ import annotations

import re
from typing import Any

_TERMINAL = frozenset({
    "completed", "completed_with_gaps", "failed", "cancelled",
})

_NEXT_ASK = re.compile(
    r"("
    r"\bwhat(?:'s| is)?\s+next\b"
    r"|\bthen\s+what\b"
    r"|\bwhat\s+(?:should|do)\s+i\s+do\b"
    r"|\bwhat(?:'s| is) the next step\b"
    r"|ماذا\s+بعد"
    r"|وش\s+(?:الخطوة|بعدين)"
    r"|ما\s+الخطوة"
    r"|بعدين\s*\??"
    r")",
    re.IGNORECASE,
)

_CONTINUER = re.compile(
    r"^\s*(?:ok|okay|and|then|next|go\s+on|بعدها|بعدين)\s*[.?؟]?\s*$",
    re.IGNORECASE,
)

_PAYROLL_RE = re.compile(
    r"\b(?:payslip|payroll|gosi|net pay|take-home|deduction)\b|قسيمة|راتب|استقطاع",
    re.IGNORECASE,
)

_OFFER = {
    "submit_in_agent": {
        "en": "Next: switch to Agent to submit. Chat will not send it.",
        "ar": "التالي: بدّل إلى الوكيل لإرسال الطلب. الدردشة لا تُرسل.",
    },
    "approve_in_agent": {
        "en": "Next: open Agent and Approve, then Run.",
        "ar": "التالي: افتح الوكيل واضغط اعتماد ثم تشغيل.",
    },
    "run_in_agent": {
        "en": "Next: open Agent and Run.",
        "ar": "التالي: افتح الوكيل وشغّل الخطة.",
    },
    "confirm_in_agent": {
        "en": "Next: open Agent and confirm the waiting step.",
        "ar": "التالي: افتح الوكيل وأكّد الخطوة المنتظرة.",
    },
}


def _lang(text: str, state: Any = None) -> str:
    if re.search(r"[\u0600-\u06FF]", text or ""):
        return "ar"
    lang = str(getattr(state, "language", "") or "")
    return "ar" if lang.startswith("ar") else "en"


def open_active_plan(state: Any) -> dict | None:
    """First non-terminal active plan, else None."""
    if state is None:
        return None
    for item in getattr(state, "active_plans", None) or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "") in _TERMINAL:
            continue
        return item
    return None


def next_step_action(state: Any) -> str | None:
    """Return the next-verb key, or None when nothing is waiting."""
    plan = open_active_plan(state)
    slots = dict(getattr(state, "slots", None) or {}) if state is not None else {}
    if plan:
        slots = {**(plan.get("slots") or {}), **slots}
        status = str(plan.get("status") or "")
        if status in {"handoff_ready", "discovering"}:
            return "submit_in_agent"
        if status == "pending_approval":
            return "approve_in_agent"
        if status == "approved":
            return "run_in_agent"
        if status == "paused":
            return "confirm_in_agent"
        if status == "running":
            return None
        return None
    plans = [
        item for item in (getattr(state, "active_plans", None) or [])
        if isinstance(item, dict)
    ]
    if plans:
        return None
    if slots.get("loan_type") or slots.get("leave_type") or slots.get(
        "permission_type"
    ) or slots.get("principal") or slots.get("amount"):
        return "submit_in_agent"
    return None


def render_next_step_offer(state: Any, user_message: str = "") -> str | None:
    action = next_step_action(state)
    if not action:
        return None
    lang = _lang(user_message, state)
    return (_OFFER.get(action) or {}).get(lang) or _OFFER[action]["en"]


def is_next_step_utterance(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or _PAYROLL_RE.search(raw):
        return False
    return bool(_NEXT_ASK.search(raw) or _CONTINUER.search(raw))


def should_offer_next_step(text: str, state: Any) -> bool:
    """True when Chat should speak the next verb without a status ask."""
    if not is_next_step_utterance(text):
        return False
    if next_step_action(state) is None:
        return False
    try:
        from ai.engine.cognition.turn.plan_status import is_plan_status_utterance

        if is_plan_status_utterance(text):
            return False
    except Exception:  # noqa: BLE001
        pass
    try:
        from ai.engine.cognition.turn.handoff_agent import is_ess_write_utterance

        if is_ess_write_utterance(text):
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def append_next_step(text: str, state: Any, user_message: str = "") -> str:
    """Append the offer once. Status copy stays the first sentence."""
    body = (text or "").strip()
    offer = render_next_step_offer(state, user_message)
    if not offer:
        return body
    if offer in body or "Next:" in body or "التالي:" in body:
        return body
    if not body:
        return offer
    return f"{body} {offer}"
