"""Roster list/add + student join-by-code (persona apps P5 slice)."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from gradevance.models import Assignment, Course, Enrollment

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
def roster_campus(django_user_model):
    course = Course.objects.create(
        code="ROST101", name="Roster course", entry_code="JOIN-ROST"
    )
    other = Course.objects.create(code="ROST999", name="Other", entry_code="OTHER")
    asg = Assignment.objects.create(
        course=course,
        title="Roster stem",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    lead = _lead(django_user_model, "roster_lead")
    student = _student(django_user_model, "roster_stu")
    return {
        "course": course,
        "other": other,
        "asg": asg,
        "lead": lead,
        "student": student,
    }


@pytest.mark.django_db
def test_manage_user_lists_and_adds_enrollment(roster_campus, django_user_model):
    course = roster_campus["course"]
    lead = roster_campus["lead"]
    target = _student(django_user_model, "roster_add_me")
    client = APIClient()
    client.force_authenticate(lead)

    empty = client.get(f"{BASE}/courses/{course.id}/enrollments/")
    assert empty.status_code == 200
    assert empty.data["count"] == 0

    created = client.post(
        f"{BASE}/courses/{course.id}/enrollments/",
        {"username": target.username, "role": "student"},
        format="json",
    )
    assert created.status_code == 201
    assert created.data["user"] == target.username
    assert created.data["role"] == Enrollment.ROLE_STUDENT
    assert created.data["source"] == Enrollment.SOURCE_MANUAL

    listed = client.get(f"{BASE}/courses/{course.id}/enrollments/")
    assert listed.status_code == 200
    assert listed.data["count"] == 1
    assert listed.data["results"][0]["user"] == target.username


@pytest.mark.django_db
def test_student_joins_via_entry_code_then_sees_assignment(roster_campus):
    course = roster_campus["course"]
    student = roster_campus["student"]
    asg = roster_campus["asg"]
    client = APIClient()
    client.force_authenticate(student)

    before = client.get(f"{ME}/assignments/")
    assert before.status_code == 200
    assert before.data["count"] == 0

    bad = client.post(f"{ME}/join/", {"entry_code": "NOPE"}, format="json")
    assert bad.status_code == 404

    joined = client.post(f"{ME}/join/", {"entry_code": "JOIN-ROST"}, format="json")
    assert joined.status_code == 200
    assert joined.data["code"] == course.code

    ens = Enrollment.objects.get(course=course, user=student)
    assert ens.role == Enrollment.ROLE_STUDENT
    assert ens.source == Enrollment.SOURCE_CODE

    after = client.get(f"{ME}/assignments/")
    assert after.status_code == 200
    ids = {row["id"] for row in after.data["results"]}
    assert str(asg.id) in ids


@pytest.mark.django_db
def test_student_cannot_post_course_enrollments(roster_campus, django_user_model):
    course = roster_campus["course"]
    student = roster_campus["student"]
    peer = _student(django_user_model, "roster_peer")
    client = APIClient()
    client.force_authenticate(student)

    # MarkAccess fails → 403 from permission class (no mark/manage).
    res = client.post(
        f"{BASE}/courses/{course.id}/enrollments/",
        {"username": peer.username, "role": "student"},
        format="json",
    )
    assert res.status_code == 403
