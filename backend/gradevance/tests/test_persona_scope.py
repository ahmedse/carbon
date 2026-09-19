"""P0 privacy scope (GRADEVANCE-PERSONA-APPS §2.2, ADR-0042 §8).

A submit-only student must never read or re-analyze another student's submission.
Course staff (mark/manage) keep cohort visibility.
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from gradevance.models import Assignment, Submission

BASE = "/carbon-api/gradevance"


def _with_global_role(django_user_model, name, group_name):
    """Capabilities resolve from active global ScopedRole rows (accounts.capabilities)."""
    from accounts.models import ScopedRole

    user = django_user_model.objects.create_user(name, f"{name}@test.local", "x")
    group, _ = Group.objects.get_or_create(name=group_name)
    ScopedRole.objects.create(user=user, group=group, org_unit=None, module=None, is_active=True)
    return user


def _student(django_user_model, name):
    return _with_global_role(django_user_model, name, "gradevance_students")


def _marker(django_user_model, name):
    return _with_global_role(django_user_model, name, "gradevance_markers")


@pytest.fixture
def cohort(django_user_model):
    asg = Assignment.objects.create(
        title="Scoped",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    alice = _student(django_user_model, "alice")
    bob = _student(django_user_model, "bob")
    a_sub = Submission.objects.create(
        assignment=asg, student_user=alice, text="alice private reflection " * 10, word_count=30
    )
    b_sub = Submission.objects.create(
        assignment=asg, student_user=bob, text="bob private reflection " * 10, word_count=30
    )
    return {"asg": asg, "alice": alice, "bob": bob, "a_sub": a_sub, "b_sub": b_sub}


@pytest.mark.django_db
def test_student_lists_only_own_submissions(cohort):
    client = APIClient()
    client.force_authenticate(cohort["alice"])
    res = client.get(f"{BASE}/submissions/", {"assignment": str(cohort["asg"].id)})
    assert res.status_code == 200
    ids = {row["id"] for row in res.data["results"]}
    assert ids == {str(cohort["a_sub"].id)}
    assert res.data["count"] == 1
    assert all("bob" not in (row.get("text") or "") for row in res.data["results"])


@pytest.mark.django_db
def test_student_cannot_analyze_other_students_submission(cohort):
    client = APIClient()
    client.force_authenticate(cohort["alice"])
    res = client.post(f"{BASE}/submissions/{cohort['b_sub'].id}/analyze/")
    assert res.status_code == 404


@pytest.mark.django_db
def test_marker_keeps_cohort_visibility(cohort, django_user_model):
    client = APIClient()
    client.force_authenticate(_marker(django_user_model, "marker1"))
    res = client.get(f"{BASE}/submissions/", {"assignment": str(cohort["asg"].id)})
    assert res.status_code == 200
    assert res.data["count"] == 2
