"""Chat ``plan_status`` from ConversationState (PV2-5B · C9 · A8).

When the user asks "status of my request?" and state has an active plan
(or Chat-handoff slots), answer deterministically — 0 LLM calls.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V


import re
from typing import Any

from ai.engine.text.word_match import contains_any_phrase, has_any_word
from ai.engine.cognition.turn.plan_status_i18n import (
    WRITE_ASK_AR,
    STATUS_LABEL,
    any_needle,
    is_status_ask_ar,
)

_STATUS_TAILS = T("turn/plan_status.py::_STATUS_TAILS")
_HAPPENED_TAILS = T("turn/plan_status.py::_HAPPENED_TAILS")


def _is_status_ask_en(text: str) -> bool:
    from ai.engine.text.word_match import has_gapped_words

    if contains_any_phrase(text, ("status of my",)):
        return True
    if has_gapped_words(text, "happened", _HAPPENED_TAILS, max_gap=6):
        return True
    return any(
        has_gapped_words(text, head, _STATUS_TAILS, max_gap=8)
        for head in ("what", "how", "where")
    )

def _is_write_ask_en(text: str) -> bool:
    return (
        has_any_word(text, ("apply", "submit"))
        or contains_any_phrase(text, ("i want", "i need", "request a"))
    )



def is_plan_status_utterance(text: str) -> bool:
    """True for a status/recall ask — not a new write request."""
    body = (text or "").strip()
    if not body:
        return False
    is_status = bool(_is_status_ask_en(body) or is_status_ask_ar(body))
    if (_is_write_ask_en(body) or any_needle(body, WRITE_ASK_AR)) and not is_status:
        return False
    return is_status


def _lang(text: str, state: Any = None) -> str:
    if re.search(r"[\u0600-\u06FF]", text or ""):
        return "ar"
    lang = str(getattr(state, "language", "") or "")
    return "ar" if lang.startswith("ar") else "en"


def _title_from_slots(slots: dict) -> str:
    advance_value = slots.get("loan_type")
    kind_value = slots.get("leave_type")
    amount = slots.get("amount") or slots.get("principal")
    if advance_value and amount is not None:
        return f"{advance_value} {V("t_loan_2")}"
    if advance_value:
        return f"{advance_value} {V("t_loan_2")}"
    if kind_value:
        return f"{kind_value} {V("t_leave")}"
    if amount is not None:
        return V("t_loan_request_2")
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

    label = (STATUS_LABEL.get(status) or STATUS_LABEL["handoff_ready"])[lang]
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
