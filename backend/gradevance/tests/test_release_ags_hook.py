"""Release summative triggers AGS dry-run when lineitem is on assignment.brief."""
from __future__ import annotations

import pytest
from django.test import override_settings

from accounts.models import User
from gradevance.models import AnalysisRun, Assignment, Submission
from gradevance.services.pipeline import ReviewService


@pytest.mark.django_db(transaction=True)
@override_settings(GRADEVANCE_LTI_AGS_DRY_RUN=True)
def test_release_triggers_ags_dry_run_when_lineitem_set():
    user = User.objects.create_superuser("gv_ags_rel", "ags@test.com", "pass")
    asg = Assignment.objects.create(
        title="Summative",
        mode=Assignment.MODE_SUMMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        brief={"lti": {"ags_lineitem_url": "https://lms.example/lineitems/42"}},
    )
    sub = Submission.objects.create(
        assignment=asg,
        text="x " * 50,
        external_student_key="lti-user-9",
    )
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_NEEDS_REVIEW,
        released=False,
    )
    run = ReviewService().release_summative(run, user)
    run.refresh_from_db()
    assert run.released is True
    ags = (run.run_manifest or {}).get("ags_passback") or {}
    assert ags.get("attempted") is True
    assert ags.get("dry_run") is True
    assert ags.get("ok") is True
    assert "scores" in (ags.get("url") or "")


@pytest.mark.django_db(transaction=True)
@override_settings(GRADEVANCE_LTI_AGS_DRY_RUN=True)
def test_release_skips_ags_without_lineitem():
    user = User.objects.create_superuser("gv_ags_rel2", "ags2@test.com", "pass")
    asg = Assignment.objects.create(
        title="Summative",
        mode=Assignment.MODE_SUMMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        brief={},
    )
    sub = Submission.objects.create(assignment=asg, text="x " * 50)
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_NEEDS_REVIEW,
    )
    run = ReviewService().release_summative(run, user)
    run.refresh_from_db()
    assert (run.run_manifest or {}).get("ags_passback") is None
