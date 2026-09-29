"""The pane answers section, lecture, and fact questions from the page block."""
from pathlib import Path

import yaml

from ai.moodle_host import door_answer, page_context_from_snapshot, snapshot_from_page_context
from ai.moodle_page import lecture_answer, section_answer

_ROOT = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold"


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


def test_a_greeting_is_not_a_door_answer():
    snapshot = {
        "course": {"shortname": "NMD1103", "fullname": "Clinical Skills 1", "visible_to_user": True},
        "sections": [{"number": 0, "name": "General", "visible": True}],
    }
    assert door_answer("hello there", _page(snapshot)) is None
