"""Medicine CBL formative pipeline."""
from __future__ import annotations

import pytest

from gradevance.models import Assignment, Submission
from gradevance.services.packs import find_profile_file_for_id, load_profile
from gradevance.services.pipeline import FormativePipelineService

CBL_SAMPLE = """
The 22-year-old reported migratory pain to the right iliac fossa overnight.
She said the pain started around the belly button and later moved to the right side.
Appendicitis classically progresses from visceral to somatic peritoneal irritation.
Guarding and rebound suggest localised peritonism; Rovsing was negative.
On reflection the case illustrates why early surgical review matters when migratory
pain and localised tenderness coincide.
"""


def test_cbl_profile_loads():
    loaded = load_profile(find_profile_file_for_id("medicine_cbl_appendicitis", 1))
    assert loaded.device is not None
    assert len(loaded.device.anchors) >= 3
    assert loaded.rubric is not None


@pytest.mark.django_db
def test_cbl_pipeline_end_to_end():
    asg = Assignment.objects.create(
        title="CBL appendicitis",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="medicine_cbl_appendicitis",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text=CBL_SAMPLE.strip())
    run = FormativePipelineService().analyze_submission(sub)
    assert run.status in (
        run.STATUS_COMPLETE,
        run.STATUS_NEEDS_REVIEW,
    )
    assert run.segments.exists()
    coded = sum(seg.codes.count() for seg in run.segments.all())
    assert coded >= 1
