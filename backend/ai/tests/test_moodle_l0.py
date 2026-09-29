"""L0 gold for the Moodle Ask door. Counts come from the pack gold file."""
from pathlib import Path

import yaml

from ai.moodle_host import course_block, page_context_from_snapshot, prepare_ask, prepare_embed
from ai.moodle_refusals import classify

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l0.yaml"
_LISTED = {
    "audience": "staff",
    "courseid": 11,
    "enrolled": True,
    "course": {
        "id": 11,
        "shortname": "NMD1103",
        "fullname": "Clinical Skills 1",
        "visible_to_user": True,
    },
    "sections": [{"number": 1, "name": "Week 1", "visible": True}],
}


def _gold() -> dict:
    return yaml.safe_load(_GOLD.read_text(encoding="utf-8"))


def test_gold_file_has_the_l0_counts():
    gold = _gold()
    assert len(gold["dial"]) == 4
    assert len(gold["course_list"]["empty"]) == 2
    assert len(gold["course_list"]["miss"]) == 4
    assert len(gold["cohort"]["outside"]) == 4
    assert len(gold["cohort"]["students_when_student_list_empty"]) == 2
    assert len(gold["refusals"]) == 8
    assert len(gold["allow"]) == 4


def test_two_plan_and_two_agent_posts_do_not_build_a_chat():
    poisoned = {
        "course": {
            "shortname": "SECRET1103",
            "fullname": "Secret Clinical Skills",
            "visible_to_user": True,
        },
    }
    for row in _gold()["dial"]:
        body = {
            "pulse_mode": row["pulse_mode"],
            "message": row["message"],
            "snapshot": poisoned,
        }
        decision = prepare_ask(body)
        assert decision.error == "ask_only"
        assert decision.status == 403
        assert decision.chat is None
        embed = prepare_embed(body)
        assert embed.error == "ask_only"
        assert embed.status == 403
        assert embed.answer is None
        assert "SECRET1103" not in (embed.answer or "")


def test_closed_topics_refuse_and_page_questions_do_not():
    gold = _gold()
    for row in gold["refusals"]:
        decision = prepare_ask({
            "pulse_mode": "ask",
            "message": row["message"],
            "snapshot": _LISTED,
            "host_context": {"audience": "staff", "courseid": 11},
            "moodle_user_id": 7,
        })
        assert decision.refusal == row["id"]
        assert decision.chat is None
        assert decision.answer
        assert "NMD1103" not in decision.answer
        assert "Clinical Skills" not in decision.answer
    for message in gold["allow"]:
        assert classify(message) is None
        decision = prepare_ask({
            "pulse_mode": "ask",
            "message": message,
            "snapshot": _LISTED,
            "host_context": {"audience": "staff", "courseid": 11},
            "moodle_user_id": 7,
        })
        assert decision.refusal is None
        assert decision.error is None
        if decision.chat is not None:
            assert decision.chat["process_mode"] == "ask"
        else:
            assert decision.answer


def test_paraphrases_outside_the_gold_file_still_refuse():
    samples = [
        ("The dose to give this patient tonight", "clinical_care"),
        ("Please write the essay", "assignment_text"),
        ("I need an MCQ", "question_bank"),
        ("Show the medmentor goals", "mentorship_caseload"),
    ]
    for message, kind in samples:
        assert classify(message) == kind


def test_course_list_block_drops_a_poisoned_name():
    poisoned = {
        "block": "course_list",
        "course": {
            "id": 9,
            "shortname": "SECRET1103",
            "fullname": "Secret Clinical Skills",
            "visible_to_user": True,
        },
        "sections": [{"number": 1, "name": "Hidden week", "visible": True}],
    }
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "What is this course called?",
        "snapshot": poisoned,
        "moodle_user_id": 7,
    })
    assert course_block(poisoned) == "course_list"
    assert decision.chat is None
    assert decision.refusal == "course_list"
    blob = (decision.answer or "") + page_context_from_snapshot({}, poisoned)
    assert "SECRET1103" not in blob
    assert "Secret Clinical" not in blob
    assert "Hidden week" not in blob


def test_engine_does_not_gain_l0_tokens():
    root = Path(__file__).resolve().parents[1] / "engine"
    needles = ("enabled_courses", "course_list_empty", "clinical_care", "medmentor")
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in text, f"{needle} in {path}"
