"""Section-title answers for the Moodle Ask door.

Titles come from the signed snapshot. The question groups live in the pack.
This module is not imported by engine/.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med"
_PACK = _ROOT / "section_asks.yaml"
_LECTURE = _ROOT / "lecture_asks.yaml"
_FACT = _ROOT / "fact_asks.yaml"
_IDENTITY = _ROOT / "identity_asks.yaml"
_COURSE = _ROOT / "course_asks.yaml"
_ACCESS = _ROOT / "access_reasons.yaml"


@lru_cache(maxsize=1)
def _groups() -> tuple[tuple[str, ...], ...]:
    data = yaml.safe_load(_PACK.read_text(encoding="utf-8")) or {}
    groups = []
    for group in data.get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups)


def is_section_ask(message: str, groups: tuple[tuple[str, ...], ...] | None = None) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    for terms in groups if groups is not None else _groups():
        if all(term in text for term in terms):
            return True
    return False


@lru_cache(maxsize=1)
def _lecture_groups() -> tuple[tuple[str, ...], ...]:
    data = yaml.safe_load(_LECTURE.read_text(encoding="utf-8")) or {}
    groups = []
    for group in data.get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups)


@lru_cache(maxsize=1)
def _fact_spec() -> tuple[tuple[tuple[str, ...], ...], int]:
    data = yaml.safe_load(_FACT.read_text(encoding="utf-8")) or {}
    groups = []
    for group in data.get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups), int(data.get("min_span") or 24)


@lru_cache(maxsize=1)
def _identity() -> tuple[tuple[tuple[str, ...], ...], str]:
    data = yaml.safe_load(_IDENTITY.read_text(encoding="utf-8")) or {}
    groups = []
    for group in data.get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups), str(data.get("answer") or "").strip()


def identity_answer(message: str, snapshot: dict[str, Any] | None = None) -> str | None:
    """Who this assistant is. None when the message is not that question."""
    del snapshot
    text = (message or "").casefold()
    if not text.strip():
        return None
    groups, sentence = _identity()
    if not sentence:
        return None
    if any(all(term in text for term in terms) for terms in groups):
        return sentence
    return None


@lru_cache(maxsize=1)
def _course_groups() -> tuple[tuple[str, ...], ...]:
    data = yaml.safe_load(_COURSE.read_text(encoding="utf-8")) or {}
    groups = []
    for group in data.get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups)


def is_course_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    return any(all(term in text for term in terms) for terms in _course_groups())


def course_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    """Name the open course from the snapshot. None when this is not that question."""
    if not is_course_ask(message):
        return None
    course = (snapshot or {}).get("course") if isinstance((snapshot or {}).get("course"), dict) else {}
    full = str(course.get("fullname") or "").strip()
    short = str(course.get("shortname") or "").strip()
    if full and short:
        return f"This course is {full} ({short})."
    if full or short:
        return f"This course is {full or short}."
    return "No course is open."


def is_fact_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    groups, _min_span = _fact_spec()
    return any(all(term in text for term in terms) for terms in groups)


def fact_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    """Cite the open activity, or the lecture miss. None when this is not a fact question."""
    if not is_fact_ask(message):
        return None
    from ai.moodle_bank import MISS, cite_open_activity, listed_world, load_c3, load_c4_files

    page = snapshot or {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "")
    activity = page.get("activity") if isinstance(page.get("activity"), dict) else {}
    cmid = activity.get("cmid")
    if not shortname or not cmid:
        return MISS
    _groups, min_span = _fact_spec()
    bank = {**load_c3(shortname), **load_c4_files(shortname)}
    return cite_open_activity(
        message,
        bank,
        course=shortname,
        activity_id=int(cmid),
        world=listed_world(shortname),
        min_span=min_span,
    )


def is_lecture_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    return any(all(term in text for term in terms) for terms in _lecture_groups())


def lecture_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    if not is_lecture_ask(message):
        return None
    activity = (snapshot or {}).get("activity")
    if not isinstance(activity, dict):
        return "This page has no lecture to cite."
    name = str(activity.get("name") or "").strip()
    if not name:
        return "This page has no lecture to cite."
    return f"This lecture is {name}."


@lru_cache(maxsize=1)
def _access() -> dict[str, Any]:
    return yaml.safe_load(_ACCESS.read_text(encoding="utf-8")) or {}


def _why_groups() -> tuple[tuple[str, ...], ...]:
    data = _access()
    groups = []
    for group in (data.get("why") or {}).get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups)


def is_why_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    return any(all(term in text for term in terms) for terms in _why_groups())


def access_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    """One of the four reasons, or nothing. Never copies a name from the snapshot."""
    page = snapshot or {}
    reason = str(page.get("access") or "")
    answers = (_access().get("reasons") or {})
    sentence = str(answers.get(reason) or "").strip()
    if not sentence:
        return None
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    page_closed = reason in {"hidden", "course_list"} or (
        reason == "not_enrolled" and not course.get("visible_to_user")
    )
    if page_closed or (reason == "wrong_group" and is_why_ask(message)) or (
        reason == "not_enrolled" and is_why_ask(message)
    ):
        return sentence
    return None


def section_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    if not is_section_ask(message):
        return None
    page = snapshot or {}
    sections = page.get("sections") or []
    if not sections:
        return "This page has no sections to cite."
    lines = ["Sections on this page:"]
    for section in sections[:40]:
        if not isinstance(section, dict):
            continue
        name = str(section.get("name") or "").strip() or "(untitled)"
        lines.append(f"- {section.get('number')}: {name}")
    if page.get("sections_truncated"):
        lines.append("Further sections exist and were not included.")
    return "\n".join(lines)
