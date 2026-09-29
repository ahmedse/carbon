"""C6: a fact question cites the open activity or refuses."""
from pathlib import Path

import yaml

from ai.moodle_bank import cite_open_activity, load_c3, load_c4_files
from ai.moodle_host import page_context_from_snapshot, prepare_ask, snapshot_from_page_context
from ai.moodle_page import fact_answer

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c6.yaml"


def _ask(activity: int, quote: str, gold: dict, extra: dict | None = None):
    bank_note = extra or {}
    snapshot = {
        "course": {"shortname": gold["course"], "fullname": "Clinical Skills 1", "visible_to_user": True},
        "activity": {"cmid": activity, "name": "Handout", "module": "resource", "section": 1},
        "audience": "staff",
    }
    snapshot.update(bank_note)
    return prepare_ask(
        {
            "pulse_mode": "ask",
            "message": f"{gold['ask']}, {quote}",
            "snapshot": snapshot,
            "host_context": {"audience": "staff"},
        }
    )


def test_the_page_block_keeps_the_activity_id_for_the_pane():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    case = gold["hits"][0]
    snapshot = {
        "course": {
            "shortname": gold["course"],
            "fullname": "Clinical Skills 1",
            "visible_to_user": True,
            "id": 12,
        },
        "activity": {"cmid": case["activity"], "name": "Handout", "module": "resource", "section": 3},
        "sections": [{"number": 3, "name": "Hand Hygiene", "visible": True}],
    }
    restored = snapshot_from_page_context(page_context_from_snapshot({"audience": "staff"}, snapshot))
    assert restored["course"]["shortname"] == gold["course"]
    assert restored["activity"]["cmid"] == case["activity"]
    answer = fact_answer(f"{gold['ask']}, {case['quote']}", restored)
    assert answer.startswith(case["passage"] + "\n")


def test_four_quotes_cite_the_open_passage():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    stored = {**load_c3(gold["course"]), **load_c4_files(gold["course"])}
    assert len(gold["hits"]) == 4
    for case in gold["hits"]:
        assert case["quote"] in stored[case["passage"]]["text"]
        decision = _ask(case["activity"], case["quote"], gold)
        assert decision.chat is None
        assert decision.answer.startswith(case["passage"] + "\n")
        assert case["quote"] in decision.answer
        for other in gold["hits"]:
            if other["passage"] != case["passage"]:
                assert other["passage"] not in decision.answer


def test_four_quotes_outside_the_open_activity_are_the_lecture_miss():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    assert len(gold["misses"]) == 4
    for case in gold["misses"]:
        decision = _ask(case["activity"], case["quote"], gold)
        assert decision.answer == gold["miss"]
        assert decision.chat is None
        if case.get("absent"):
            assert case["absent"] not in decision.answer
        assert "AHFAD-FACT-8841" not in (decision.answer or "")
    planted = {**load_c3(gold["course"]), **load_c4_files(gold["course"])}
    planted["AHFAD-PED:page:1009"] = {
        "id": "AHFAD-PED:page:1009",
        "course": "AHFAD-PED",
        "activity_id": 1009,
        "world": "ahfad",
        "text": "AHFAD-FACT-8841",
    }
    answer = cite_open_activity(
        f"{gold['ask']}, AHFAD-FACT-8841",
        planted,
        course=gold["course"],
        activity_id=1009,
        world=gold["world"],
    )
    assert answer == gold["miss"]
    assert "AHFAD-PED:page:1009" not in answer
