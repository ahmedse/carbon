"""L5 stays closed until 100 curriculum cases and R11 and R12 are frozen."""
from pathlib import Path

import yaml

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l5.yaml"
_C6 = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c6.yaml"


def test_l5_is_not_passable_on_eight_cases():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    c6 = yaml.safe_load(_C6.read_text(encoding="utf-8"))
    frozen = len(c6["hits"]) + len(c6["misses"])
    bar = gold["curriculum_benchmark"]
    assert gold["status"] == "not_passable"
    assert bar["frozen_n"] == frozen == 8
    assert bar["frozen_n"] < bar["min_passage_cite"]
    assert bar["sample_size"] - bar["frozen_n"] == bar["deferred_n"] == 92
    assert gold["r11_draft"]["frozen_n"] == 0
    assert gold["r12_same_lecture_two_students"]["frozen_n"] == 0
    assert gold["enabled_courses_gold_covers"] == ["NMD1103"]
