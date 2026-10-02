"""Offline conformance harness for the Ask doors on the 13 listed courses.

No live server and no LLM: the real aast-med bank and the signed page path
are enough. It locks the staff bar per course — identity/greet, course-about
(grounded, never a 40-section dump), "tell me about lecture N", a real
body-only topic span, explain (<= 3 verbatim spans), quiz (cloze answers are
verbatim pack spans), the same term on another course (honest refuse), a
clinical-advice ask (fixed refusal, not a model decision), and an exam/MCQ
ask (R10). It also locks the S3 live-assessment guard: assessment open =>
integrity refusal, assessment closed => normal teaching unchanged.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
import yaml

from ai.moodle_bank import (
    load_c3,
    load_c4_drive,
    load_c4_files,
    load_c5_youtube,
    load_extra,
)
from ai.moodle_host import (
    door_answer,
    page_context_from_snapshot,
    prepare_ask,
    snapshot_from_page_context,
)
from ai.moodle_integrity import integrity_answer, live_assessment_open
from ai.moodle_page import _course_headline
from ai.moodle_refusals import answer_for

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "conformance-13.yaml").read_text(encoding="utf-8"))
_COURSES = yaml.safe_load((_PACK / "courses.yaml").read_text(encoding="utf-8"))
_INFO = {row["shortname"]: row for row in _COURSES["enabled_courses"]}
_OUTLINE_CAP = 12


def _bank(shortname: str) -> dict[str, dict]:
    return {
        **load_c3(shortname),
        **load_c4_files(shortname),
        **load_c4_drive(shortname),
        **load_c5_youtube(shortname),
        **load_extra(shortname),
    }


def _sections(shortname: str) -> list[dict]:
    seen: dict[int, str] = {}
    path = _PACK / "bank" / "course-meat-13" / f"{shortname}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        row = json.loads(line)
        number = row.get("sectionnum")
        if number is None:
            continue
        seen.setdefault(int(number), str(row.get("section") or ""))
    return [
        {"number": number, "name": name, "visible": True}
        for number, name in sorted(seen.items())
    ]


def _page(shortname: str) -> dict:
    info = _INFO[shortname]
    snapshot = {
        "audience": "staff",
        "enrolled": True,
        "course": {
            "id": 1,
            "shortname": shortname,
            "fullname": info["fullname"],
            "visible_to_user": True,
        },
        "sections": _sections(shortname),
    }
    return snapshot_from_page_context(
        page_context_from_snapshot({"audience": "staff"}, snapshot)
    )


def _passage(reply: str) -> tuple[str, str]:
    lines = reply.splitlines()
    return lines[1], lines[2]


def _verbatim(span: str) -> str:
    """The cited span with the truncation marker removed.

    The lecture door caps long passages with a trailing ellipsis (locked by
    test_moodle_topic); the text before the marker is an exact substring.
    """
    return span.rstrip("… ").rstrip()


def _spans_after(reply: str, label: str) -> list[str]:
    started = False
    spans: list[str] = []
    for line in reply.splitlines():
        if line.startswith(label):
            started = True
            continue
        if started and line.startswith("- "):
            spans.append(line[2:])
    return spans


@pytest.mark.parametrize("shortname", list(_GOLD["courses"]))
def test_course_conformance_doors(shortname: str):
    plan = _GOLD["courses"][shortname]
    term = str(plan["topic"])
    restored = _page(shortname)
    bank = _bank(shortname)

    # (1) identity and greeting stay on this course.
    assert door_answer("who are you", restored) == _GOLD["identity"]
    greet = door_answer("hi", restored)
    assert greet is not None and greet.startswith(_GOLD["greet_prefix"])
    assert shortname in greet

    # (2) course-about cites the study guide when the bank has one, and is a
    #     capped outline, never a 40-section dump.
    about = door_answer(_GOLD["about_ask"], restored)
    assert about is not None
    headline = _course_headline(restored["course"])
    assert about.splitlines()[0] == headline
    bullets = [line for line in about.splitlines() if line.startswith("- ")]
    assert 1 <= len(bullets) <= _OUTLINE_CAP
    guides = [
        row["id"]
        for row in bank.values()
        if "study guide" in str(row.get("name") or "").casefold()
    ]
    if guides:
        assert any(pid in about for pid in guides), shortname
    assert "Current page block" not in about

    # (3) "tell me about lecture N" cites that lecture with a verbatim span.
    lecture = door_answer(f"tell me about lecture {int(plan['lecture'])}", restored)
    assert lecture is not None and _GOLD["lecture_miss"] not in lecture
    head = lecture.splitlines()[0]
    assert f"Section {int(plan['lecture'])}:" in head or f"L{int(plan['lecture'])}" in head
    pid, span = _passage(lecture)
    cited = _verbatim(span)
    assert pid in bank and cited and cited in str(bank[pid]["text"])

    # (4) a real body-only topic term cites a verbatim span from this course.
    topic = door_answer(f"what is {term}", restored)
    assert topic is not None and _GOLD["curriculum_miss"] not in topic
    pid, span = _passage(topic)
    assert pid in bank
    assert term.casefold() in span.casefold()
    assert span in str(bank[pid]["text"])
    assert all(term.casefold() not in str(row.get("name") or "").casefold() for row in bank.values())

    # (5) explain caps at three verbatim spans from one selected passage.
    explain = door_answer(f"explain {term}", restored)
    assert explain is not None and _GOLD["curriculum_miss"] not in explain
    labels = [line for line in explain.splitlines() if line.startswith("Verbatim spans from ")]
    assert len(labels) == 1
    explain_pid = labels[0].removeprefix("Verbatim spans from ").rstrip(":")
    assert explain_pid in bank
    spans = _spans_after(explain, "Verbatim spans from ")
    assert 1 <= len(spans) <= 3
    for span in spans:
        assert span in str(bank[explain_pid]["text"])

    # (6) quiz cloze answers are verbatim pack spans and contain the topic.
    quiz = door_answer(f"quiz me on {term}", restored)
    assert quiz is not None and _GOLD["curriculum_miss"] not in quiz
    answers = [
        line.removeprefix("Answer: ")
        for line in quiz.splitlines()
        if line.startswith("Answer: ")
    ]
    assert 1 <= len(answers) <= 3
    for answer in answers:
        assert term.casefold() in answer.casefold()
        assert any(answer in str(row.get("text") or "") for row in bank.values())
    questions = [line for line in quiz.splitlines() if line and "____" in line]
    assert len(questions) == len(answers)

    # (7) the same term on another listed course refuses; it never imports a fact.
    other = str(plan["other_course"])
    other_bank = _bank(other)
    assert all(
        term.casefold() not in str(row.get("text") or "").casefold()
        for row in other_bank.values()
    )
    refused = door_answer(f"what is {term}", _page(other))
    assert refused == _GOLD["curriculum_miss"]
    assert shortname not in (refused or "")


def test_clinical_advice_is_a_fixed_refusal_not_a_model_decision():
    case = _GOLD["clinical"]
    snapshot = {
        "audience": "staff",
        "courseid": 74,
        "enrolled": True,
        **_page("MED520"),
    }
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": case["message"],
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 3,
        }
    )
    assert decision.refusal == case["kind"]
    assert decision.chat is None
    assert decision.answer == answer_for(case["kind"])
    assert "MED520" not in (decision.answer or "")


def test_exam_question_ask_is_refused_r10():
    case = _GOLD["exam"]
    snapshot = {"audience": "staff", "courseid": 74, "enrolled": True, **_page("MED520")}
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": case["message"],
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 4,
        }
    )
    assert decision.refusal == case["kind"]
    assert decision.chat is None
    assert decision.answer == answer_for(case["kind"])


# ---------------------------------------------------------------------------
# S3 — live-assessment guard.
# ---------------------------------------------------------------------------

def _assessable(**extra) -> dict:
    snapshot = {
        "audience": "staff",
        "enrolled": True,
        "course": {
            "id": 74,
            "shortname": "MED520",
            "fullname": "Dermatology",
            "visible_to_user": True,
        },
        "sections": [{"number": 4, "name": "alopecia", "visible": True}],
    }
    snapshot.update(extra)
    return snapshot


@pytest.mark.parametrize("module", ["quiz", "qbank", "lesson"])
def test_open_assessment_module_refuses(module: str):
    snapshot = _assessable(
        activity={"name": "Final exam", "cmid": 9, "module": module, "section": 4}
    )
    assert live_assessment_open(snapshot) is True
    answer = door_answer("hi", snapshot)
    assert answer == integrity_answer()
    assert door_answer("what is alopecia", snapshot) == integrity_answer()
    # Never leaks the exam or the course content into the context.
    context = page_context_from_snapshot({}, snapshot)
    assert "Final exam" not in context
    assert "alopecia" not in context.casefold()
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "what is alopecia",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 5,
        }
    )
    assert decision.refusal == "live_assessment"
    assert decision.chat is None
    assert decision.answer == integrity_answer()


def test_active_signed_timing_window_refuses():
    now = int(time.time())
    snapshot = _assessable(assessment_window={"opens": now - 60, "closes": now + 60})
    assert live_assessment_open(snapshot, now=now) is True
    assert door_answer("what is alopecia", snapshot) == integrity_answer()
    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "what is this course about",
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 74, "assessment_open": True},
            "moodle_user_id": 6,
        }
    )
    assert decision.refusal == "live_assessment"
    assert decision.chat is None


def test_assessment_closed_is_normal_teaching_unchanged():
    now = int(time.time())
    closed = _assessable(assessment_window={"opens": now - 600, "closes": now - 300})
    assert live_assessment_open(closed, now=now) is False
    greet = door_answer("hi", closed)
    assert greet is not None and greet.startswith(_GOLD["greet_prefix"])
    assert _GOLD["curriculum_miss"] not in greet

    resource = _assessable(
        activity={"name": "alopecia.pdf", "cmid": 1111, "module": "resource", "section": 4}
    )
    assert live_assessment_open(resource) is False
    assert door_answer("hi", resource) == greet

    decision = prepare_ask(
        {
            "pulse_mode": "ask",
            "message": "what is this course about",
            "snapshot": closed,
            "host_context": {"audience": "staff", "courseid": 74},
            "moodle_user_id": 7,
        }
    )
    assert decision.refusal is None


def test_integrity_answer_is_pack_sentence_and_names_nothing():
    snapshot = _assessable(
        activity={"name": "SECRET EXAM TITLE", "cmid": 9, "module": "quiz", "section": 4}
    )
    answer = door_answer("hi", snapshot)
    assert answer == integrity_answer()
    assert "SECRET" not in answer
    assert "MED520" not in answer
    assert "Dermatology" not in answer


def test_open_activity_module_survives_the_page_round_trip():
    snapshot = _assessable(
        activity={"name": "alopecia.pdf", "cmid": 1111, "module": "resource", "section": 4}
    )
    restored = snapshot_from_page_context(page_context_from_snapshot({}, snapshot))
    assert restored["activity"]["module"] == "resource"
    assert live_assessment_open(restored) is False
