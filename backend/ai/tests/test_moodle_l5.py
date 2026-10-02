"""L5 is frozen passable under the recorded local pilot exception.

See docs/pulse/aast-med/PILOT-EXCEPTION.md. This is NOT a production claim:
K11 (production) stays unmarked; the freeze rests on the local consented pilot.
"""
from pathlib import Path

import yaml

_GOLD = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "l5.yaml"
_C6 = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med" / "gold" / "c6.yaml"


def test_l5_frozen_passable_under_recorded_pilot_exception():
    gold = yaml.safe_load(_GOLD.read_text(encoding="utf-8"))
    c6 = yaml.safe_load(_C6.read_text(encoding="utf-8"))
    bar = gold["curriculum_benchmark"]
    assert gold["status"] == "passable"
    assert bar["sample_size"] == 100
    assert bar["min_passage_cite"] == 95
    assert bar["max_extra_fact"] == 2
    assert bar["per"] == "shortname"
    assert bar["notice_courses"] == 13
    assert bar["at_bar"] == 13
    assert bar["handout_frozen_n"] == len(c6["hits"]) + len(c6["misses"]) == 8
    assert len(bar["short"]) == 13
    assert set(bar["short"]) == set(gold["enabled_courses_gold_covers"])
    for shortname, row in bar["short"].items():
        assert row["items"] >= 100, shortname
        assert row["cited"] >= 95, shortname
        assert row["extra_facts"] <= 2, shortname
        assert row["at_bar"] is True, shortname
    assert "MED5310" in gold["enabled_courses_gold_covers"]
    assert len(gold["enabled_courses_gold_covers"]) == 13
    assert gold["r11_draft"]["frozen_n"] == 4
    assert gold["r12_same_lecture_two_students"]["frozen_n"] == 2

    # Honest history: the freeze rests on the recorded local pilot exception,
    # not on a production cohort.
    pilot = gold["pilot_exception"]
    assert pilot["scope"] == "local dev only"
    assert pilot["cohort"] == "pulse_student_pilot"
    assert pilot["authority"].startswith("platform superuser")
    assert pilot["production"].startswith("not claimed")
    assert gold["r12_same_lecture_two_students"]["exception"] == "docs/pulse/aast-med/PILOT-EXCEPTION.md"
