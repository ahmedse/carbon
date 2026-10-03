"""L-T T1 — grounded multi-passage lesson DRAFT + the B3 faithfulness pass.

TEACHING-WAVE-SPEC §1.1 (T1) / §1.6 / §4. This module lives OUTSIDE
``engine/**``. It adds no ``StagedExit``, no routing ``re.compile``, and no
phrase table (the ask vocabulary is in ``domain_packs/aast-med/teach_asks.yaml``).

The B3 pass is deterministic and offline: every curriculum-fact sentence a
draft emits is accepted only when it is a **verbatim substring** (exact
characters) of the single passage it cites, and that passage id resolves in the
open course bank. A candidate with no verbatim span is **dropped, never
printed** (§4 anti-shallow rule 3). The draft is labelled ``draft`` and claims
no Moodle write (R11); Chat proposes, the Extra tab applies (ADR-0046).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ai.moodle_bank import listed_shortnames
from ai.moodle_page import _exact_spans, _load_course_bank, _prefix_topic

_ROOT = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med"
_TEACH = _ROOT / "teach_asks.yaml"
_STRUCT = _ROOT / "teach_structured.yaml"
_BODY_KIND_RANK = {"file": 0, "google": 1, "page": 1, "book": 1, "label": 2, "youtube": 3}


@lru_cache(maxsize=1)
def _spec() -> dict[str, Any]:
    data = yaml.safe_load(_TEACH.read_text(encoding="utf-8")) or {}
    return {
        "prefixes": tuple(
            str(item).casefold() for item in (data.get("prefixes") or []) if str(item).strip()
        ),
        "miss": str(data.get("miss") or "This is not in this course.").strip(),
        "label": str(data.get("label") or "Draft lesson (proposal only):").strip(),
        "grounding_note": str(data.get("grounding_note") or "").strip(),
        "no_write": str(
            data.get("no_write") or "No write was made. Paste and save it in the Extra tab."
        ).strip(),
        "max_passages": int(data.get("max_passages") or 3),
        "per_passage": int(data.get("per_passage") or 2),
        "span": int(data.get("span") or 450),
        "min_span": int(data.get("min_span") or 40),
        "stopwords": frozenset(
            str(word).casefold().strip() for word in (data.get("stopwords") or []) if str(word).strip()
        ),
    }


def is_teach_ask(message: str) -> bool:
    return _prefix_topic(message, _spec()["prefixes"]) is not None


def _topic_tokens(topic: str, stopwords: frozenset[str]) -> list[str]:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", str(topic or "").casefold())
        if len(token) > 2 and token not in stopwords
    ]
    if tokens:
        return tokens
    folded = " ".join(str(topic or "").casefold().split())
    return [folded] if folded else []


def ground_sentence(passage_text: str, sentence: str) -> bool:
    """The B3 check: the sentence is an exact substring of the cited passage."""
    candidate = str(sentence or "")
    return bool(candidate) and candidate in str(passage_text or "")


def _grounded_spans(text: str, topic: str, spec: dict[str, Any]) -> list[str]:
    """Sentence-bounded exact substrings of ``text`` that hold the topic.

    Reuses the same slice rule as the other doors and then applies the B3 pass:
    a slice that is not an exact substring is dropped, never returned. At most
    ``per_passage`` spans, so the draft stays bounded.
    """
    tokens = _topic_tokens(topic, spec["stopwords"])
    if not tokens:
        return []
    out: list[str] = []
    for candidate in _exact_spans(text, spec["span"], spec["min_span"]):
        if not any(token in candidate.casefold() for token in tokens):
            continue
        if not ground_sentence(text, candidate):
            continue
        out.append(candidate)
        if len(out) >= spec["per_passage"]:
            break
    return out


def _scored_rows(bank: dict[str, dict], topic: str, spec: dict[str, Any]) -> list[tuple[dict, int]]:
    tokens = _topic_tokens(topic, spec["stopwords"])
    scored: list[tuple[dict, int]] = []
    for row in bank.values():
        text = str(row.get("text") or "")
        if not text.strip():
            continue
        count = sum(text.casefold().count(token) for token in tokens)
        if count:
            scored.append((row, count))
    scored.sort(
        key=lambda item: (
            -item[1],
            _BODY_KIND_RANK.get(str(item[0].get("kind") or ""), 9),
            int(item[0].get("activity_id") or 0),
            str(item[0].get("id") or ""),
        )
    )
    return scored


def lesson_draft(
    topic: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str:
    """A grounded, multi-passage lesson draft. Read-only; never a host write."""
    spec = _spec()
    page = snapshot if isinstance(snapshot, dict) else {}
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname:
        return spec["miss"]
    bank = _load_course_bank(shortname)
    picked: list[tuple[dict, list[str]]] = []
    for row, _count in _scored_rows(bank, topic, spec):
        spans = _grounded_spans(str(row.get("text") or ""), topic, spec)
        if spans:
            picked.append((row, spans))
        if len(picked) >= spec["max_passages"]:
            break
    if not picked:
        return spec["miss"]
    parts = [spec["label"], f"Course: {shortname}", f"Topic: {topic}"]
    if spec["grounding_note"]:
        parts.append(spec["grounding_note"])
    for row, spans in picked:
        parts.append(str(row["id"]))
        for span in spans:
            parts.append(f"- {span}")
    parts.append(spec["no_write"])
    return "\n".join(parts)


def teach_answer(
    message: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """L-T T1 door: a staff lesson ask → a grounded draft, or None.

    Student audiences and off-list courses are refused (None). Chat never
    writes; the returned text is a proposal for the Extra tab.
    """
    topic = _prefix_topic(message, _spec()["prefixes"])
    if topic is None:
        return None
    page = snapshot if isinstance(snapshot, dict) else {}
    if str(page.get("audience") or "").strip().casefold() == "student":
        return None
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname or shortname not in listed_shortnames():
        return None
    return lesson_draft(topic, page, state=state)


# ---------------------------------------------------------------------------
# L-T T2 — STRUCTURED lesson (ILO + grounded worked example + grounded
# assessment), staff-approved. TEACHING-WAVE-SPEC §1.1 (T2) / §1.6 / §4.
#
# Every ILO, worked-example, and assessment line is a VERBATIM span of the
# single passage it cites, or it is DROPPED. Nothing here is reachable from a
# Chat turn: the only write is a staff Apply in the Extra tab (ADR-0046).
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _structured_spec() -> dict[str, Any]:
    data = yaml.safe_load(_STRUCT.read_text(encoding="utf-8")) or {}
    return {
        "miss": str(data.get("miss") or "This is not in this course.").strip(),
        "label": str(data.get("label") or "Structured lesson (proposal only):").strip(),
        "objectives_label": str(data.get("objectives_label") or "Learning objectives:").strip(),
        "example_label": str(data.get("example_label") or "Worked example:").strip(),
        "assessment_label": str(data.get("assessment_label") or "Assessment:").strip(),
        "blank": str(data.get("blank") or "________"),
        "grounding_note": str(data.get("grounding_note") or "").strip(),
        "no_write": str(
            data.get("no_write") or "No write was made by Chat. Apply it in the Extra tab."
        ).strip(),
        "max_objectives": int(data.get("max_objectives") or 3),
        "max_examples": int(data.get("max_examples") or 2),
        "max_assessment": int(data.get("max_assessment") or 2),
        "objective_markers": tuple(
            str(marker).casefold().strip()
            for marker in (data.get("objective_markers") or [])
            if str(marker).strip()
        ),
    }


def _is_objective(span: str, markers: tuple[str, ...]) -> bool:
    folded = str(span or "").casefold()
    return any(marker in folded for marker in markers)


def _cloze_question(span: str, topic: str, spec: dict[str, Any]) -> str:
    """A cloze of a verbatim span: one topic token blanked. No new fact."""
    tokens = _topic_tokens(topic, spec["stopwords"])
    folded = span.casefold()
    for token in tokens:
        idx = folded.rfind(token)
        if idx >= 0:
            blanked = span[:idx] + _structured_spec()["blank"] + span[idx + len(token):]
            if blanked != span:
                return blanked
    parts = span.rsplit(" ", 1)
    if len(parts) == 2 and parts[0]:
        return parts[0] + " " + _structured_spec()["blank"]
    return _structured_spec()["blank"] + " " + span


def _grounded_items(
    topic: str, snapshot: dict[str, Any] | None
) -> tuple[str, dict[str, dict], list[tuple[str, str]]] | None:
    """(shortname, bank, [(passage_id, verbatim_span)]) for a staff-visible bank."""
    spec = _spec()
    page = snapshot if isinstance(snapshot, dict) else {}
    if str(page.get("audience") or "").strip().casefold() == "student":
        return None
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    shortname = str(course.get("shortname") or "").strip()
    if not shortname or shortname not in listed_shortnames():
        return None
    bank = _load_course_bank(shortname)
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row, _count in _scored_rows(bank, topic, spec):
        text = str(row.get("text") or "")
        pid = str(row.get("id"))
        for span in _grounded_spans(text, topic, spec):
            if span in seen or not ground_sentence(text, span):
                continue
            seen.add(span)
            items.append((pid, span))
    return shortname, bank, items


def build_structured_lesson(
    topic: str,
    snapshot: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """A grounded structured lesson (ILO + worked example + assessment) or None.

    Deterministic and offline. Every emitted line is an exact substring of the
    passage it cites; an ungroundable candidate is dropped. Returns None when a
    complete structured lesson (>=1 ILO, >=1 example, >=1 assessment) cannot be
    grounded — never a partly invented lesson.
    """
    gathered = _grounded_items(topic, snapshot)
    if gathered is None:
        return None
    shortname, bank, items = gathered
    if not items:
        return None
    sspec = _structured_spec()
    markers = sspec["objective_markers"]

    objectives = [
        (pid, span) for pid, span in items if _is_objective(span, markers)
    ][: sspec["max_objectives"]]
    used = {span for _pid, span in objectives}
    if not objectives:
        # Fall back to the top grounded span; still a verbatim span, never a fact.
        objectives = [items[0]]
        used = {items[0][1]}

    remaining = [(pid, span) for pid, span in items if span not in used]
    if not remaining:
        return None
    examples = sorted(remaining, key=lambda item: len(item[1]), reverse=True)[
        : sspec["max_examples"]
    ]
    used |= {span for _pid, span in examples}
    remaining = [(pid, span) for pid, span in remaining if span not in used]
    assessment = [
        {"question": _cloze_question(span, topic, _spec()), "answer": span, "passage_ref": pid}
        for pid, span in remaining[: sspec["max_assessment"]]
    ]
    if not objectives or not examples or not assessment:
        return None

    lesson: dict[str, Any] = {
        "status": "proposal",
        "grounded": True,
        "course": shortname,
        "topic": str(topic or "").strip(),
        "objectives": [{"text": span, "passage_ref": pid} for pid, span in objectives],
        "worked_example": [
            {"text": span, "passage_ref": pid, "label": sspec["example_label"]}
            for pid, span in examples
        ],
        "assessment": assessment,
    }
    # Final B3 gate: any line that is somehow not a verbatim span fails closed.
    for item in lesson["objectives"] + lesson["worked_example"]:
        if not ground_sentence(str(bank.get(item["passage_ref"], {}).get("text") or ""), item["text"]):
            return None
    for item in lesson["assessment"]:
        if not ground_sentence(str(bank.get(item["passage_ref"], {}).get("text") or ""), item["answer"]):
            return None
    return lesson


def structured_lesson_text(lesson: dict[str, Any] | None) -> str:
    """Render a structured lesson proposal for display. Read-only; no write."""
    sspec = _structured_spec()
    if not isinstance(lesson, dict) or not lesson.get("grounded"):
        return sspec["miss"]
    parts = [
        sspec["label"],
        f"Course: {lesson.get('course')}",
        f"Topic: {lesson.get('topic')}",
    ]
    if sspec["grounding_note"]:
        parts.append(sspec["grounding_note"])
    parts.append(sspec["objectives_label"])
    for item in lesson.get("objectives") or []:
        parts.append(str(item.get("passage_ref")))
        parts.append(f"- {item.get('text')}")
    parts.append(sspec["example_label"])
    for item in lesson.get("worked_example") or []:
        parts.append(str(item.get("passage_ref")))
        parts.append(f"- {item.get('text')}")
    parts.append(sspec["assessment_label"])
    for item in lesson.get("assessment") or []:
        parts.append(str(item.get("passage_ref")))
        parts.append(f"Q: {item.get('question')}")
        parts.append(f"- {item.get('answer')}")
    parts.append(sspec["no_write"])
    return "\n".join(parts)


def approved_lessons_dir() -> Path:
    """Where approved structured lessons are appended as JSONL (pack, no table)."""
    override = os.environ.get("MOODLE_APPROVED_LESSONS_DIR", "").strip()
    if not override:
        try:
            from django.conf import settings as dj

            if dj.configured():
                override = str(getattr(dj, "MOODLE_APPROVED_LESSONS_DIR", "") or "").strip()
        except Exception:  # pragma: no cover - settings optional outside Django
            override = ""
    return Path(override) if override else (_ROOT / "approved-lessons")


def approved_lessons_path(shortname: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", str(shortname or "").strip()) or "unknown"
    return approved_lessons_dir() / f"{safe}.jsonl"


def _lesson_is_grounded(lesson: dict[str, Any], bank: dict[str, dict]) -> bool:
    for item in (lesson.get("objectives") or []) + (lesson.get("worked_example") or []):
        text = str(item.get("text") or "")
        passage = str(bank.get(item.get("passage_ref"), {}).get("text") or "")
        if not ground_sentence(passage, text):
            return False
    for item in lesson.get("assessment") or []:
        answer = str(item.get("answer") or "")
        passage = str(bank.get(item.get("passage_ref"), {}).get("text") or "")
        if not ground_sentence(passage, answer):
            return False
    return bool(lesson.get("objectives")) and bool(lesson.get("worked_example")) and bool(
        lesson.get("assessment")
    )


def apply_structured_lesson(
    topic: str,
    shortname: str,
    staff_ref: str = "",
) -> dict[str, Any]:
    """Staff Apply: build + re-verify + append one approved lesson to the pack.

    This is a HOST-UI action (the Extra tab endpoint). It is never called by a
    Chat turn, and it never trusts an externally supplied lesson: it rebuilds
    from the committed bank so only grounded lines can be stored. No DB table.
    """
    shortname = str(shortname or "").strip()
    if shortname not in listed_shortnames():
        return {"ok": False, "error": "off_list"}
    snapshot = {
        "audience": "staff",
        "course": {"id": 0, "shortname": shortname, "fullname": shortname, "visible_to_user": True},
        "sections": [],
    }
    lesson = build_structured_lesson(topic, snapshot)
    if not lesson:
        return {"ok": False, "error": "ungrounded"}
    bank = _load_course_bank(shortname)
    if not _lesson_is_grounded(lesson, bank):
        return {"ok": False, "error": "ungrounded"}
    record = {
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "shortname": shortname,
        "topic": str(topic or "").strip(),
        "applied_by": str(staff_ref or ""),
        "lesson": lesson,
    }
    path = approved_lessons_path(shortname)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "error": None, "path": str(path), "lesson": lesson}
