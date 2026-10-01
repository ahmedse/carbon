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
_GREET = _ROOT / "greet_asks.yaml"
_COURSE = _ROOT / "course_asks.yaml"
_TOPIC = _ROOT / "topic_asks.yaml"
_REFERENCE = _ROOT / "reference_asks.yaml"
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
    from ai.moodle_bank import load_c3, load_c4_drive, load_c4_files, load_c5_youtube

    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
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
    """Section on this page plus bank rows for that lecture number/name."""
    num = _lecture_number(message)
    sections = [row for row in (page.get("sections") or []) if isinstance(row, dict)]
    off_sec = _pulse_off_sections(page)
    off_cm = _pulse_off_cmids(page)
    section = None
    for row in sections:
        name = str(row.get("name") or "")
        if num is not None and _name_has_lecture_num(name, num):
            if _section_number_off(row, off_sec):
                continue
            section = row
            break
    if section is None and num is not None:
        # Fall back to bank names when the snapshot title uses a different number.
        for row in bank.values():
            if _row_cmid_off(row, off_cm):
                continue
            if _name_has_lecture_num(str(row.get("name") or ""), num):
                section = {"number": None, "name": str(row.get("name") or "")}
                break
    if section is None:
        return None, [], num
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
    preferred = _prefer_lecture_rows(matched, num)
    return section, preferred, num


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


def _rows_for_topic(
    bank: dict[str, dict],
    topic: str,
    page: dict[str, Any] | None = None,
) -> list[dict]:
    """Title matches win. Incidental text hits only when no title match exists.

    Snapshot section/activity titles and bank activity names both count as
    titles. Snapshot-titled open-activity ids win when present.
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
            return _prefer_topic_rows(snap_hits)
    title_hits = [
        row
        for row in rows_iter
        if needle in str(row.get("name") or "").casefold()
        and str(row.get("text") or "").strip()
    ]
    if title_hits:
        return _prefer_topic_rows(title_hits)
    bag = page if isinstance(page, dict) else {}
    off_sec = _pulse_off_sections(bag)
    named = [
        row
        for row in (bag.get("sections") or [])
        if isinstance(row, dict) and needle in str(row.get("name") or "").casefold()
    ]
    if named and all(_section_number_off(row, off_sec) for row in named):
        return []
    text_hits = [
        row
        for row in rows_iter
        if needle in str(row.get("text") or "").casefold()
        and str(row.get("text") or "").strip()
    ]
    return _prefer_topic_rows(text_hits)


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
    miss = _topic_spec()["miss"]
    if not shortname:
        return miss
    bank = _load_course_bank(shortname)
    rows = _rows_for_topic(bank, topic, page=page)
    if not rows:
        return miss
    head = _topic_section_line(page, topic, rows)
    primary = rows[0]
    span = _short_span(str(primary.get("text") or ""), int(_topic_spec()["cite_span"]))
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
