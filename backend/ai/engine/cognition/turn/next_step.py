"""L4 — next ESS action from ConversationState (0 LLM).

Status labels stay in ``plan_status``. This module names the verb the
user must take next (switch to Agent / Approve / Run / Confirm). Chat
never submits (ADR-0046).
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


from typing import Any

from ai.engine.text.word_match import contains_any_phrase, has_any_word, has_arabic_script
from ai.engine.cognition.turn.next_step_i18n import (
    CONTINUER_AR,
    NEXT_ASK_AR,
    OFFER,
    PAYROLL_AR,
    any_needle,
)

_TERMINAL = T("turn/next_step.py::_TERMINAL")

_NEXT_ASK_PHRASES = T("turn/next_step.py::_NEXT_ASK_PHRASES")
_CONTINUERS = T("turn/next_step.py::_CONTINUERS")
_PAYROLL_WORDS = T("turn/next_step.py::_PAYROLL_WORDS")
_PAYROLL_PHRASES = T("turn/next_step.py::_PAYROLL_PHRASES")


def _is_next_ask(text: str) -> bool:
    return contains_any_phrase(text, _NEXT_ASK_PHRASES)


def _is_continuer(text: str) -> bool:
    raw = (text or "").strip().rstrip(".?! ").casefold()
    return raw in _CONTINUERS


def _is_payroll(text: str) -> bool:
    return has_any_word(text, _PAYROLL_WORDS) or contains_any_phrase(text, _PAYROLL_PHRASES)



def _lang(text: str, state: Any = None) -> str:
    if has_arabic_script(text or ""):
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
    return (OFFER.get(action) or {}).get(lang) or OFFER[action]["en"]


def is_next_step_utterance(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or _is_payroll(raw) or any_needle(raw, PAYROLL_AR):
        return False
    return bool(
        _is_next_ask(raw)
        or _is_continuer(raw)
        or any_needle(raw, NEXT_ASK_AR)
        or any_needle(raw, CONTINUER_AR)
    )


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
