"""Chat ``plan_status`` from ConversationState (PV2-5B · C9 · A8).

When the user asks "status of my request?" and state has an active plan
(or Chat-handoff slots), answer deterministically — 0 LLM calls.
"""
from __future__ import annotations

import re
from typing import Any

_STATUS_ASK = re.compile(
    r"("
    r"\b(?:what(?:'s| is)|how is|where(?:'s| is))\b.{0,48}"
    r"\b(?:status|request|application|plan|loan|leave)\b"
    r"|\bstatus\s+of\s+my\b"
    r"|\bwhat happened\b.{0,32}\b(?:request|loan|leave|plan|application)\b"
    r"|(?:حالة|وضع).{0,24}(?:طلب|قرض|إجازة|اجازة|المخطط|الخطة)"
    r"|ماذا\s+حدث.{0,24}(?:طلب|قرض|إجازة|اجازة)"
    r"|وش\s+صار.{0,16}(?:طلب|قرض)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_WRITE_ASK = re.compile(
    r"\b(?:i\s+(?:want|need)|apply|submit|request a)\b"
    r"|أريد|اريد|أبغى|اطلب",
    re.IGNORECASE,
)

_STATUS_LABEL = {
    "handoff_ready": {
        "en": "ready to submit in Agent — not under review until you submit",
        "ar": "جاهز للتقديم في الوكيل — ليس قيد المراجعة حتى تُرسله",
    },
    "discovering": {
        "en": "still gathering details",
        "ar": "ما زال يجمع التفاصيل",
    },
    "pending_approval": {
        "en": "pending your approval in Tasks, then review",
        "ar": "بانتظار موافقتك في المهام ثم المراجعة",
    },
    "approved": {
        "en": "approved and waiting to run",
        "ar": "مُعتمد وبانتظار التشغيل",
    },
    "running": {
        "en": "running now",
        "ar": "قيد التشغيل الآن",
    },
    "paused": {
        "en": "paused — waiting for a confirmation",
        "ar": "متوقف — بانتظار تأكيد",
    },
    "completed": {
        "en": "completed",
        "ar": "مكتمل",
    },
    "completed_with_gaps": {
        "en": "completed with gaps",
        "ar": "مكتمل مع نواقص",
    },
    "failed": {
        "en": "failed",
        "ar": "فشل",
    },
    "cancelled": {
        "en": "cancelled",
        "ar": "ملغى",
    },
}


def is_plan_status_utterance(text: str) -> bool:
    """True for a status/recall ask — not a new write request."""
    body = (text or "").strip()
    if not body:
        return False
    if _WRITE_ASK.search(body) and not _STATUS_ASK.search(body):
        return False
    return bool(_STATUS_ASK.search(body))


def _lang(text: str, state: Any = None) -> str:
    if re.search(r"[\u0600-\u06FF]", text or ""):
        return "ar"
    lang = str(getattr(state, "language", "") or "")
    return "ar" if lang.startswith("ar") else "en"


def _title_from_slots(slots: dict) -> str:
    loan = slots.get("loan_type")
    leave = slots.get("leave_type")
    amount = slots.get("amount") or slots.get("principal")
    if loan and amount is not None:
        return f"{loan} loan"
    if loan:
        return f"{loan} loan"
    if leave:
        return f"{leave} leave"
    if amount is not None:
        return "loan request"
    return "request"


def can_answer_plan_status(state: Any) -> bool:
    if state is None:
        return False
    if getattr(state, "active_plans", None):
        return True
    slots = getattr(state, "slots", None) or {}
    return bool(
        slots.get("loan_type")
        or slots.get("leave_type")
        or slots.get("principal")
        or slots.get("amount")
    )


def render_plan_status(state: Any, user_message: str = "") -> str:
    """Deterministic bilingual status from ``active_plans`` + slots."""
    lang = _lang(user_message, state)
    plans = list(getattr(state, "active_plans", None) or [])
    slots = dict(getattr(state, "slots", None) or {})
    plan = plans[0] if plans else {}
    if isinstance(plan, dict):
        slots = {**(plan.get("slots") or {}), **slots}
        status = str(plan.get("status") or "handoff_ready")
        title = str(plan.get("title") or "") or _title_from_slots(slots)
        extra = str(plan.get("step_summary") or "").strip()
    else:
        status = "handoff_ready"
        title = _title_from_slots(slots)
        extra = ""

    label = (_STATUS_LABEL.get(status) or _STATUS_LABEL["handoff_ready"])[lang]
    amount = slots.get("amount") or slots.get("principal")
    bits: list[str] = []
    if title:
        bits.append(title)
    if amount is not None:
        bits.append(str(int(amount)) if float(amount) == int(float(amount)) else str(amount))
        if lang == "en":
            bits[-1] = f"{bits[-1]} SAR" if "SAR" not in str(amount) else str(amount)

    if lang == "ar":
        have = "لدي: " + "؛ ".join(bits) if bits else "لدي طلبك."
        more = f" {extra}." if extra else ""
        text = f"{have}. الحالة: {label}.{more}".strip()
        from ai.engine.cognition.turn.next_step import append_next_step

        return append_next_step(text, state, user_message)
    have = "I have: " + "; ".join(bits) if bits else "I have your request."
    more = f" {extra}." if extra else ""
    text = f"{have}. It is {label}.{more}".strip()
    from ai.engine.cognition.turn.next_step import append_next_step

    return append_next_step(text, state, user_message)
