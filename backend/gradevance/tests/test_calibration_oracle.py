"""Calibration profile uses gold_oracle coder."""
from __future__ import annotations

import pytest

from gradevance.models import Assignment, Submission
from gradevance.services.packs import find_profile_file_for_id, load_profile
from gradevance.services.pipeline import FormativePipelineService


def test_calibration_profile_pins_gold_oracle():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_calibration", 1))
    assert loaded.profile["mode"] == "calibration"
    assert loaded.profile["pipeline"]["coder"] == "gold_oracle"


@pytest.mark.django_db
def test_calibration_run_uses_gold_oracle_on_held_out_text():
    from gradevance.services.publish import load_held_out_rows

    rows = load_held_out_rows("engines/lct_semantics/naa_reflective_v1")
    text = rows[0]["text"]
    asg = Assignment.objects.create(
        title="calibration",
        mode=Assignment.MODE_CALIBRATION,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_calibration",
        profile_version=1,
        pipeline_config_snapshot={
            "lct_enabled": True,
            "coder": "gold_oracle",
            "stages": ["preprocess", "segment", "code_lct", "profile_wave", "rubric_score", "gate"],
        },
    )
    # Analyze full gold text — segmentation may not match gold offsets, but run must complete.
    sub = Submission.objects.create(assignment=asg, text=text)
    run = FormativePipelineService().analyze_submission(sub)
    assert run.run_manifest.get("coder") == "gold_oracle"
    assert run.segments.exists()
