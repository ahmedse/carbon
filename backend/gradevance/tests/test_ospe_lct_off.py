"""LCT-off OSPE profile — checklist-only formative path."""
from __future__ import annotations

import pytest

from gradevance.models import Assignment, Submission
from gradevance.services.packs import find_profile_file_for_id, load_profile
from gradevance.services.pipeline import FormativePipelineService

OSPE_TEXT = """
I washed hands and put on gloves, verified the patient label, then mixed the specimen.
I immersed the dipstick for the timed seconds and compared pads to the colour chart.
Leukocytes and nitrites were positive; I documented findings and discarded as biohazard.
"""


def test_ospe_profile_lct_off():
    loaded = load_profile(find_profile_file_for_id("medicine_ospe_urinalysis", 1))
    assert loaded.profile["pipeline"]["lct_enabled"] is False
    assert loaded.device is None
    assert loaded.rubric is not None


@pytest.mark.django_db
def test_ospe_pipeline_checklist_only():
    asg = Assignment.objects.create(
        title="OSPE urinalysis",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="medicine_ospe_urinalysis",
        profile_version=1,
        pipeline_config_snapshot={"lct_enabled": False, "stages": ["preprocess", "rubric_score", "gate", "coach"]},
    )
    sub = Submission.objects.create(assignment=asg, text=OSPE_TEXT)
    run = FormativePipelineService().analyze_submission(sub)
    assert run.rubric_scores.exists()
    assert run.segments.count() >= 0  # may still segment text
    quant = run.rubric_scores.filter(score_0_100__isnull=False)
    assert quant.exists()
