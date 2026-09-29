"""L3 gold: one of four reasons, and no other person's name."""
from pathlib import Path

import yaml

from ai.moodle_host import prepare_ask

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l3.yaml"
_REASONS = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "access_reasons.yaml"
_PHRASES = (
    "not enrolled",
    "wrong group",
    "hidden",
    "not on the course list",
)


def test_each_reason_is_used_twice_and_names_nobody_else():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    reasons = yaml.safe_load(_REASONS.read_text(encoding="utf-8"))["reasons"]
    assert len(gold["cases"]) == 8
    counts = {key: 0 for key in reasons}
    person = gold["other_person"]
    for case in gold["cases"]:
        counts[case["access"]] += 1
        decision = prepare_ask({
            "pulse_mode": "ask",
            "message": case["message"],
            "moodle_user_id": 7,
            "snapshot": {
                "access": case["access"],
                "audience": "student",
                "course": {
                    "id": 9,
                    "visible_to_user": case["access"] == "wrong_group",
                    "fullname": person,
                    "shortname": "SECRET",
                },
                "sections": [{"number": 1, "name": person, "visible": False}],
                "activity": {"cmid": 3, "name": person, "module": "page", "section": 1},
            },
        })
        answer = decision.answer or ""
        assert answer == reasons[case["access"]]
        assert person not in answer
        assert "SECRET" not in answer
        phrase = {
            "not_enrolled": "not enrolled",
            "wrong_group": "wrong group",
            "hidden": "hidden",
            "course_list": "not on the course list",
        }[case["access"]]
        assert phrase in answer
        for other in _PHRASES:
            if other != phrase:
                assert other not in answer
    assert counts == {key: 2 for key in reasons}
