"""Greeting on a listed Pulse course is a door, not a model tour."""
from pathlib import Path

import yaml

from ai.moodle_host import COURSE_LIST_ANSWERS, door_answer, page_context_from_snapshot, prepare_ask, snapshot_from_page_context
from ai.moodle_page import _topic_from_message, greet_answer, is_greet_ask

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GREET = _PACK / "greet_asks.yaml"
_MISS = "This is not in this course."
GREET_NMD3101 = (
    "Hi. This course is NMD3101: priniciples of infection (staff view).\n"
    "Pulse can answer from this course's lectures and files."
)
_FORBIDDEN = (
    "page",
    "exams",
    "weeks",
    "quiz",
    "Open My",
    "Current page block",
)


def _page(snapshot: dict) -> dict:
    return snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))


def _nmd3101_home(*, fullname: str) -> dict:
    return {
        "audience": "staff",
        "courseid": 25,
        "enrolled": True,
        "course": {
            "id": 25,
            "shortname": "NMD3101",
            "fullname": fullname,
            "visible_to_user": True,
        },
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }


def _assert_clean_greet(answer: str) -> None:
    folded = answer.casefold()
    for needle in _FORBIDDEN:
        assert needle.casefold() not in folded, needle
    assert "NMD3101: NMD3101:" not in answer


def test_greet_pack_owns_the_phrases():
    pack = yaml.safe_load(_GREET.read_text(encoding="utf-8"))
    phrases = [str(p).casefold() for p in (pack.get("phrases") or [])]
    for phrase in ("hi", "hello", "hey", "good morning"):
        assert phrase in phrases
    assert pack["hello"]
    assert pack["grounding"]
    grounding = pack["grounding"].casefold()
    for needle in ("page", "exam", "week"):
        assert needle not in grounding, needle


def test_hi_on_nmd3101_is_the_greet_door():
    snapshot = _nmd3101_home(fullname="NMD3101: priniciples of infection")
    restored = _page(snapshot)
    assert is_greet_ask("hi")
    assert _topic_from_message("hi") is None
    answer = door_answer("hi", restored)
    assert answer == GREET_NMD3101
    assert greet_answer("hi", restored) == GREET_NMD3101
    assert "NMD3101" in answer
    assert "priniciples of infection" in answer
    assert "staff view" in answer
    _assert_clean_greet(answer)


def test_hi_uses_snapshot_fullname_without_doubling():
    restored = _page(_nmd3101_home(fullname="priniciples of infection"))
    answer = door_answer("hi", restored)
    assert answer == GREET_NMD3101
    _assert_clean_greet(answer)


def test_hi_does_not_reach_the_model():
    snapshot = _nmd3101_home(fullname="NMD3101: priniciples of infection")
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "hi",
        "snapshot": snapshot,
        "host_context": {"audience": "staff", "courseid": 25},
        "moodle_user_id": 7,
    })
    assert decision.chat is None
    assert decision.refusal is None
    assert decision.answer == GREET_NMD3101


def test_hi_is_not_a_topic_miss():
    restored = _page(_nmd3101_home(fullname="priniciples of infection"))
    answer = door_answer("hi", restored)
    assert answer != _MISS
    assert _MISS not in (answer or "")


def test_which_course_stays_identity_without_hi():
    restored = _page(_nmd3101_home(fullname="priniciples of infection"))
    answer = door_answer("which course", restored)
    assert answer == "This course is NMD3101: priniciples of infection."
    assert "Hi." not in (answer or "")
    assert "lectures and files" not in (answer or "")


def test_hi_on_pulse_off_is_the_list_miss():
    snapshot = {
        "audience": "staff",
        "courseid": 25,
        "block": "course_list",
        "course": {"id": 25, "visible_to_user": False},
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "hi",
        "snapshot": snapshot,
        "host_context": {"audience": "staff", "courseid": 25},
        "moodle_user_id": 7,
    })
    assert decision.chat is None
    assert decision.refusal == "course_list"
    assert decision.answer == COURSE_LIST_ANSWERS["course_list"]
    assert (decision.answer or "").startswith("This is not on the course list.")
    assert "NMD3101" not in (decision.answer or "")
    assert "priniciples" not in (decision.answer or "")
