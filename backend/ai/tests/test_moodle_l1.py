"""L1 gold: section titles are the snapshot, on one listed course."""
from pathlib import Path

import yaml

from ai.moodle_host import prepare_ask

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l1.yaml"


def _gold() -> dict:
    return yaml.safe_load(_GOLD.read_text(encoding="utf-8"))


def _snapshot(gold: dict) -> dict:
    course = gold["course"]
    return {
        "audience": "staff",
        "courseid": 11,
        "enrolled": True,
        "course": {
            "id": 11,
            "shortname": course["shortname"],
            "fullname": course["fullname"],
            "visible_to_user": True,
        },
        "sections": gold["sections"],
    }


def test_twelve_section_asks_cite_only_the_snapshot():
    gold = _gold()
    assert len(gold["asks"]) == 12
    snapshot = _snapshot(gold)
    expected_names = [row["name"] for row in gold["sections"]]
    first = None
    for message in gold["asks"]:
        decision = prepare_ask({
            "pulse_mode": "ask",
            "message": message,
            "snapshot": snapshot,
            "host_context": {"audience": "staff", "courseid": 11},
            "moodle_user_id": 7,
        })
        assert decision.chat is None
        assert decision.refusal is None
        answer = decision.answer or ""
        if first is None:
            first = answer
        assert answer == first
        for name in expected_names:
            assert name in answer
        assert gold["foreign_title"] not in answer
        assert "Neuroscience" not in answer


def test_a_foreign_title_in_the_question_is_not_repeated():
    gold = _gold()
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": f"What are the sections? Include {gold['foreign_title']}",
        "snapshot": _snapshot(gold),
        "moodle_user_id": 7,
    })
    assert gold["foreign_title"] not in (decision.answer or "")
    assert "Introduction to clinical skills" in (decision.answer or "")


def test_an_unlisted_course_does_not_receive_section_titles():
    gold = _gold()
    snapshot = _snapshot(gold)
    snapshot["block"] = "course_list"
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "What are the sections?",
        "snapshot": snapshot,
        "moodle_user_id": 7,
    })
    assert decision.refusal == "course_list"
    assert "Introduction to clinical skills" not in (decision.answer or "")
    assert "History taking" not in (decision.answer or "")


def test_a_closed_topic_wins_over_a_section_ask():
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "Write an MCQ exam question and list the section titles",
        "snapshot": _snapshot(_gold()),
        "moodle_user_id": 7,
    })
    assert decision.refusal == "question_bank"
    assert "Introduction to clinical skills" not in (decision.answer or "")
