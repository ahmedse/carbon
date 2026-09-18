"""Medicine OSCE hybrid pack — quantitative checklist scoring."""
from __future__ import annotations

import pytest

from gradevance.models import Assignment, Submission
from gradevance.services.packs import find_profile_file_for_id, load_profile
from gradevance.services.pipeline import FormativePipelineService, score_rubric


OSCE_SAMPLE = """
I introduced myself and explained the procedure, obtained consent, and washed hands.
Patient was positioned supine with one pillow. I exposed the abdomen from xiphisternum
to symphysis. On general appearance the patient looked uncomfortable with RIF pain.
Abdominal contour was flat; no scars or masses; skin normal. I asked about pain first,
started away from the tender area, performed light palpation and deep palpation of all
four quadrants. Right iliac fossa tenderness identified near McBurney point; guarding
and rebound tenderness present; Rovsing sign negative. Percussion was tympanic;
bowel sounds present and normal on auscultation. Differential includes appendicitis.
On reflection I will slow down consent next time and check for hernia more carefully.
"""


def test_osce_profile_loads_hybrid():
    loaded = load_profile(find_profile_file_for_id("medicine_osce_abdominal", 1))
    assert loaded.rubric is not None
    assert loaded.rubric.rubric["mode"] == "hybrid"
    assert loaded.device is not None


def test_osce_checklist_scores_keywords():
    loaded = load_profile(find_profile_file_for_id("medicine_osce_abdominal", 1))
    evaluations, advisory, coaching = score_rubric(
        loaded,
        {"stages_present": ["what", "so_what", "now_what"], "sg_range": 2, "transitions": 2},
        word_count=180,
        submission_text=OSCE_SAMPLE,
    )
    quant = [e for e in evaluations if e["evidence_bindings"].get("scoring") == "quantitative"]
    assert len(quant) >= 3
    assert any((e.get("score_0_100") or 0) > 50 for e in quant)
    assert coaching["watermark"] == "advisory"


@pytest.mark.django_db
def test_osce_pipeline_end_to_end():
    asg = Assignment.objects.create(
        title="OSCE abdominal",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="medicine_osce_abdominal",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text=OSCE_SAMPLE)
    run = FormativePipelineService().analyze_submission(sub)
    assert run.rubric_scores.filter(score_0_100__isnull=False).exists()
    assert run.coaching.get("watermark") == "advisory"
    coded = sum(seg.codes.count() for seg in run.segments.all())
    assert coded >= 1
