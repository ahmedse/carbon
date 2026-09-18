"""HITL learning loop — ExpertEdit → ProposalMiner."""
from __future__ import annotations

import pytest

from gradevance.models import AnalysisRun, Assignment, ExpertEdit, Proposal, Submission
from gradevance.services.learning import ProposalMiner
from gradevance.services.pipeline import ReviewService


@pytest.mark.django_db
def test_proposal_miner_clusters_lct_edits():
    asg = Assignment.objects.create(
        title="t",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text="hello world " * 20)
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        status=AnalysisRun.STATUS_NEEDS_REVIEW,
    )
    edit = ExpertEdit.objects.create(
        run=run,
        edit_kind=ExpertEdit.KIND_LCT,
        before={"value": "SG+"},
        after={"dimension": "semantic_gravity", "value": "SG--", "numeric": 4},
        rationale="More abstract framing",
    )
    created = ProposalMiner().mine([edit])
    assert len(created) == 1
    assert created[0].kind == "anchor"
    assert created[0].status == Proposal.STATUS_DRAFT
    assert created[0].payload["activation"].startswith("requires_professor")


@pytest.mark.django_db
def test_review_service_mines_on_edit():
    asg = Assignment.objects.create(
        title="t",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text="hello world " * 20)
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        status=AnalysisRun.STATUS_NEEDS_REVIEW,
    )
    ReviewService().apply_edit(
        run=run,
        editor=None,
        edit_kind=ExpertEdit.KIND_RUBRIC,
        before={"band": "C"},
        after={"criterion_id": "task_achievement", "band": "B"},
        rationale="Stronger SO WHAT",
    )
    assert Proposal.objects.filter(kind="rubric_note").exists()
