"""Deterministic 0-LLM Chat surfaces (C8) — thanks, clock, notification FAQ.

Navigation and how/where UI grounding stay in ``navigation.py``.
Write handoff stays in ``handoff_agent.py``. Plan status stays in
``plan_status.py``. This module is only the leftover clock/ack/FAQ
short-circuits that must not spend intent+draft.
"""
from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any

from ai.engine.cognition.turn.navigation import detect_lang, normalize_text

_THANKS_RE = re.compile(
    r"("
    r"^\s*(thanks|thank\s+you|thx|ty)\b"
    r"|شكرا"
    r")",
    re.IGNORECASE,
)
_THANKS_WRITE_RE = re.compile(
    r"\b(?:submit|apply|request|approve|send)\b"
    r"|قدّم|قدم|أرسل|ارسل",
    re.IGNORECASE,
)
_CLOCK_RE = re.compile(
    r"("
    r"\b(?:what(?:'s| is)|tell\s+me)\b.{0,24}"
    r"\b(?:today'?s\s+date|the\s+date|date\s+today|day\s+is\s+it|month)\b"
    r"|\bwhat\s+month\b"
    r"|\bwhat\s+year\b"
    r"|ما\s+(?:هو\s+)?(?:تاريخ|اليوم|الشهر)"
    r"|اليوم\s+كم"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_MONTH_ASK_RE = re.compile(r"\bmonth\b|الشهر", re.IGNORECASE)
_NOTIFICATION_RE = re.compile(
    r"\bnotifications?\b|إشعارات|اشعارات|تنبيهات",
    re.IGNORECASE,
)
_SHOW_OPEN_RE = re.compile(
    r"\b(?:show|open|go\s+to|where)\b|أرني|ارني|افتح|وين|أين",
    re.IGNORECASE,
)

_THANKS_TEXT = {
    "en": "You're welcome. Ask if you need anything else.",
    "ar": "على الرحب والسعة. أنا هنا إذا احتجت شيئاً آخر.",
}
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_DATE_IN_TEXT_RE = re.compile(
    r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,\s*(\d{4}))?\b",
    re.IGNORECASE,
)
_DEIXIS_RE = re.compile(
    r"\bis that\s+(before|after|earlier than|later than)\b",
    re.IGNORECASE,
)
_END_MONTH_RE = re.compile(r"end of (the )?month", re.IGNORECASE)
_NOTIFICATION_TEXT = {
    "en": "Notifications are in the bell in the header — there is no separate notifications page.",
    "ar": "الإشعارات في الجرس أعلى الصفحة — لا توجد صفحة منفصلة للإشعارات.",
}


def is_thanks(text: str) -> bool:
    """True for a bare thank-you — not 'thanks for submitting'."""
    raw = (text or "").strip()
    if not raw or not _THANKS_RE.search(raw):
        return False
    return not _THANKS_WRITE_RE.search(raw)


def is_clock_ask(text: str) -> bool:
    """True for today's date / current month — not leave-start or payroll when."""
    raw = (text or "").strip()
    return bool(raw and _CLOCK_RE.search(raw))


def is_notification_faq(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or not _NOTIFICATION_RE.search(raw):
        return False
    return bool(_SHOW_OPEN_RE.search(raw) or normalize_text(raw) in {
        "notifications", "notification",
    })


def render_thanks(text: str, facts: list[dict[str, str]] | None = None) -> str:
    lang = "ar" if detect_lang(text) == "ar" else "en"
    base = _THANKS_TEXT[lang]
    if not facts:
        return base
    fact = facts[-1]
    if lang == "ar":
        return f"{base} سأتذكر {fact['key']} {fact['value']}."
    return (
        f"You're welcome. I'll keep remembering your {fact['key']} "
        f"{fact['value']}."
    )


def render_clock(text: str, today: date | None = None) -> str:
    day = today or date.today()
    lang = detect_lang(text)
    month = day.strftime("%B")
    if _MONTH_ASK_RE.search(text or "") and "date" not in (text or "").lower():
        if lang == "ar":
            return f"نحن في {month} {day.year}."
        return f"We are in {month} {day.year}."
    if lang == "ar":
        return f"اليوم {day.day} {month} {day.year}."
    return f"Today is {month} {day.day}, {day.year}."


def render_notification_faq(text: str) -> str:
    return _NOTIFICATION_TEXT["ar" if detect_lang(text) == "ar" else "en"]


def last_dates_in_history(
    history: list[dict] | None,
    today: date | None = None,
) -> list[date]:
    """Dates mentioned in recent assistant turns (most recent last)."""
    day = today or date.today()
    found: list[date] = []
    for msg in history or []:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        for match in _DATE_IN_TEXT_RE.finditer(str(msg.get("content") or "")):
            month = _MONTHS.get(match.group(1).lower())
            if not month:
                continue
            year = int(match.group(3) or day.year)
            try:
                found.append(date(year, month, int(match.group(2))))
            except ValueError:
                continue
    return found


def is_date_deixis(text: str) -> bool:
    raw = (text or "").strip()
    return bool(raw and _DEIXIS_RE.search(raw) and _END_MONTH_RE.search(raw))


def render_date_deixis(
    text: str,
    history: list[dict] | None = None,
    today: date | None = None,
) -> str | None:
    if not is_date_deixis(text):
        return None
    day = today or date.today()
    dates = last_dates_in_history(history, day)
    if not dates:
        return None
    last = dates[-1]
    end = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
    match = _DEIXIS_RE.search(text or "")
    relation = (match.group(1) if match else "before").lower()
    is_before = last <= end
    wants_before = relation.startswith("before") or relation.startswith("earlier")
    yes = is_before if wants_before else not is_before
    month = last.strftime("%B")
    clause = (
        f"{month} {last.day} is before the end of {end.strftime('%B')}"
        if is_before
        else f"{month} {last.day} is after the end of {end.strftime('%B')}"
    )
    return f"{'Yes' if yes else 'No'}, {clause}."


def try_zero_llm_answer(
    text: str,
    *,
    today: date | None = None,
    facts: list[dict[str, str]] | None = None,
    history: list[dict] | None = None,
    newly_stored: bool = False,
) -> dict[str, Any] | None:
    """Return ``{decision, text}`` when the utterance is a 0-LLM surface."""
    from ai.engine.cognition.turn.memory_recall import (
        is_memory_use,
        render_fact_ack,
        render_recall,
    )

    raw = (text or "").strip()
    if not raw:
        return None
    known = list(facts or [])
    if is_thanks(raw):
        return {
            "decision": "answer",
            "text": render_thanks(raw, known),
            "gate": "thanks",
        }
    if is_clock_ask(raw):
        return {"decision": "answer", "text": render_clock(raw, today), "gate": "clock"}
    if is_notification_faq(raw):
        return {
            "decision": "answer",
            "text": render_notification_faq(raw),
            "gate": "notification_faq",
        }
    deixis = render_date_deixis(raw, history, today)
    if deixis:
        return {"decision": "answer", "text": deixis, "gate": "date_deixis"}
    if known and is_memory_use(raw, known):
        return {"decision": "answer", "text": render_recall(raw, known), "gate": "memory_recall"}
    if newly_stored and known:
        return {"decision": "answer", "text": render_fact_ack(raw, known), "gate": "memory_store"}
    return None
