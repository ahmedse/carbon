"""Learn + Instrument Trust smoke — API journey without live passwords.

Covers the product path: me/* coaching contract, course-filtered assignments,
progress, calibration gold_status honesty (NAA expert vs medicine seeded).
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from gradevance.models import AnalysisRun, Assignment, Course, Enrollment, Submission
from gradevance.services.packs import find_profile_file_for_id, load_profile
from gradevance.services.publish import evaluate_publish_gate

BASE = "/carbon-api/gradevance"
ME = f"{BASE}/me"


def _with_global_role(django_user_model, name, group_name):
    from accounts.models import ScopedRole

    user = django_user_model.objects.create_user(name, f"{name}@test.local", "x")
    group, _ = Group.objects.get_or_create(name=group_name)
    ScopedRole.objects.create(user=user, group=group, org_unit=None, module=None, is_active=True)
    return user


@pytest.fixture
def smoke_world(django_user_model):
    course_a = Course.objects.create(code="SMOKE-A", name="Smoke Course A", entry_code="SMOKEA")
    course_b = Course.objects.create(code="SMOKE-B", name="Smoke Course B", entry_code="SMOKEB")
    alice = _with_global_role(django_user_model, "smoke_alice", "gradevance_students")
    lead = _with_global_role(django_user_model, "smoke_lead", "gradevance_lead")
    Enrollment.objects.create(
        course=course_a, user=alice, role=Enrollment.ROLE_STUDENT, source=Enrollment.SOURCE_MANUAL
    )
    Enrollment.objects.create(
        course=course_a, user=lead, role=Enrollment.ROLE_INSTRUCTOR, source=Enrollment.SOURCE_MANUAL
    )
    asg_a = Assignment.objects.create(
        course=course_a,
        title="Smoke reflection A",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    asg_b = Assignment.objects.create(
        course=course_b,
        title="Other course stem",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
    )
    return {
        "course_a": course_a,
        "course_b": course_b,
        "alice": alice,
        "lead": lead,
        "asg_a": asg_a,
        "asg_b": asg_b,
    }


@pytest.mark.django_db
def test_smoke_learn_home_coaching_and_assignments_by_course(smoke_world):
    client = APIClient()
    client.force_authenticate(smoke_world["alice"])

    courses = client.get(f"{ME}/courses/")
    assert courses.status_code == 200
    assert any(c["code"] == "SMOKE-A" for c in courses.data["results"])

    all_asg = client.get(f"{ME}/assignments/")
    assert all_asg.status_code == 200
    titles = {a["title"] for a in all_asg.data["results"]}
    assert "Smoke reflection A" in titles
    assert "Other course stem" not in titles

    filtered = client.get(f"{ME}/assignments/", {"course": str(smoke_world["course_a"].id)})
    assert filtered.status_code == 200
    assert len(filtered.data["results"]) >= 1
    assert all(
        str(a.get("course") or a.get("course_id") or "") == str(smoke_world["course_a"].id)
        or a.get("course_title")
        for a in filtered.data["results"]
    )

    sub = Submission.objects.create(
        assignment=smoke_world["asg_a"],
        student_user=smoke_world["alice"],
        text="The most difficult aspect of preparing is time. " * 15,
        word_count=75,
        status=Submission.STATUS_DRAFT,
    )
    AnalysisRun.objects.create(
        submission=sub,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        status=AnalysisRun.STATUS_COMPLETE,
        coaching={
            "watermark": "advisory",
            "strengths": ["Specific episode"],
            "diagnosis_actions": [{"diagnosis": "Thin SO WHAT", "action": "Name the principle"}],
        },
    )

    subs = client.get(f"{ME}/submissions/")
    assert subs.status_code == 200
    row = next(r for r in subs.data["results"] if r["id"] == str(sub.id))
    assert row["assignment_title"] == "Smoke reflection A"
    assert row["latest_run"]["coaching"]["strengths"] == ["Specific episode"]
    assert row["latest_run"]["coaching"]["watermark"] == "advisory"

    progress = client.get(f"{ME}/progress/")
    assert progress.status_code == 200
    assert progress.data["count"] >= 1
    prog_row = next(
        r for r in progress.data["results"] if r["assignment_id"] == str(smoke_world["asg_a"].id)
    )
    assert prog_row["title"] == "Smoke reflection A"


@pytest.mark.django_db
def test_smoke_calibration_naa_expert_vs_medicine_seeded(smoke_world):
    """Teach/engine calibration honesty — NAA expert; OSCE seeded; CBL disjoint soft."""
    client = APIClient()
    client.force_authenticate(smoke_world["lead"])

    naa = client.get(
        f"{BASE}/calibration/",
        {"profile_pack_id": "naa_cycle1_exam_prep", "profile_version": 1},
    )
    assert naa.status_code == 200
    gate = naa.data["publish_gate"]
    assert gate.get("expert_trusted") is True
    assert gate.get("held_out_n", 0) >= 5

    # OSCE clinical reflection still seeded
    loaded = load_profile(find_profile_file_for_id("medicine_osce_abdominal", 1))
    summative = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=1)
    assert summative["expert_trusted"] is False
    assert summative["gold_status"] == "seeded_draft"
    assert summative["passed"] is False

    # CBL promoted to instrument_coded_disjoint
    cbl = load_profile(find_profile_file_for_id("medicine_cbl_appendicitis", 1))
    cbl_gate = evaluate_publish_gate(cbl, as_mode="summative", min_held_out=5)
    assert cbl_gate["expert_trusted"] is True
    assert cbl_gate["gold_status"] == "instrument_coded_disjoint"


@pytest.mark.django_db
def test_smoke_naa_summative_gate_still_expert_trusted():
    loaded = load_profile(find_profile_file_for_id("naa_cycle1_exam_prep", 1))
    gate = evaluate_publish_gate(loaded, as_mode="summative", min_held_out=5)
    assert gate["required"] is True
    assert gate["expert_trusted"] is True
    assert gate.get("held_out_anchor_overlaps", 0) == 0
