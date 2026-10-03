"""Section-title answers for the Moodle Ask door.

Titles come from the signed snapshot. The question groups live in the pack.
This module is not imported by engine/.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import re
import yaml

_ROOT = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med"
_PACK = _ROOT / "section_asks.yaml"
_LECTURE = _ROOT / "lecture_asks.yaml"
_FACT = _ROOT / "fact_asks.yaml"
_IDENTITY = _ROOT / "identity_asks.yaml"
_GREET = _ROOT / "greet_asks.yaml"
_COURSE = _ROOT / "course_asks.yaml"
_TOPIC = _ROOT / "topic_asks.yaml"
_REFERENCE = _ROOT / "reference_asks.yaml"
_EXPLAIN = _ROOT / "explain_asks.yaml"
_QUIZ = _ROOT / "quiz_asks.yaml"
_STAFF = _ROOT / "staff_asks.yaml"
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
def _lecture_spec() -> tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...], tuple[str, ...], int]:
    data = yaml.safe_load(_LECTURE.read_text(encoding="utf-8")) or {}
    markers = tuple(
        str(marker).casefold()
        for marker in (data.get("number_markers") or [])
        if str(marker).strip()
    )
    return (
        _term_groups(data, "all_of_any"),
        _term_groups(data, "about_of_any"),
        markers,
        int(data.get("cite_span") or 200),
    )


def _lecture_groups() -> tuple[tuple[str, ...], ...]:
    groups, _about, _markers, _span = _lecture_spec()
    return groups


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
def _identity() -> dict[str, Any]:
    data = yaml.safe_load(_IDENTITY.read_text(encoding="utf-8")) or {}
    groups = []
    for group in data.get("all_of_any") or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    phrases = frozenset(
        " ".join(str(phrase).casefold().split())
        for phrase in (data.get("phrases") or [])
        if str(phrase).strip()
    )
    prefixes = tuple(
        str(prefix).casefold()
        for prefix in (data.get("expert_prefixes") or [])
        if str(prefix).strip()
    )
    return {
        "groups": tuple(groups),
        "phrases": phrases,
        "expert_prefixes": prefixes,
        "answer": str(data.get("answer") or "").strip(),
        "miss": str(data.get("miss") or "").strip() or "This is not in this course.",
    }


def _identity_core(message: str) -> str:
    return " ".join((message or "").casefold().split()).strip(" \t.?!:;,\"'")


def closed_answer(snapshot: dict[str, Any] | None) -> str:
    """Off-course miss on a Moodle course snapshot. Never a page-block tour."""
    miss = _identity()["miss"]
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    headline = _course_headline(course)
    if headline:
        return f"{headline} {miss}"
    return miss


def identity_answer(
    message: str,
    snapshot: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """Who this assistant is, or expert-in-X against this course."""
    text = (message or "").casefold()
    if not text.strip():
        return None
    spec = _identity()
    sentence = spec["answer"]
    folded = " ".join(text.split())
    for prefix in spec["expert_prefixes"]:
        if not folded.startswith(prefix):
            continue
        rest = folded[len(prefix) :].strip(" \t.?!:;,\"'")
        if not rest:
            return sentence or None
        cited = topic_answer("what is " + rest, snapshot, state=state)
        miss = spec["miss"]
        if cited and cited != miss and not cited.endswith(miss):
            return cited
        return closed_answer(snapshot)
    if _identity_core(message) in spec["phrases"]:
        return sentence or None
    if sentence and any(all(term in text for term in terms) for terms in spec["groups"]):
        return sentence
    return None


@lru_cache(maxsize=1)
def _greet_spec() -> dict[str, Any]:
    data = yaml.safe_load(_GREET.read_text(encoding="utf-8")) or {}
    phrases = frozenset(
        " ".join(str(phrase).casefold().split())
        for phrase in (data.get("phrases") or [])
        if str(phrase).strip()
    )
    return {
        "phrases": phrases,
        "hello": str(data.get("hello") or "Hi.").strip() or "Hi.",
        "grounding": str(data.get("grounding") or "").strip(),
    }


def _greet_core(message: str) -> str:
    return " ".join((message or "").casefold().split()).strip(" \t.?!:;,\"'")


def is_greet_ask(message: str) -> bool:
    core = _greet_core(message)
    return bool(core) and core in _greet_spec()["phrases"]


def greet_answer(message: str, snapshot: dict[str, Any] | None = None) -> str | None:
    """Hello plus the open course. None when the message is not a greeting."""
    if not is_greet_ask(message):
        return None
    spec = _greet_spec()
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    headline = _course_headline(course)
    audience = str(page.get("audience") or "").strip().casefold()
    if headline and audience in {"staff", "student"}:
        headline = headline[:-1] + f" ({audience} view)."
    hello = spec["hello"]
    grounding = spec["grounding"]
    if headline and grounding:
        return f"{hello} {headline}\n{grounding}"
    if headline:
        return f"{hello} {headline}"
    if grounding:
        return f"{hello} {grounding}"
    return hello


def _int_set(raw: Any) -> set[int]:
    items: list[Any]
    if isinstance(raw, (list, tuple, set)):
        items = list(raw)
    elif raw is None or raw == "":
        return set()
    else:
        items = [raw]
    out: set[int] = set()
    for item in items:
        try:
            out.add(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _pulse_off_cmids(page: dict[str, Any] | None) -> set[int]:
    return _int_set((page or {}).get("pulse_off_cmids"))


def _pulse_off_sections(page: dict[str, Any] | None) -> set[int]:
    return _int_set((page or {}).get("pulse_off_sections"))


def _row_cmid_off(row: dict[str, Any], off: set[int]) -> bool:
    if not off:
        return False
    try:
        return int(row.get("activity_id")) in off
    except (TypeError, ValueError):
        return False


def _section_number_off(section: dict[str, Any], off: set[int]) -> bool:
    if not off:
        return False
    try:
        return int(section.get("number")) in off
    except (TypeError, ValueError):
        return False


def _term_groups(data: dict[str, Any], key: str) -> tuple[tuple[str, ...], ...]:
    groups = []
    for group in data.get(key) or []:
        terms = tuple(str(term).casefold() for term in group if str(term).strip())
        if terms:
            groups.append(terms)
    return tuple(groups)


@lru_cache(maxsize=1)
def _course_spec() -> dict[str, Any]:
    data = yaml.safe_load(_COURSE.read_text(encoding="utf-8")) or {}
    return {
        "identity": _term_groups(data, "all_of_any"),
        "about": _term_groups(data, "about_of_any"),
        "overview_name": _term_groups(data, "overview_name_of_any"),
        "description_miss": str(data.get("description_miss") or "").strip(),
        "body_miss": str(data.get("body_miss") or "").strip(),
        "outline_cap": int(data.get("outline_cap") or 12),
        "cite_span": int(data.get("cite_span") or 160),
    }


def is_course_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    spec = _course_spec()
    return any(all(term in text for term in terms) for terms in spec["identity"]) or any(
        all(term in text for term in terms) for terms in spec["about"]
    )


def _is_course_about_ask(message: str) -> bool:
    text = (message or "").casefold()
    return any(all(term in text for term in terms) for terms in _course_spec()["about"])


def _listed_section_lines(page: dict[str, Any]) -> list[str]:
    sections = page.get("sections") or []
    if not sections:
        return []
    off = _pulse_off_sections(page)
    lines = ["Sections on this page:"]
    for section in sections[:40]:
        if not isinstance(section, dict):
            continue
        if _section_number_off(section, off):
            continue
        name = str(section.get("name") or "").strip() or "(untitled)"
        lines.append(f"- {section.get('number')}: {name}")
    if page.get("sections_truncated"):
        lines.append("Further sections exist and were not included.")
    return lines


def _course_headline(course: dict[str, Any]) -> str | None:
    full = str(course.get("fullname") or "").strip()
    short = str(course.get("shortname") or "").strip()
    if full and short:
        if short.casefold() in full.casefold():
            return f"This course is {full}."
        return f"This course is {short}: {full}."
    if full or short:
        return f"This course is {full or short}."
    return None


def _short_span(text: str, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return f"{cut}…" if cut else cleaned[:limit]


def _load_course_bank(shortname: str) -> dict[str, dict]:
    from ai.moodle_bank import load_c3, load_c4_drive, load_c4_files, load_c5_youtube, load_extra

    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _course_about_answer(page: dict[str, Any], headline: str) -> str:
    """Capped week outline from titles, plus a course-overview bank span only."""
    spec = _course_spec()
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    sections = [row for row in (page.get("sections") or []) if isinstance(row, dict)]
    titles = [str(row.get("name") or "").strip() for row in sections]
    titles = [title for title in titles if title]
    parts = [headline]
    cap = max(1, int(spec["outline_cap"]))
    if titles:
        parts.append("Listed weeks and topics on this page include:")
        for title in titles[:cap]:
            parts.append(f"- {title}")
        if len(titles) > cap:
            parts.append(f"…and {len(titles) - cap} more section titles on the page.")
    bank = _load_course_bank(shortname) if shortname else {}
    cite = _about_cite(bank, int(spec["cite_span"]))
    if cite:
        parts.append(cite)
    elif not titles:
        miss = spec["description_miss"]
        if miss:
            parts.append(miss)
    return "\n".join(parts)


def _is_overview_row(row: dict[str, Any], overview_groups: tuple[tuple[str, ...], ...]) -> bool:
    name = str(row.get("name") or "").casefold()
    if not name or not overview_groups:
        return False
    return any(all(term in name for term in terms) for terms in overview_groups)


def _about_cite(bank: dict[str, dict], limit: int) -> str:
    """One short span from a course-overview row. Never a lecture PDF."""
    if not bank:
        return ""
    overview_groups = _course_spec()["overview_name"]
    rows = [row for row in bank.values() if _is_overview_row(row, overview_groups)]
    if not rows:
        return ""
    kind_order = {"file": 0, "google": 1, "page": 2, "book": 3, "youtube": 4, "label": 5}
    rows_sorted = sorted(
        rows,
        key=lambda row: (
            kind_order.get(str(row.get("kind") or ""), 9),
            -int(row.get("activity_id") or 0),
            -len(str(row.get("text") or "")),
        ),
    )
    for row in rows_sorted:
        span = _short_span(str(row.get("text") or ""), limit)
        if len(span) < 40:
            continue
        return f"{row['id']}\n{span}"
    return ""

def course_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    """Identity is the course name. About is a grounded, capped outline."""
    if not is_course_ask(message):
        return None
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    headline = _course_headline(course)
    if not headline:
        return "No course is open."
    if _is_course_about_ask(message):
        return _course_about_answer(page, headline)
    return headline


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
    from ai.moodle_bank import (
        MISS,
        cite_open_activity,
        listed_world,
        load_c3,
        load_c4_drive,
        load_c4_files,
        load_c5_youtube,
        load_extra,
    )

    page = snapshot or {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "")
    activity = page.get("activity") if isinstance(page.get("activity"), dict) else {}
    cmid = activity.get("cmid")
    if not shortname or not cmid:
        return MISS
    try:
        if int(cmid) in _pulse_off_cmids(page):
            return MISS
    except (TypeError, ValueError):
        return MISS
    _groups, min_span = _fact_spec()
    bank = {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }
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
    groups, about, _markers, _span = _lecture_spec()
    if any(all(term in text for term in terms) for terms in groups):
        return True
    if any(all(term in text for term in terms) for terms in about):
        return True
    return _lecture_number(message) is not None


def _lecture_number(message: str) -> int | None:
    text = (message or "").casefold()
    _groups, _about, markers, _span = _lecture_spec()
    for marker in markers:
        start = 0
        while True:
            pos = text.find(marker, start)
            if pos < 0:
                break
            rest = text[pos + len(marker) :]
            if marker == "l":
                # L10 / l10 only — not every word that contains "l".
                if rest[:1].isdigit():
                    digits = []
                    for ch in rest:
                        if ch.isdigit():
                            digits.append(ch)
                        else:
                            break
                    if digits:
                        return int("".join(digits))
            else:
                rest = rest.lstrip(" :-_")
                digits = []
                for ch in rest:
                    if ch.isdigit():
                        digits.append(ch)
                    else:
                        break
                if digits:
                    return int("".join(digits))
            start = pos + 1
    return None


def _is_lecture_about_ask(message: str) -> bool:
    text = (message or "").casefold()
    _groups, about, _markers, _span = _lecture_spec()
    if any(all(term in text for term in terms) for terms in about):
        return True
    return _lecture_number(message) is not None and not any(
        all(term in text for term in terms) for terms in _groups
    )


def _lecture_token_from_name(name: str) -> int | None:
    return _lecture_number(name) if name else None


def _compact_name(name: str) -> str:
    return "".join(ch for ch in (name or "").casefold() if ch.isalnum())


def _name_has_lecture_num(name: str, num: int) -> bool:
    compact = _compact_name(name)
    token = f"l{num}"
    start = 0
    while True:
        pos = compact.find(token, start)
        if pos < 0:
            return False
        end = pos + len(token)
        if end >= len(compact) or not compact[end].isdigit():
            return True
        start = pos + 1


def _row_matches_lecture(row: dict[str, Any], num: int | None, section_name: str = "") -> bool:
    name = str(row.get("name") or "")
    if num is not None and _name_has_lecture_num(name, num):
        return True
    section = _compact_name(section_name)
    row_name = _compact_name(name)
    if section and row_name and (section in row_name or row_name in section):
        return True
    return False


def _prefer_lecture_rows(rows: list[dict], num: int | None) -> list[dict]:
    if not rows:
        return []

    def score(row: dict) -> tuple:
        name = str(row.get("name") or "").casefold()
        compact = _compact_name(name)
        kind = str(row.get("kind") or "")
        primary = 0
        if num is not None:
            token = f"l{num}"
            if f"{token}-" in name.replace(" ", "") or f"{token}:" in name.replace(" ", ""):
                primary = 0
            elif f"{token}&" in compact or "activity" in name:
                primary = 2
            else:
                primary = 1
        kind_rank = {"file": 0, "page": 1, "book": 1, "label": 2, "google": 3, "youtube": 4}.get(kind, 5)
        return (primary, kind_rank, int(row.get("activity_id") or 0))

    return sorted(rows, key=score)


def _resolve_named_lecture(
    message: str, page: dict[str, Any], bank: dict[str, dict]
) -> tuple[dict[str, Any] | None, list[dict], int | None]:
    """Section on this page plus bank rows for that lecture number/name.

    Resolution order is deterministic and additive, so the L-number golds
    keep their answer: (1) a snapshot section whose title carries the
    number (``L10``), (2) a snapshot section whose section number equals the
    lecture number (week/session courses), (3) a bank row title that carries
    the number. In (2) and (3) the rows are matched by the section name, so a
    course whose snapshot titles carry no L-number still cites the lecture.
    """
    num = _lecture_number(message)
    sections = [row for row in (page.get("sections") or []) if isinstance(row, dict)]
    off_sec = _pulse_off_sections(page)
    off_cm = _pulse_off_cmids(page)

    def _strict_matched(section: dict[str, Any]) -> list[dict]:
        section_name = str(section.get("name") or "")
        matched = [
            row
            for row in bank.values()
            if not _row_cmid_off(row, off_cm)
            and _row_matches_lecture(row, num, section_name)
            and (num is None or _name_has_lecture_num(str(row.get("name") or ""), num) or num == _lecture_token_from_name(section_name))
        ]
        if num is not None:
            matched = [row for row in matched if _name_has_lecture_num(str(row.get("name") or ""), num)]
        return matched

    def _section_rows(section: dict[str, Any]) -> list[dict]:
        """Rows for a section. L-number rows win; else match by section name.

        A generic page row ("Lecture Video") carries the section number but
        not the topic words, so it is a last-resort match for the section.
        """
        section_name = str(section.get("name") or "")
        base = [
            row
            for row in bank.values()
            if not _row_cmid_off(row, off_cm)
            and str(row.get("text") or "").strip()
            and _row_matches_lecture(row, num, section_name)
        ]
        if not base:
            try:
                number = int(section.get("number"))
            except (TypeError, ValueError):
                number = None
            if number is not None:
                base = [
                    row
                    for row in bank.values()
                    if not _row_cmid_off(row, off_cm)
                    and str(row.get("text") or "").strip()
                    and row.get("sectionnum") is not None
                    and int(row.get("sectionnum") or -1) == number
                ]
        if num is not None:
            named = [row for row in base if _name_has_lecture_num(str(row.get("name") or ""), num)]
            if named:
                return named
        return base

    section = None
    for row in sections:
        name = str(row.get("name") or "")
        if num is not None and _name_has_lecture_num(name, num):
            if _section_number_off(row, off_sec):
                continue
            section = row
            break
    if section is not None:
        matched = _strict_matched(section)
        if matched:
            return section, _prefer_lecture_rows(matched, num), num
        # The snapshot section names the lecture but no bank row carries the
        # L-number: keep the section and match its rows by name.
        named_rows = _section_rows(section)
        if named_rows:
            return section, _prefer_lecture_rows(named_rows, num), num

    # Week/session courses number their lectures by section number.
    if num is not None:
        for row in sections:
            try:
                number = int(row.get("number"))
            except (TypeError, ValueError):
                continue
            if number != num or _section_number_off(row, off_sec):
                continue
            number_rows = _section_rows(row)
            if number_rows:
                return row, _prefer_lecture_rows(number_rows, num), num

    # Fall back to bank names when the snapshot title uses a different number.
    if num is not None:
        for row in bank.values():
            if _row_cmid_off(row, off_cm):
                continue
            if _name_has_lecture_num(str(row.get("name") or ""), num):
                bank_section = {"number": None, "name": str(row.get("name") or "")}
                named_rows = _section_rows(bank_section)
                if named_rows:
                    return bank_section, _prefer_lecture_rows(named_rows, num), num

    if section is None:
        return None, [], num
    return section, [], num


def _lecture_about_answer(message: str, snapshot: dict[str, Any] | None) -> str:
    from ai.moodle_bank import MISS

    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname:
        return MISS
    _groups, _about, _markers, cite_span = _lecture_spec()
    bank = _load_course_bank(shortname)
    section, rows, num = _resolve_named_lecture(message, page, bank)
    if section is None:
        return MISS
    label = str(section.get("name") or "").strip() or (f"L{num}" if num is not None else "lecture")
    number = section.get("number")
    head = f"Section {number}: {label}." if number is not None else f"{label}."
    if not rows:
        body_miss = _course_spec()["body_miss"] or MISS
        return f"{head}\n{body_miss}"
    primary = rows[0]
    span = _short_span(str(primary.get("text") or ""), cite_span)
    parts = [head, f"{primary['id']}\n{span}" if span else str(primary["id"])]
    extras = []
    seen = {primary.get("activity_id")}
    for row in rows[1:]:
        aid = row.get("activity_id")
        if aid in seen:
            continue
        seen.add(aid)
        extras.append(str(row.get("name") or row["id"]))
        if len(extras) >= 2:
            break
    if extras:
        parts.append("Also openable on this lecture: " + "; ".join(extras) + ".")
    return "\n".join(parts)


def lecture_answer(message: str, snapshot: dict[str, Any] | None) -> str | None:
    if not is_lecture_ask(message):
        return None
    if _is_lecture_about_ask(message):
        return _lecture_about_answer(message, snapshot)
    activity = (snapshot or {}).get("activity")
    if not isinstance(activity, dict):
        return "This page has no lecture to cite."
    try:
        if int(activity.get("cmid")) in _pulse_off_cmids(snapshot if isinstance(snapshot, dict) else {}):
            return "This page has no lecture to cite."
    except (TypeError, ValueError):
        pass
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
    lines = _listed_section_lines(page)
    if not lines:
        return "This page has no sections to cite."
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _topic_spec() -> dict[str, Any]:
    data = yaml.safe_load(_TOPIC.read_text(encoding="utf-8")) or {}
    prefixes = tuple(
        str(prefix).casefold()
        for prefix in (data.get("prefixes") or [])
        if str(prefix).strip()
    )
    short = data.get("short_query") if isinstance(data.get("short_query"), dict) else {}
    stopwords = frozenset(
        str(word).casefold().strip()
        for word in (short.get("stopwords") or [])
        if str(word).strip()
    )
    greetings = frozenset(
        str(word).casefold().strip()
        for word in (short.get("greetings") or [])
        if str(word).strip()
    )
    return {
        "prefixes": prefixes,
        "miss": str(data.get("miss") or "This is not in this course.").strip(),
        "cite_span": int(data.get("cite_span") or 200),
        "body_cite_span": int(data.get("body_cite_span") or 160),
        "short_max_tokens": int(short.get("max_tokens") or 0),
        "short_stopwords": stopwords,
        "short_greetings": greetings,
    }


def _is_identity_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    spec = _identity()
    if _identity_core(message) in spec["phrases"]:
        return True
    folded = " ".join(text.split())
    if any(folded.startswith(prefix) for prefix in spec["expert_prefixes"]):
        return True
    return any(all(term in text for term in terms) for terms in spec["groups"])


def _topic_meta_blocked(topic: str) -> bool:
    """Course/page meta complements stay on other doors."""
    if topic in {"this course", "the course", "this", "the"}:
        return True
    if topic.startswith("this course") or topic.startswith("the course"):
        return True
    if topic.endswith(" on this page") or topic in {
        "on this page",
        "the sections",
        "the weeks",
        "the outline",
        "the contents",
        "the contents of this page",
    }:
        return True
    return False


def _short_topic_from_text(text: str) -> str | None:
    """Bare topic from pack short_query. None for greetings / chatty turns."""
    spec = _topic_spec()
    max_tokens = int(spec["short_max_tokens"] or 0)
    if max_tokens <= 0:
        return None
    core = text.strip(" \t.?!:;,\"'")
    if not core:
        return None
    # Multi-clause chat is not a short topic query.
    if any(mark in core for mark in (".", "!", "?", ";", ":")):
        return None
    tokens = core.split()
    if not tokens or len(tokens) > max_tokens:
        return None
    greetings = spec["short_greetings"]
    stopwords = spec["short_stopwords"]
    if tokens[0] in greetings:
        return None
    if core in stopwords or core in greetings:
        return None
    if all(token in stopwords or token in greetings for token in tokens):
        return None
    if _topic_meta_blocked(core):
        return None
    return core


def _topic_from_message(message: str) -> str | None:
    """Named topic after a pack prefix or short_query, else None."""
    if (
        is_section_ask(message)
        or is_course_ask(message)
        or is_lecture_ask(message)
        or is_fact_ask(message)
        or is_reference_ask(message)
        or _is_identity_ask(message)
        or is_greet_ask(message)
    ):
        return None
    text = " ".join((message or "").casefold().split())
    if not text:
        return None
    for prefix in _topic_spec()["prefixes"]:
        if not text.startswith(prefix):
            continue
        topic = text[len(prefix) :].strip(" \t.?!:;,\"'")
        if not topic or _topic_meta_blocked(topic):
            return None
        return topic
    return _short_topic_from_text(text)


def is_topic_ask(message: str) -> bool:
    return _topic_from_message(message) is not None


def _snapshot_title_activity_ids(page: dict[str, Any] | None, topic: str) -> set[int]:
    """Activity ids whose snapshot open-activity title matches topic."""
    needle = topic.casefold()
    if not needle or not isinstance(page, dict):
        return set()
    off = _pulse_off_cmids(page)
    ids: set[int] = set()
    activity = page.get("activity") if isinstance(page.get("activity"), dict) else None
    if activity and needle in str(activity.get("name") or "").casefold():
        cmid = activity.get("cmid")
        if cmid is not None:
            try:
                value = int(cmid)
            except (TypeError, ValueError):
                value = None
            if value is not None and value not in off:
                ids.add(value)
    return ids


def _topic_word_pattern(topic: str):
    """Word-boundary matcher for a topic phrase. Vocabulary stays in the pack."""
    parts = [part for part in re.split(r"\s+", str(topic or "").strip()) if part]
    if not parts:
        return None
    phrase = r"\s+".join(re.escape(part) for part in parts)
    return re.compile(rf"(?<![A-Za-z0-9]){phrase}(?![A-Za-z0-9])", re.IGNORECASE)


_BODY_KIND_RANK = {"file": 0, "page": 1, "book": 1, "label": 2, "google": 3, "youtube": 4}


def _body_rank(row: dict, count: int) -> tuple:
    """Most occurrences, then lowest cmid, then kind, then longest text."""
    activity = int(row.get("activity_id") or 0)
    cmid = activity if activity > 0 else 10 ** 9
    return (
        -count,
        cmid,
        _BODY_KIND_RANK.get(str(row.get("kind") or ""), 5),
        -len(str(row.get("text") or "")),
    )


def _body_topic_rows(rows: list[dict], topic: str) -> list[dict]:
    """Passages whose body holds the topic word. Whole-word, occurrence-ranked."""
    pattern = _topic_word_pattern(topic)
    if pattern is None:
        return []
    scored: list[tuple[dict, int]] = []
    for row in rows:
        text = str(row.get("text") or "")
        if not text.strip():
            continue
        count = len(pattern.findall(text))
        if count:
            scored.append((row, count))
    scored.sort(key=lambda item: _body_rank(item[0], item[1]))
    return [row for row, _count in scored]


def _bounded_body_span(text: str, pattern, limit: int) -> str:
    """Exact substring around the matched word, sentence-bounded and capped."""
    match = pattern.search(text)
    if match is None or limit <= 0:
        return ""
    return _window_around(text, match.start(), match.end(), limit)


def _window_around(text: str, start: int, end: int, limit: int) -> str:
    """Exact substring around one match, sentence-bounded and capped.

    The result is always a contiguous slice of ``text``, so a caller can
    assert ``span in text`` with no normalization.
    """
    if limit <= 0:
        return ""
    sent_start = text.rfind(". ", 0, start)
    sent_start = 0 if sent_start < 0 else sent_start + 2
    sent_end = text.find(". ", end)
    sent_end = len(text) if sent_end < 0 else sent_end + 1
    if sent_end - sent_start <= limit:
        return text[sent_start:sent_end].strip()
    seg_start = max(sent_start, start - 24)
    seg_end = min(sent_end, seg_start + limit)
    if seg_end < end:
        seg_end = end
        seg_start = max(sent_start, seg_end - limit)
    while 0 < seg_end < len(text) and text[seg_end - 1:seg_end].isalnum() and text[seg_end:seg_end + 1].isalnum():
        seg_end -= 1
    while seg_start > 0 and text[seg_start - 1:seg_start].isalnum() and text[seg_start:seg_start + 1].isalnum():
        seg_start += 1
    # A capped window can land on leading punctuation ("," / ";"). Move to the
    # next word start, never past the match, so the span begins on a word.
    while seg_start < start and not text[seg_start].isalnum():
        seg_start += 1
    span = text[seg_start:seg_end].strip()
    if len(span) > limit:
        span = span[:limit].rstrip()
    return span


def _topic_rows(
    bank: dict[str, dict],
    topic: str,
    page: dict[str, Any] | None = None,
) -> tuple[list[dict], str]:
    """Rows for a topic plus the origin: snapshot, title, body, or none.

    Title matches win. The body search runs only when no title match exists,
    and it is whole-word and occurrence-ranked (R-body2/R-body3).
    """
    needle = topic.casefold()
    snap_ids = _snapshot_title_activity_ids(page, topic)
    off_cm = _pulse_off_cmids(page if isinstance(page, dict) else {})
    rows_iter = [
        row
        for row in bank.values()
        if not _row_cmid_off(row, off_cm)
    ]
    if snap_ids:
        snap_hits = [
            row
            for row in rows_iter
            if row.get("activity_id") in snap_ids
            and str(row.get("text") or "").strip()
        ]
        if snap_hits:
            return _prefer_topic_rows(snap_hits), "snapshot"
    title_hits = [
        row
        for row in rows_iter
        if needle in str(row.get("name") or "").casefold()
        and str(row.get("text") or "").strip()
    ]
    if title_hits:
        return _prefer_topic_rows(title_hits), "title"
    bag = page if isinstance(page, dict) else {}
    off_sec = _pulse_off_sections(bag)
    named = [
        row
        for row in (bag.get("sections") or [])
        if isinstance(row, dict) and needle in str(row.get("name") or "").casefold()
    ]
    if named and all(_section_number_off(row, off_sec) for row in named):
        return [], "none"
    body_hits = _body_topic_rows(rows_iter, topic)
    if not body_hits:
        return [], "none"
    return body_hits, "body"


def _rows_for_topic(
    bank: dict[str, dict],
    topic: str,
    page: dict[str, Any] | None = None,
) -> list[dict]:
    """Title matches win. Whole-word body hits only when no title match exists."""
    return _topic_rows(bank, topic, page=page)[0]


def _prefer_topic_rows(rows: list[dict]) -> list[dict]:
    kind_rank = {"file": 0, "page": 1, "book": 1, "label": 2, "google": 3, "youtube": 4}

    def score(row: dict) -> tuple:
        return (
            kind_rank.get(str(row.get("kind") or ""), 5),
            int(row.get("activity_id") or 0),
            -len(str(row.get("text") or "")),
        )

    return sorted(rows, key=score)


def _topic_section_line(page: dict[str, Any], topic: str, rows: list[dict]) -> str:
    needle = topic.casefold()
    sections = [row for row in (page.get("sections") or []) if isinstance(row, dict)]
    off_sec = _pulse_off_sections(page)
    section = next(
        (
            row
            for row in sections
            if needle in str(row.get("name") or "").casefold()
            and not _section_number_off(row, off_sec)
        ),
        None,
    )
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        names.append(name)
        if len(names) >= 4:
            break
    activities = "; ".join(names) if names else topic
    if section is not None:
        number = section.get("number")
        label = str(section.get("name") or "").strip() or topic
        if number is not None:
            return f"Section {number}: {label}. Activities: {activities}."
        return f"{label}. Activities: {activities}."
    return f"Activities: {activities}."


def _topic_index_fallback(
    topic: str,
    bank: dict[str, dict],
    page: dict[str, Any] | None,
    shortname: str,
) -> tuple[str, str] | None:
    """Recall-only keyword-index cite for a title/whole-file miss.

    Scoped to the open activity and unique-passage rule (see
    ``ai.moodle_bank.cite_topic_index``). Returns ``None`` so the door keeps its
    exact miss whenever the index is absent or the hit is not unique.
    """
    bag = page if isinstance(page, dict) else {}
    activity = bag.get("activity") if isinstance(bag.get("activity"), dict) else {}
    cmid = activity.get("cmid")
    if cmid in (None, ""):
        return None
    from ai.moodle_bank import cite_topic_index, listed_world

    try:
        return cite_topic_index(
            topic,
            bank,
            course=shortname,
            activity_id=int(cmid),
            world=listed_world(shortname),
        )
    except (TypeError, ValueError):
        return None


def topic_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """Cite this course’s bank for a named topic, or the course miss."""
    topic = _topic_from_message(message)
    if topic is None:
        return None
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    spec = _topic_spec()
    miss = spec["miss"]
    if not shortname:
        return miss
    bank = _load_course_bank(shortname)
    rows, origin = _topic_rows(bank, topic, page=page)
    if not rows:
        fallback = _topic_index_fallback(topic, bank, page, shortname)
        if fallback is None:
            return miss
        pid, span = fallback
        row = bank.get(pid)
        if row is None:
            return miss
        head = _topic_section_line(page, topic, [row])
        if isinstance(state, dict):
            from ai.moodle_ask_state import set_resolved_topic

            set_resolved_topic(state, topic=topic, shortname=shortname, passage_ids=[pid])
        return "\n".join([head, f"{pid}\n{span}"])
    head = _topic_section_line(page, topic, rows)
    primary = rows[0]
    text = str(primary.get("text") or "")
    if origin == "body":
        pattern = _topic_word_pattern(topic)
        span = _bounded_body_span(text, pattern, int(spec["body_cite_span"])) if pattern else ""
    else:
        span = _short_span(text, int(spec["cite_span"]))
    if not span:
        return miss
    parts = [head, f"{primary['id']}\n{span}"]
    extras: list[str] = []
    seen = {primary.get("activity_id")}
    for row in rows[1:]:
        aid = row.get("activity_id")
        if aid in seen:
            continue
        seen.add(aid)
        extras.append(str(row.get("name") or row["id"]))
        if len(extras) >= 2:
            break
    if extras:
        parts.append("Also openable on this topic: " + "; ".join(extras) + ".")
    if isinstance(state, dict):
        from ai.moodle_ask_state import set_resolved_topic

        set_resolved_topic(
            state,
            topic=topic,
            shortname=shortname,
            passage_ids=[str(row["id"]) for row in rows if row.get("id")],
        )
    return "\n".join(parts)


@lru_cache(maxsize=1)
def _reference_spec() -> dict[str, Any]:
    data = yaml.safe_load(_REFERENCE.read_text(encoding="utf-8")) or {}
    return {
        "groups": _term_groups(data, "all_of_any"),
        "cite_span": int(data.get("cite_span") or 160),
        "no_topic": str(data.get("no_topic") or "No course topic is in focus.").strip(),
        "course_label": str(
            data.get("course_label") or "Course materials for {topic}:"
        ).strip(),
    }


def is_reference_ask(message: str) -> bool:
    text = (message or "").casefold()
    if not text.strip():
        return False
    return any(all(term in text for term in terms) for terms in _reference_spec()["groups"])


def reference_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """Cite course passages for the resolved topic. Never opens the web."""
    if not is_reference_ask(message):
        return None
    from ai.moodle_ask_state import (
        COURSE_SHORTNAME,
        PASSAGE_IDS,
        RESOLVED_TOPIC,
    )

    spec = _reference_spec()
    bag = state if isinstance(state, dict) else {}
    topic = str(bag.get(RESOLVED_TOPIC) or "").strip()
    if not topic:
        return spec["no_topic"]
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(
        bag.get(COURSE_SHORTNAME) or course.get("shortname") or ""
    ).strip()
    if not shortname:
        return spec["no_topic"]
    bank = _load_course_bank(shortname)
    ids = [str(pid) for pid in (bag.get(PASSAGE_IDS) or []) if str(pid).strip()]
    rows: list[dict] = []
    if ids:
        for pid in ids:
            row = bank.get(pid)
            if isinstance(row, dict) and str(row.get("text") or "").strip():
                rows.append(row)
    if not rows:
        rows = _rows_for_topic(bank, topic, page=page)
    if not rows:
        return _topic_spec()["miss"]
    label = spec["course_label"].replace("{topic}", topic)
    parts = [label]
    span_limit = int(spec["cite_span"])
    seen: set[Any] = set()
    for row in rows:
        aid = row.get("activity_id")
        if aid in seen:
            continue
        seen.add(aid)
        span = _short_span(str(row.get("text") or ""), span_limit)
        if not span:
            continue
        parts.append(f"{row['id']}\n{span}")
        if len(seen) >= 2:
            break
    if len(parts) < 2:
        return _topic_spec()["miss"]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# T2 Explain · T3 Quiz · T5 Staff coworker (frozen 2 Oct 2026).
# Vocabulary lives in explain_asks.yaml / quiz_asks.yaml / staff_asks.yaml.
# Every emitted span is a contiguous slice of a selected passage's text, so a
# caller can assert ``span in passage_text`` with no normalization.
# ---------------------------------------------------------------------------


def _doc(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _str_tuple(data: dict[str, Any], key: str) -> tuple[str, ...]:
    return tuple(
        str(item).casefold()
        for item in (data.get(key) or [])
        if str(item).strip()
    )


@lru_cache(maxsize=1)
def _explain_spec() -> dict[str, Any]:
    data = _doc(_EXPLAIN)
    return {
        "prefixes": _str_tuple(data, "prefixes"),
        "miss": str(data.get("miss") or "This is not in this course.").strip(),
        "max_spans": int(data.get("max_spans") or 3),
        "span": int(data.get("span") or 220),
        "min_span": int(data.get("min_span") or 30),
        "label": str(data.get("label") or "Verbatim spans from {passage}:").strip(),
    }


@lru_cache(maxsize=1)
def _quiz_spec() -> dict[str, Any]:
    data = _doc(_QUIZ)
    return {
        "prefixes": _str_tuple(data, "prefixes"),
        "miss": str(data.get("miss") or "This is not in this course.").strip(),
        "max_items": int(data.get("max_items") or 3),
        "span": int(data.get("span") or 260),
        "label": str(
            data.get("label") or "Practice from this course — answers are verbatim spans."
        ).strip(),
    }


@lru_cache(maxsize=1)
def _staff_spec() -> dict[str, Any]:
    data = _doc(_STAFF)
    return {
        "off_list": str(data.get("off_list") or "This is not on the course list.").strip(),
        "gap_miss": str(data.get("gap_miss") or "No pack gaps found for this course.").strip(),
        "ilo_miss": str(data.get("ilo_miss") or "No pack passage contains those terms.").strip(),
        "gap_label": str(data.get("gap_label") or "Not in the pack on {course}:").strip(),
        "ilo_label": str(data.get("ilo_label") or "Pack passages containing those terms:").strip(),
        "draft_label": str(
            data.get("draft_label")
            or "Draft extra note (proposal only — apply it in the Extra tab):"
        ).strip(),
        "gap_max": int(data.get("gap_max") or 8),
        "ilo_max": int(data.get("ilo_max") or 5),
        "draft_max_spans": int(data.get("draft_max_spans") or 3),
        "draft_span": int(data.get("draft_span") or 220),
        "stopwords": frozenset(
            str(word).casefold().strip()
            for word in (data.get("stopwords") or [])
            if str(word).strip()
        ),
        "gap_prefixes": _str_tuple(data, "gap_prefixes"),
        "ilo_prefixes": _str_tuple(data, "ilo_prefixes"),
        "draft_prefixes": _str_tuple(data, "draft_prefixes"),
    }


def _is_other_door(message: str) -> bool:
    """True when another door already owns the message shape."""
    return (
        is_section_ask(message)
        or is_course_ask(message)
        or is_lecture_ask(message)
        or is_fact_ask(message)
        or is_reference_ask(message)
        or _is_identity_ask(message)
        or is_greet_ask(message)
    )


def _prefix_topic(message: str, prefixes: tuple[str, ...]) -> str | None:
    """Remainder after the first matching pack prefix, else None."""
    text = " ".join((message or "").casefold().split())
    if not text:
        return None
    for prefix in prefixes:
        if not text.startswith(prefix):
            continue
        topic = text[len(prefix) :].strip(" \t.?!:;,\"'")
        if not topic or _topic_meta_blocked(topic):
            return None
        return topic
    return None


def _sentence_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] in ".!?\n":
            ranges.append((start, i + 1))
            start = i + 1
            while start < n and text[start] in " \t\r\n":
                start += 1
            i = start
            continue
        i += 1
    ranges.append((start, n))
    return ranges


def _exact_spans(text: str, limit: int, min_span: int) -> list[str]:
    """Sentence-bounded slices of text; each is an exact substring, deduped."""
    raw = str(text or "")
    out: list[str] = []
    seen: set[str] = set()
    for start, end in _sentence_ranges(raw):
        seg = raw[start:end].strip()
        if len(seg) < min_span:
            continue
        if limit > 0 and len(seg) > limit:
            cut = seg[:limit]
            if " " in cut:
                cut = cut.rsplit(" ", 1)[0]
            seg = cut.strip()
        if seg and seg not in seen:
            seen.add(seg)
            out.append(seg)
    return out


def _keep_substrings(candidates: list[str], text: str) -> list[str]:
    """A proposal survives only when it is an exact substring of the passage.

    The door writes no prose, so it proposes nothing; this guard makes the
    honesty rule explicit and testable: a non-substring is dropped, never
    printed.
    """
    return [item for item in candidates if item and item in text]


def _seed_resolved_topic(state: Any, topic: str, shortname: str, rows: list[dict]) -> None:
    if not isinstance(state, dict):
        return
    from ai.moodle_ask_state import set_resolved_topic

    set_resolved_topic(
        state,
        topic=topic,
        shortname=shortname,
        passage_ids=[str(row["id"]) for row in rows if row.get("id")],
    )


def is_explain_ask(message: str) -> bool:
    if _is_other_door(message):
        return False
    return _prefix_topic(message, _explain_spec()["prefixes"]) is not None


def explain_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """T2 — 2–3 verbatim spans from ONE selected passage, plus its id."""
    if _is_other_door(message):
        return None
    spec = _explain_spec()
    topic = _prefix_topic(message, spec["prefixes"])
    if topic is None:
        return None
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname:
        return spec["miss"]
    bank = _load_course_bank(shortname)
    rows, _origin = _topic_rows(bank, topic, page=page)
    if not rows:
        return spec["miss"]
    primary = rows[0]
    primary_text = str(primary.get("text") or "")
    spans = _keep_substrings(
        _exact_spans(primary_text, spec["span"], spec["min_span"]),
        primary_text,
    )[: spec["max_spans"]]
    if not spans:
        return spec["miss"]
    head = _topic_section_line(page, topic, rows)
    label = spec["label"].replace("{passage}", str(primary["id"]))
    parts = [head, label]
    for span in spans:
        parts.append(f"- {span}")
    _seed_resolved_topic(state, topic, shortname, rows)
    return "\n".join(parts)


def is_quiz_ask(message: str) -> bool:
    if _is_other_door(message):
        return False
    return _prefix_topic(message, _quiz_spec()["prefixes"]) is not None


def _quiz_items(
    rows: list[dict],
    topic: str,
    max_items: int,
    limit: int,
) -> list[tuple[dict, str, str]]:
    """(row, cloze question, verbatim answer span) from passages only."""
    pattern = _topic_word_pattern(topic)
    if pattern is None:
        return []
    items: list[tuple[dict, str, str]] = []
    seen: set[str] = set()
    for row in rows:
        text = str(row.get("text") or "")
        for match in pattern.finditer(text):
            answer = _window_around(text, match.start(), match.end(), limit)
            if not answer or answer in seen:
                continue
            cloze = pattern.sub("____", answer, count=1)
            if "____" not in cloze:
                continue
            seen.add(answer)
            items.append((row, cloze, answer))
            if len(items) >= max_items:
                return items
    return items


def quiz_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """T3 — cloze items whose answers are verbatim spans, or an exact miss."""
    if _is_other_door(message):
        return None
    spec = _quiz_spec()
    topic = _prefix_topic(message, spec["prefixes"])
    if topic is None:
        return None
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname:
        return spec["miss"]
    bank = _load_course_bank(shortname)
    rows, _origin = _topic_rows(bank, topic, page=page)
    if not rows:
        return spec["miss"]
    items = _quiz_items(rows, topic, spec["max_items"], spec["span"])
    if not items:
        return spec["miss"]
    head = _topic_section_line(page, topic, rows)
    parts = [head, spec["label"]]
    for index, (row, cloze, answer) in enumerate(items, 1):
        name = str(row.get("name") or "").strip() or str(row.get("id") or "")
        parts.append(f"Q{index} — from {name} [{row['id']}]")
        parts.append(cloze)
        parts.append(f"Answer: {answer}")
    return "\n".join(parts)


def _staff_ask(message: str) -> tuple[str, str] | None:
    spec = _staff_spec()
    text = " ".join((message or "").casefold().split())
    if not text:
        return None
    for prefix in spec["gap_prefixes"]:
        if text.startswith(prefix):
            return ("gap", "")
    for prefix in spec["ilo_prefixes"]:
        if text.startswith(prefix):
            topic = text[len(prefix) :].strip(" \t.?!:;,\"'")
            return ("ilo", topic) if topic else None
    for prefix in spec["draft_prefixes"]:
        if text.startswith(prefix):
            topic = text[len(prefix) :].strip(" \t.?!:;,\"'")
            return ("draft", topic) if topic else None
    return None


def _staff_term_hits(
    shortname: str,
    query: str,
    spec: dict[str, Any],
) -> list[tuple[dict, str]]:
    """Passages ranked by how many query terms they contain (whole-word)."""
    terms = [
        term
        for term in re.findall(r"[a-z0-9]+", str(query or "").casefold())
        if len(term) > 2 and term not in spec["stopwords"]
    ]
    unique = list(dict.fromkeys(terms))
    if not unique:
        return []
    patterns = [
        re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)
        for term in unique
    ]
    bank = _load_course_bank(shortname)
    scored: list[tuple[dict, int]] = []
    for row in bank.values():
        text = str(row.get("text") or "")
        if not text:
            continue
        hits = sum(1 for pattern in patterns if pattern.search(text))
        if hits:
            scored.append((row, hits))
    scored.sort(
        key=lambda item: (
            -item[1],
            int(item[0].get("activity_id") or 0),
            str(item[0].get("id") or ""),
        )
    )
    out: list[tuple[dict, str]] = []
    for row, _hits in scored[: int(spec["ilo_max"])]:
        text = str(row.get("text") or "")
        window = ""
        for pattern in patterns:
            match = pattern.search(text)
            if match is not None:
                window = _window_around(text, match.start(), match.end(), 160)
                break
        out.append((row, window))
    return out


def _staff_gap_answer(shortname: str, spec: dict[str, Any]) -> str:
    from ai.moodle_bank import course_roster

    roster = course_roster(shortname)
    if not roster.get("ok"):
        return spec["off_list"]
    gaps = [row for row in (roster.get("activities") or []) if not row.get("in_pack")]
    if not gaps:
        return spec["gap_miss"]
    gaps.sort(
        key=lambda row: (
            int(row.get("sectionnum") or 0),
            int(row.get("cmid") or 0),
            str(row.get("name") or ""),
        )
    )
    parts = [spec["gap_label"].replace("{course}", shortname)]
    for row in gaps[: int(spec["gap_max"])]:
        name = str(row.get("name") or "(untitled)")
        kind = str(row.get("kind") or "?")
        parts.append(f"- Section {row.get('sectionnum')}: {name} ({kind})")
    if len(gaps) > int(spec["gap_max"]):
        parts.append(f"…and {len(gaps) - int(spec['gap_max'])} more not-in-pack activities.")
    return "\n".join(parts)


def _staff_ilo_answer(shortname: str, topic: str, spec: dict[str, Any]) -> str:
    hits = _staff_term_hits(shortname, topic, spec)
    if not hits:
        return spec["ilo_miss"]
    parts = [spec["ilo_label"].replace("{course}", shortname)]
    for row, window in hits:
        name = str(row.get("name") or "").strip() or str(row["id"])
        parts.append(f"- {name} [{row['id']}]")
        if window:
            parts.append(window)
    return "\n".join(parts)


def _staff_draft_answer(shortname: str, topic: str, spec: dict[str, Any]) -> str:
    bank = _load_course_bank(shortname)
    rows, _origin = _topic_rows(bank, topic, page=None)
    if not rows:
        return _topic_spec()["miss"]
    primary = rows[0]
    spans = _exact_spans(
        str(primary.get("text") or ""), int(spec["draft_span"]), 30
    )[: int(spec["draft_max_spans"])]
    if not spans:
        return _topic_spec()["miss"]
    parts = [
        spec["draft_label"],
        f"Course: {shortname}",
        f"Title: {topic}",
        f"Source: {primary['id']}",
    ]
    for span in spans:
        parts.append(f"- {span}")
    parts.append("No write was made. Paste and save it in the Extra tab.")
    return "\n".join(parts)


def staff_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """T5 — staff-only read-only coworker actions. Never mutates the host."""
    ask = _staff_ask(message)
    if ask is None:
        return None
    page = snapshot if isinstance(snapshot, dict) else {}
    if str(page.get("audience") or "").strip().casefold() == "student":
        return None
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname:
        return None
    spec = _staff_spec()
    kind, topic = ask
    if kind == "gap":
        return _staff_gap_answer(shortname, spec)
    if kind == "ilo":
        return _staff_ilo_answer(shortname, topic, spec)
    return _staff_draft_answer(shortname, topic, spec)


def teach_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """L-T T1 — grounded multi-passage lesson draft (see ``ai.moodle_teach``).

    A read-only proposal: every emitted sentence is a verbatim span of the
    passage it cites, and the draft claims no Moodle write (ADR-0046). Kept
    here as a thin delegator so ``door_answer`` needs no new import shape.
    """
    from ai.moodle_teach import teach_answer as _teach_answer

    return _teach_answer(message, snapshot, state=state)
