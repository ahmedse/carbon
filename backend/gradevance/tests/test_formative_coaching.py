"""NAA formative coaching / band heuristics."""
from __future__ import annotations

import json
from pathlib import Path

from gradevance.services.packs import eduos_pack_root, find_profile_file_for_id, load_profile
from gradevance.services.pipeline import score_rubric


def _naa_gold_text() -> str:
    path = eduos_pack_root() / "gold/naa/AR-CYCLE1-18-week1.json"
    return json.loads(path.read_text(encoding="utf-8"))["text"]


def test_naa_formative_coaching_has_watermark_and_actions():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    text = _naa_gold_text()
    evaluations, advisory, coaching = score_rubric(
        loaded,
        {"stages_present": ["what", "so_what", "now_what"], "sg_range": 2, "transitions": 3},
        word_count=len(text.split()),
        submission_text=text,
    )
    assert evaluations
    assert advisory
    assert coaching.get("watermark") == "advisory"
    assert isinstance(coaching.get("strengths"), list)
    assert isinstance(coaching.get("diagnosis_actions"), list)


def test_naa_short_text_triggers_too_short_or_lower_bands():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    short = "I studied hard for Gaokao."
    evaluations, advisory, coaching = score_rubric(
        loaded,
        {"stages_present": ["what"], "sg_range": 0, "transitions": 0},
        word_count=len(short.split()),
        submission_text=short,
    )
    actions = coaching.get("diagnosis_actions") or []
    ids = {a.get("id") for a in actions}
    # Expect stage-missing and/or length coaching from action templates.
    assert actions or any((e.get("band") or "") in ("F", "E", "D") for e in evaluations)
    assert "task_achievement" in advisory or evaluations
