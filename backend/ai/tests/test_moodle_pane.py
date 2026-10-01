"""The pane answers section, lecture, and fact questions from the page block."""
from pathlib import Path

import yaml

from ai.moodle_host import door_answer, page_context_from_snapshot, prepare_ask, snapshot_from_page_context
from ai.moodle_page import lecture_answer, section_answer

_ROOT = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold"
_COURSE_ASKS = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "course_asks.yaml"


def _page(snapshot: dict) -> dict:
    return snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))


def test_section_questions_match_the_door():
    gold = yaml.safe_load((_ROOT / "l1.yaml").read_text(encoding="utf-8"))
    snapshot = {
        "course": {"shortname": gold["course"]["shortname"], "fullname": gold["course"]["fullname"], "visible_to_user": True},
        "sections": gold["sections"],
    }
    restored = _page(snapshot)
    assert len(gold["asks"]) >= 12
    matched = 0
    for message in gold["asks"]:
        expected = section_answer(message, snapshot)
        got = door_answer(message, restored)
        if expected and got == expected:
            matched += 1
        assert gold["foreign_title"] not in (got or "")
    assert matched >= 11


def test_lecture_questions_name_the_open_activity():
    gold = yaml.safe_load((_ROOT / "l2.yaml").read_text(encoding="utf-8"))
    for activity in gold["activities"]:
        snapshot = {
            "course": {"shortname": "NMD1103", "fullname": "Clinical Skills 1", "visible_to_user": True},
            "activity": activity,
            "sections": [{"number": 1, "name": "Airway", "visible": True}],
        }
        restored = _page(snapshot)
        for message in gold["asks"]:
            assert door_answer(message, restored) == lecture_answer(message, snapshot)


def test_which_course_names_the_open_course():
    snapshot = {
        "course": {"shortname": "NMD3101", "fullname": "Principles of Infection", "visible_to_user": True},
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    answer = door_answer("which course", _page(snapshot))
    assert answer == "This course is NMD3101: Principles of Infection."
    assert not answer.startswith("Hi.")
    assert "Sections on this page" not in answer
    assert "Open My" not in answer
    assert "Plan" not in answer
    assert "Current page block" not in answer


def test_course_fullname_that_already_has_shortname_is_not_doubled():
    snapshot = {
        "course": {
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    answer = door_answer("which course", _page(snapshot))
    assert answer == "This course is NMD1000: Introduction to Medical School."
    assert "NMD1000: NMD1000:" not in answer


def test_course_about_is_grounded_not_a_section_dump():
    pack = yaml.safe_load(_COURSE_ASKS.read_text(encoding="utf-8"))
    sections = [{"number": i, "name": f"Topic {i}", "visible": True} for i in range(20)]
    sections[19] = {"number": 19, "name": "L10: Terminology1", "visible": True}
    snapshot = {
        "course": {
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": sections,
    }
    restored = _page(snapshot)
    assert pack["asks"]
    for message in pack["asks"]:
        got = door_answer(message, restored)
        assert got
        assert "NMD1000: NMD1000:" not in got
        assert "Current page block" not in got
        assert "ILO" not in got
        assert "syllabus" not in got.casefold()
        if "about" in message.casefold():
            assert got.startswith("This course is NMD1000: Introduction to Medical School.")
            assert "Listed weeks and topics on this page include:" in got
            assert "Topic 0" in got
            assert got.count("\n- ") <= int(pack["outline_cap"])
            assert "…and" in got
            assert pack["description_miss"] not in got
            # Course-about cites a study-guide overview — never lecture 10.
            assert "NMD1000:file:1252:NMD1000 Study guide. 26-27.pdf" in got
            assert "All the needed details of the course" in got
            assert "1278" not in got
            assert "Terminology 1" not in got
            assert "MEDICAL TERMINOLOGY" not in got
            assert len(got.splitlines()) < 30
        else:
            assert got == "This course is NMD1000: Introduction to Medical School."
            assert "Sections on this page" not in got
            assert "Listed weeks" not in got


def test_lecture_ten_cites_the_matching_activity_not_the_model():
    snapshot = {
        "course": {
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [
            {"number": 0, "name": "General", "visible": True},
            {"number": 19, "name": "L10: Terminology1", "visible": True},
        ],
    }
    restored = _page(snapshot)
    for message in (
        "tell me more about lecture 10",
        "lecture 10",
        "L10",
        "tell me more about L10",
    ):
        got = door_answer(message, restored)
        assert got is not None
        assert "Section 19: L10: Terminology1." in got
        assert "NMD1000:file:1278:Terminology 1.pdf" in got
        assert "MEDICAL TERMINOLOGY 1" in got
        assert "only lists the title" not in got.casefold()
        assert "according to the handout" not in message.casefold()
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "tell me more about lecture 10",
        "snapshot": {
            "audience": "staff",
            "courseid": 32,
            "enrolled": True,
            **snapshot,
            "course": {**snapshot["course"], "id": 32},
        },
        "host_context": {"audience": "staff", "courseid": 32},
        "moodle_user_id": 7,
    })
    assert decision.chat is None
    assert "1278" in (decision.answer or "")


def test_course_identity_asks_do_not_reach_the_model():
    pack = yaml.safe_load(_COURSE_ASKS.read_text(encoding="utf-8"))
    snapshot = {
        "audience": "staff",
        "courseid": 32,
        "enrolled": True,
        "course": {
            "id": 32,
            "shortname": "NMD1000",
            "fullname": "NMD1000: Introduction to Medical School",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    for message in pack["asks"]:
        decision = prepare_ask({
            "pulse_mode": "ask",
            "message": message,
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 32},
            "moodle_user_id": 7,
        })
        assert decision.chat is None
        assert decision.refusal is None
        assert "NMD1000" in (decision.answer or "")
        assert "Introduction to Medical School" in (decision.answer or "")
        assert "Current page block" not in (decision.answer or "")
        if "about" not in message.casefold():
            assert decision.answer == "This course is NMD1000: Introduction to Medical School."


def test_who_are_you_stays_on_this_page():
    snapshot = {
        "course": {"shortname": "NMD1103", "fullname": "Clinical Skills 1", "visible_to_user": True},
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    answer = door_answer("who are you ?", _page(snapshot))
    assert answer == (
        "I am Pulse for this course. I answer from this course's lectures and files."
    )
    assert "Open My" not in answer
    assert "Plan" not in answer


def test_a_greeting_is_a_door_answer():
    snapshot = {
        "course": {"shortname": "NMD1103", "fullname": "Clinical Skills 1", "visible_to_user": True},
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    answer = door_answer("hello there", _page(snapshot))
    assert answer == (
        "Hi. This course is NMD1103: Clinical Skills 1 (staff view).\n"
        "Pulse can answer from this course's lectures and files."
    )
    folded = answer.casefold()
    for needle in ("page", "weeks", "exams"):
        assert needle not in folded, needle
    assert "Open My" not in answer
    assert "Current page block" not in answer
    assert "NMD1103: NMD1103:" not in answer


def test_hi_on_nmd3101_names_the_course_not_the_page():
    snapshot = {
        "audience": "staff",
        "course": {
            "id": 25,
            "shortname": "NMD3101",
            "fullname": "priniciples of infection",
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    answer = door_answer("hi", _page(snapshot))
    assert answer == (
        "Hi. This course is NMD3101: priniciples of infection (staff view).\n"
        "Pulse can answer from this course's lectures and files."
    )
    folded = answer.casefold()
    for needle in ("page", "weeks", "exams"):
        assert needle not in folded, needle
    assert "This is not in this course." not in answer
