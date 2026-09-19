"""P1 persona apps — Enrollment + gradevance/me/* + teach course scope (ADR-0042)."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from gradevance.models import AnalysisRun, Assignment, Course, Enrollment, Submission
from gradevance.lti.roster_sync import ensure_enrollment, role_from_lti_roles

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
def campus(django_user_model):
    mine = Course.objects.create(code="NURS101", name="Mine")
    other = Course.objects.create(code="NURS999", name="Other")
    alice = _student(django_user_model, "me_alice")
    Enrollment.objects.create(
        course=mine, user=alice, role=Enrollment.ROLE_STUDENT, source=Enrollment.SOURCE_MANUAL
    )
    asg_mine = Assignment.objects.create(
        course=mine,
        title="My stem",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    asg_other = Assignment.objects.create(
        course=other,
        title="Other stem",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    asg_summative = Assignment.objects.create(
        course=mine,
        title="Summative stem",
        mode=Assignment.MODE_SUMMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    return {
        "mine": mine,
        "other": other,
        "alice": alice,
        "asg_mine": asg_mine,
        "asg_other": asg_other,
        "asg_summative": asg_summative,
    }


@pytest.mark.django_db
def test_student_lists_only_enrolled_courses(campus):
    client = APIClient()
    client.force_authenticate(campus["alice"])
    res = client.get(f"{ME}/courses/")
    assert res.status_code == 200
    codes = {row["code"] for row in res.data["results"]}
    assert codes == {"NURS101"}
    assert res.data["count"] == 1


@pytest.mark.django_db
def test_student_cannot_get_assignment_on_other_course(campus):
    client = APIClient()
    client.force_authenticate(campus["alice"])
    ok = client.get(f"{ME}/assignments/{campus['asg_mine'].id}/")
    assert ok.status_code == 200
    denied = client.get(f"{ME}/assignments/{campus['asg_other'].id}/")
    assert denied.status_code == 404


@pytest.mark.django_db
def test_student_me_runs_strips_unreleased_summative_bands(campus):
    client = APIClient()
    client.force_authenticate(campus["alice"])
    sub = Submission.objects.create(
        assignment=campus["asg_summative"],
        student_user=campus["alice"],
        text="reflective prose " * 20,
        word_count=40,
    )
    run = AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        status=AnalysisRun.STATUS_COMPLETE,
        gate_decision=AnalysisRun.GATE_REVIEW,
        advisory_bands={"task_achievement": "B", "score": 72},
        coaching={"tips": ["keep going"]},
        released=False,
    )
    res = client.get(f"{ME}/runs/{run.id}/")
    assert res.status_code == 200
    assert res.data["advisory_bands"] == {"withheld": True}
    assert res.data["status"] == AnalysisRun.STATUS_COMPLETE
    assert res.data["gate_decision"] == AnalysisRun.GATE_REVIEW
    assert res.data["coaching"] == {"tips": ["keep going"]}


@pytest.mark.django_db
def test_student_me_submissions_only_own(campus, django_user_model):
    bob = _student(django_user_model, "me_bob")
    Enrollment.objects.create(
        course=campus["mine"], user=bob, role=Enrollment.ROLE_STUDENT, source=Enrollment.SOURCE_MANUAL
    )
    a_sub = Submission.objects.create(
        assignment=campus["asg_mine"],
        student_user=campus["alice"],
        text="alice text " * 10,
        word_count=20,
    )
    Submission.objects.create(
        assignment=campus["asg_mine"],
        student_user=bob,
        text="bob text " * 10,
        word_count=20,
    )
    client = APIClient()
    client.force_authenticate(campus["alice"])
    res = client.get(f"{ME}/submissions/")
    assert res.status_code == 200
    ids = {row["id"] for row in res.data["results"]}
    assert ids == {str(a_sub.id)}


@pytest.mark.django_db
def test_teacher_with_enrollments_sees_scoped_courses(campus, django_user_model):
    lead = _lead(django_user_model, "scoped_prof")
    Enrollment.objects.create(
        course=campus["mine"],
        user=lead,
        role=Enrollment.ROLE_INSTRUCTOR,
        source=Enrollment.SOURCE_MANUAL,
    )
    client = APIClient()
    client.force_authenticate(lead)
    res = client.get(f"{BASE}/courses/")
    assert res.status_code == 200
    codes = {row["code"] for row in res.data["results"]}
    assert codes == {"NURS101"}


@pytest.mark.django_db
def test_teacher_with_zero_enrollments_sees_all(campus, django_user_model):
    lead = _lead(django_user_model, "compat_prof")
    client = APIClient()
    client.force_authenticate(lead)
    res = client.get(f"{BASE}/courses/")
    assert res.status_code == 200
    codes = {row["code"] for row in res.data["results"]}
    assert "NURS101" in codes and "NURS999" in codes


@pytest.mark.django_db
def test_me_submissions_include_latest_run_coaching(campus):
    """Learn home coaching contract: list exposes latest_run.coaching + assignment_title."""
    client = APIClient()
    client.force_authenticate(campus["alice"])
    sub = Submission.objects.create(
        assignment=campus["asg_mine"],
        student_user=campus["alice"],
        text="Reflection on exam prep " * 20,
        word_count=40,
        status=Submission.STATUS_DRAFT,
    )
    AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        status=AnalysisRun.STATUS_COMPLETE,
        coaching={
            "watermark": "advisory",
            "strengths": ["Clear WHAT move"],
            "diagnosis_actions": [{"diagnosis": "NOW WHAT thin", "action": "Add next step"}],
        },
    )
    res = client.get(f"{ME}/submissions/")
    assert res.status_code == 200
    row = next(r for r in res.data["results"] if r["id"] == str(sub.id))
    assert row["assignment_title"] == "My stem"
    assert row["latest_run"] is not None
    assert row["latest_run"]["coaching"]["strengths"] == ["Clear WHAT move"]
    assert row["latest_run"]["coaching"]["diagnosis_actions"][0]["action"] == "Add next step"


@pytest.mark.django_db
def test_role_from_lti_roles_and_ensure_enrollment(campus, django_user_model):
    assert role_from_lti_roles(("Learner",)) == Enrollment.ROLE_STUDENT
    assert role_from_lti_roles(("Instructor",)) == Enrollment.ROLE_INSTRUCTOR
    assert role_from_lti_roles(("http://purl.imsglobal.org/vocab/lis/v2/membership/Instructor#TeachingAssistant",)) == Enrollment.ROLE_TA
    user = _student(django_user_model, "nrps_stu")
    ens = ensure_enrollment(campus["other"], user, Enrollment.ROLE_STUDENT)
    assert ens.course_id == campus["other"].id
    assert ens.role == Enrollment.ROLE_STUDENT
    assert ens.source == Enrollment.SOURCE_NRPS
    # idempotent update
    ens2 = ensure_enrollment(campus["other"], user, Enrollment.ROLE_TA)
    assert ens2.id == ens.id
    assert ens2.role == Enrollment.ROLE_TA
