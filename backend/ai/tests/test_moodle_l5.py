"""L5 stays closed while R11 and R12 have no frozen cases."""
from pathlib import Path

import yaml

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l5.yaml"
_C6 = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c6.yaml"


def test_l5_stays_not_passable_while_r11_and_r12_are_empty():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    c6 = yaml.safe_load(_C6.read_text(encoding="utf-8"))
    bar = gold["curriculum_benchmark"]
    assert gold["status"] == "not_passable"
    assert bar["sample_size"] == 100
    assert bar["min_passage_cite"] == 95
    assert bar["max_extra_fact"] == 2
    assert bar["per"] == "shortname"
    assert bar["notice_courses"] == 13
    assert bar["at_bar"] == 13
    assert bar["handout_frozen_n"] == len(c6["hits"]) + len(c6["misses"]) == 8
    assert bar["short"] == {}
    assert "MED5310" in gold["enabled_courses_gold_covers"]
    assert len(gold["enabled_courses_gold_covers"]) == 13
    assert gold["r11_draft"]["frozen_n"] == 0
    assert gold["r12_same_lecture_two_students"]["frozen_n"] == 0
    assert gold["r12_same_lecture_two_students"]["blocked_by"] == "student_cohorts_empty"
