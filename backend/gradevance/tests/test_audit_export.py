import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from gradevance.audit import RunAuditExportView
from gradevance.models import AnalysisRun, Assignment, Submission


@pytest.mark.django_db
def test_audit_export_formative_ok():
    user = User.objects.create_superuser("gv_audit", "gv@test.com", "pass")
    asg = Assignment.objects.create(
        title="t",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text="x " * 40)
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
    )
    factory = APIRequestFactory()
    req = factory.get(f"/api/v1/gradevance/runs/{run.id}/audit-export/")
    force_authenticate(req, user=user)
    resp = RunAuditExportView.as_view()(req, run_id=run.id)
    assert resp.status_code == 200
    assert resp.data["run_id"] == str(run.id)
    assert resp.data["export_format"] == "json_v2"
    assert "segments" in resp.data
    assert "assignment" in resp.data
    assert "coaching" in resp.data
    assert "fairness" in resp.data
    assert resp.data["fairness"]["mode"] == "formative"


@pytest.mark.django_db
def test_audit_export_summative_unreleased_409():
    user = User.objects.create_superuser("gv_audit2", "gv2@test.com", "pass")
    asg = Assignment.objects.create(
        title="t",
        mode=Assignment.MODE_SUMMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    sub = Submission.objects.create(assignment=asg, text="x " * 40)
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_NEEDS_REVIEW,
        released=False,
    )
    factory = APIRequestFactory()
    req = factory.get(f"/api/v1/gradevance/runs/{run.id}/audit-export/")
    force_authenticate(req, user=user)
    resp = RunAuditExportView.as_view()(req, run_id=run.id)
    assert resp.status_code == 409, getattr(resp, "data", resp.content)
