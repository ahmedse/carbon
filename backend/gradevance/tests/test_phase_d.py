"""Phase D — draft/submit lifecycle, appeals, progress, my_status, enrollment PATCH."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from gradevance.models import (
    AnalysisRun,
    Appeal,
    Assignment,
    Course,
    Enrollment,
    ReviewItem,
    Submission,
)

BASE = "/carbon-api/gradevance"
ME = f"{BASE}/me"


def _with_global_role(django_user_model, name, group_name):
    from accounts.models import ScopedRole

    user = django_user_model.objects.create_user(name, f"{name}@test.local", "x")
    group, _ = Group.objects.get_or_create(name=group_name)
    ScopedRole.objects.create(user=user, group=group, org_unit=None, module=None, is_active=True)
    return user


def _student(django_user_model, name):
    return _with_global_role(django_user_model, name, "gradevance_students")


def _lead(django_user_model, name):
    return _with_global_role(django_user_model, name, "gradevance_lead")


@pytest.fixture
def phase_d(django_user_model):
    course = Course.objects.create(code="PHD101", name="Phase D Course", entry_code="PHD-JOIN")
    alice = _student(django_user_model, "phd_alice")
    lead = _lead(django_user_model, "phd_lead")
    Enrollment.objects.create(
        course=course, user=alice, role=Enrollment.ROLE_STUDENT, source=Enrollment.SOURCE_MANUAL
    )
    Enrollment.objects.create(
        course=course, user=lead, role=Enrollment.ROLE_INSTRUCTOR, source=Enrollment.SOURCE_MANUAL
    )
    formative = Assignment.objects.create(
        course=course,
        title="Formative desk",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    summative = Assignment.objects.create(
        course=course,
        title="Summative desk",
        mode=Assignment.MODE_SUMMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    return {
        "course": course,
        "alice": alice,
        "lead": lead,
        "formative": formative,
        "summative": summative,
    }


@pytest.mark.django_db
def test_draft_save_patch_submit_creates_review_for_summative(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])
    text = "reflective practice draft " * 20

    created = client.post(
        f"{ME}/submissions/",
        {
            "assignment": str(phase_d["summative"].id),
            "text": text,
            "status": "draft",
        },
        format="json",
    )
    assert created.status_code == 201
    sub = created.data["submission"]
    assert sub["status"] == Submission.STATUS_DRAFT
    assert ReviewItem.objects.count() == 0

    patched = client.patch(
        f"{ME}/submissions/{sub['id']}/",
        {"text": text + " more words"},
        format="json",
    )
    assert patched.status_code == 200
    assert patched.data["status"] == Submission.STATUS_DRAFT
    assert patched.data["word_count"] > sub["word_count"]

    revert = client.patch(
        f"{ME}/submissions/{sub['id']}/",
        {"status": "submitted"},
        format="json",
    )
    assert revert.status_code == 200
    assert revert.data["status"] == Submission.STATUS_SUBMITTED
    assert ReviewItem.objects.filter(reason="student submit").exists()

    bad = client.patch(
        f"{ME}/submissions/{sub['id']}/",
        {"status": "draft"},
        format="json",
    )
    assert bad.status_code == 400


@pytest.mark.django_db
def test_analyze_keeps_draft_by_default(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])
    res = client.post(
        f"{ME}/submissions/",
        {
            "assignment": str(phase_d["formative"].id),
            "text": "coaching draft " * 30,
            "analyze": True,
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.data["submission"]["status"] == Submission.STATUS_DRAFT
    assert "run" in res.data


@pytest.mark.django_db
def test_appeal_blocked_if_summative_unreleased(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])
    sub = Submission.objects.create(
        assignment=phase_d["summative"],
        student_user=phase_d["alice"],
        text="essay " * 40,
        word_count=40,
        status=Submission.STATUS_SUBMITTED,
    )
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
        advisory_bands={"task": "B"},
        released=False,
    )
    res = client.post(
        f"{ME}/appeals/",
        {"run": str(run.id), "reason": "Please reconsider band"},
        format="json",
    )
    assert res.status_code == 400
    assert "released" in res.data["detail"].lower()


@pytest.mark.django_db
def test_appeal_ok_after_release_and_teach_resolve(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])
    sub = Submission.objects.create(
        assignment=phase_d["summative"],
        student_user=phase_d["alice"],
        text="essay " * 40,
        word_count=40,
        status=Submission.STATUS_SUBMITTED,
    )
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
        advisory_bands={"task": "B"},
        released=True,
    )
    created = client.post(
        f"{ME}/appeals/",
        {"run": str(run.id), "reason": "Evidence overlooked"},
        format="json",
    )
    assert created.status_code == 201
    assert created.data["status"] == Appeal.STATUS_OPEN
    appeal_id = created.data["id"]

    dup = client.post(
        f"{ME}/appeals/",
        {"run": str(run.id), "reason": "Again"},
        format="json",
    )
    assert dup.status_code == 400

    teach = APIClient()
    teach.force_authenticate(phase_d["lead"])
    inbox = teach.get(f"{BASE}/appeals/", {"status": "open"})
    assert inbox.status_code == 200
    assert inbox.data["count"] >= 1
    ids = {row["id"] for row in inbox.data["results"]}
    assert appeal_id in ids

    resolved = teach.post(
        f"{BASE}/appeals/{appeal_id}/resolve/",
        {"resolution": "Band confirmed after review", "status": "rejected"},
        format="json",
    )
    assert resolved.status_code == 200
    assert resolved.data["status"] == Appeal.STATUS_REJECTED
    assert resolved.data["resolution"]
    assert Appeal.objects.get(pk=appeal_id).resolved_by_id == phase_d["lead"].id


@pytest.mark.django_db
def test_me_progress_returns_rows(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])
    sub = Submission.objects.create(
        assignment=phase_d["formative"],
        student_user=phase_d["alice"],
        text="progress text " * 20,
        word_count=40,
        status=Submission.STATUS_DRAFT,
    )
    AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
        advisory_bands={"sg": "good"},
        released=False,
    )
    res = client.get(f"{ME}/progress/")
    assert res.status_code == 200
    assert res.data["count"] >= 1
    row = next(r for r in res.data["results"] if r["submission_id"] == str(sub.id))
    assert row["assignment_id"] == str(phase_d["formative"].id)
    assert row["title"] == "Formative desk"
    assert row["run_id"]
    assert row["status"] == Submission.STATUS_DRAFT
    assert "wave_points" in row


@pytest.mark.django_db
def test_my_status_transitions(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])

    open_res = client.get(f"{ME}/assignments/{phase_d['formative'].id}/")
    assert open_res.status_code == 200
    assert open_res.data["my_status"] == "open"
    assert open_res.data["course_title"] == "Phase D Course"
    assert "due_at" in open_res.data

    client.post(
        f"{ME}/submissions/",
        {
            "assignment": str(phase_d["formative"].id),
            "text": "draft words " * 10,
            "status": "draft",
        },
        format="json",
    )
    drafted = client.get(f"{ME}/assignments/{phase_d['formative'].id}/")
    assert drafted.data["my_status"] == "drafted"

    sub_id = Submission.objects.filter(
        assignment=phase_d["formative"], student_user=phase_d["alice"]
    ).first().id
    client.patch(
        f"{ME}/submissions/{sub_id}/",
        {"status": "submitted"},
        format="json",
    )
    submitted = client.get(f"{ME}/assignments/{phase_d['formative'].id}/")
    assert submitted.data["my_status"] == "submitted"

    run = AnalysisRun.objects.create(
        submission_id=sub_id,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
        released=True,
    )
    released = client.get(f"{ME}/assignments/{phase_d['formative'].id}/")
    assert released.data["my_status"] == "released"
    assert run.id  # used


@pytest.mark.django_db
def test_enrollment_deactivate(phase_d):
    ens = Enrollment.objects.get(course=phase_d["course"], user=phase_d["alice"])
    client = APIClient()
    client.force_authenticate(phase_d["lead"])
    res = client.patch(
        f"{BASE}/courses/{phase_d['course'].id}/enrollments/{ens.id}/",
        {"active": False},
        format="json",
    )
    assert res.status_code == 200
    assert res.data["active"] is False
    ens.refresh_from_db()
    assert ens.active is False

    # Student loses assignment access when inactive.
    stu = APIClient()
    stu.force_authenticate(phase_d["alice"])
    denied = stu.get(f"{ME}/assignments/{phase_d['formative'].id}/")
    assert denied.status_code == 404


@pytest.mark.django_db
def test_qa_summary(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["lead"])
    res = client.get(f"{BASE}/qa/summary/")
    assert res.status_code == 200
    assert "open_appeals" in res.data
    assert "open_reviews" in res.data
    assert "fairness_note" in res.data
    assert "profiles_hint" in res.data


@pytest.mark.django_db
def test_appeal_withdraw(phase_d):
    client = APIClient()
    client.force_authenticate(phase_d["alice"])
    sub = Submission.objects.create(
        assignment=phase_d["formative"],
        student_user=phase_d["alice"],
        text="formative " * 20,
        word_count=20,
        status=Submission.STATUS_SUBMITTED,
    )
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
        released=False,
    )
    created = client.post(
        f"{ME}/appeals/",
        {"run": str(run.id), "reason": "Want a second look"},
        format="json",
    )
    assert created.status_code == 201
    withdrawn = client.post(f"{ME}/appeals/{created.data['id']}/withdraw/", {}, format="json")
    assert withdrawn.status_code == 200
    assert withdrawn.data["status"] == Appeal.STATUS_WITHDRAWN
