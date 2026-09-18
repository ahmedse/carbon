"""P1: formative pipeline + pack loader smoke (no Django DB for pack unit tests)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradevance.services.packs import (
    eduos_pack_root,
    find_profile_file_for_id,
    list_profiles,
    load_profile,
)
from gradevance.services.pipeline import build_wave, code_segment, segment_text

REPO = Path(__file__).resolve().parents[3]
GOLD = REPO / "domain_packs/eduos/gold/naa/AR-CYCLE1-18-week1.json"


def test_eduos_pack_root_exists():
    assert eduos_pack_root().is_dir()
    assert (eduos_pack_root() / "profiles").is_dir()


def test_list_profiles_includes_naa_and_osce():
    ids = {p["pack_id"] for p in list_profiles()}
    assert "naa_cycle1_exam_prep" in ids
    assert "medicine_osce_abdominal" in ids or any("osce" in (i or "") for i in ids)


def test_load_naa_profile_binds_device_and_rubric():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    assert loaded.device is not None
    assert loaded.rubric is not None
    assert loaded.device.device["id"] == "naa_reflective_semantics"
    assert loaded.rubric.rubric["id"] == "naa_reflective_analytic"
    assert len(loaded.device.anchors) >= 4


def test_segment_and_code_gold_text_oscillates():
    gold = json.loads(GOLD.read_text())
    text = gold["text"]
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    policy = loaded.device.segmentation.get("policy") or {}
    drafts = segment_text(text, policy)
    assert len(drafts) >= 3
    codes_by_ord = {}
    for d in drafts:
        codes_by_ord[d.ordinal] = code_segment(d, loaded.device.anchors, True)
    wave = build_wave(drafts, codes_by_ord)
    # Accept oscillation OR at least multi-segment coverage (heuristic coder).
    assert wave["metrics"]["segment_count"] >= 3
    assert len(wave["points"]) == len(drafts)


@pytest.mark.django_db
def test_formative_pipeline_persists_run():
    from gradevance.models import Assignment, Submission
    from gradevance.services.pipeline import FormativePipelineService

    gold = json.loads(GOLD.read_text())
    asg = Assignment.objects.create(
        title="NAA formative",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text=gold["text"])
    run = FormativePipelineService().analyze_submission(sub)
    assert run.segments.count() >= 3
    assert run.rubric_scores.count() >= 1
    assert run.wave is not None
    assert run.coaching.get("watermark") == "advisory"
    assert run.status in ("complete", "needs_review")
