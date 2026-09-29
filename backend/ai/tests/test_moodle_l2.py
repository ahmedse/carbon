"""L2 gold: this lecture cites the open activity and not the other one."""
from pathlib import Path

import yaml

from ai.moodle_host import prepare_ask

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l2.yaml"


def _gold() -> dict:
    return yaml.safe_load(_GOLD.read_text(encoding="utf-8"))


def _snapshot(activity: dict) -> dict:
    return {
        "audience": "staff",
        "courseid": 11,
        "enrolled": True,
        "course": {
            "id": 11,
            "shortname": "NMD1103",
            "fullname": "Clinical Skills 1",
            "visible_to_user": True,
        },
        "sections": [{"number": activity["section"], "name": "Week", "visible": True}],
        "activity": activity,
    }


def test_each_open_activity_is_cited_and_the_other_is_not():
    gold = _gold()
    assert len(gold["activities"]) == 2
    assert len(gold["asks"]) == 2
    names = [row["name"] for row in gold["activities"]]
    for activity in gold["activities"]:
        for message in gold["asks"]:
            decision = prepare_ask({
                "pulse_mode": "ask",
                "message": message,
                "snapshot": _snapshot(activity),
                "moodle_user_id": 7,
            })
            answer = decision.answer or ""
            assert decision.chat is None
            assert activity["name"] in answer
            for other in names:
                if other != activity["name"]:
                    assert other not in answer


def test_a_page_with_no_activity_does_not_invent_a_lecture():
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "What is this lecture?",
        "snapshot": {
            "course": {"id": 11, "visible_to_user": True, "fullname": "Clinical Skills 1"},
            "sections": [],
        },
        "moodle_user_id": 7,
    })
    assert decision.answer == "This page has no lecture to cite."
    assert "Clinical Skills" not in decision.answer
