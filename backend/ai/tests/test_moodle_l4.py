"""L4: an MBBS turn does not return another world's passage."""
from pathlib import Path

import yaml

from ai.moodle_bank import (
    cite_for_turn,
    listed_shortnames,
    load_c3,
    load_c4_files,
    passages_if_listed,
    select_for_turn,
)
from ai.moodle_host import COURSE_LIST_ANSWERS

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l4.yaml"


def _bank() -> dict:
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    bank = {**load_c3("NMD1103"), **load_c4_files("NMD1103")}
    assert gold["marker"] not in "\n".join(row["text"] for row in bank.values())
    for case in gold["mbbs"]:
        pid = f"{case['poison_course']}:poison:{case['activity']}"
        bank[pid] = {
            "id": pid,
            "course": case["poison_course"],
            "kind": "page",
            "activity_id": case["activity"],
            "world": case["poison_world"],
            "text": gold["marker"],
            "name": "poison",
        }
    control = gold["control"]
    bank["NMD1103:page:7777"] = {
        "id": "NMD1103:page:7777",
        "course": control["course"],
        "kind": "page",
        "activity_id": control["activity"],
        "world": control["world"],
        "text": gold["marker"],
        "name": "control",
    }
    for shortname in gold["unlisted"]:
        pid = f"{shortname}:page:1"
        bank[pid] = {
            "id": pid,
            "course": shortname,
            "kind": "page",
            "activity_id": 1,
            "world": gold["world"],
            "text": gold["marker"],
            "name": shortname,
        }
    return bank


def test_mbbs_turn_drops_the_other_world_and_keeps_its_own_marker():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    bank = _bank()
    assert len(gold["mbbs"]) == 4
    for case in gold["mbbs"]:
        rows = select_for_turn(bank, course="NMD1103", activity_id=case["activity"], world=gold["world"])
        ids = [row["id"] for row in rows]
        assert all(gold["marker"] not in row["text"] for row in rows)
        if case["keep"]:
            assert case["keep"] in ids
        assert gold["marker"] not in cite_for_turn(
            bank, course="NMD1103", activity_id=case["activity"], world=gold["world"]
        )
        if not case["keep"]:
            assert cite_for_turn(
                bank, course="NMD1103", activity_id=case["activity"], world=gold["world"]
            ) == gold["other_world_miss"]
    control = gold["control"]
    kept = select_for_turn(
        bank, course=control["course"], activity_id=control["activity"], world=control["world"]
    )
    assert [row["text"] for row in kept] == [gold["marker"]]


def test_unlisted_courses_contribute_no_passages():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    bank = _bank()
    allowed = listed_shortnames()
    assert len(gold["unlisted"]) == 4
    assert COURSE_LIST_ANSWERS["course_list"].startswith(gold["unlisted_answer"])
    for shortname in gold["unlisted"]:
        assert shortname not in allowed
        assert passages_if_listed(bank, shortname, allowed) == []
