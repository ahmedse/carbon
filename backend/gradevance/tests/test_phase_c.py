"""Phase C: profile detail, KB list, upload, batch analyze, draft stem freeze."""
from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from gradevance.models import Assignment, Course, Submission
from gradevance.services.packs import list_knowledge_bases, profile_detail_payload


def test_list_knowledge_bases_includes_stub():
    rows = list_knowledge_bases()
    assert any(r["pack_id"] == "naa_reflective_kb_v1" for r in rows)


def test_profile_detail_payload_has_anchors():
    detail = profile_detail_payload("naa_cycle1_exam_prep", 1)
    assert detail["pack_id"] == "naa_cycle1_exam_prep"
    assert isinstance(detail["anchors"], list)
    assert "band_descriptors" in detail


@pytest.mark.django_db
def test_patch_stem_frozen_when_published(django_user_model):
    user = django_user_model.objects.create_superuser("gv_c", "gv_c@test.local", "x")
    course = Course.objects.create(code="C1", name="Course")
    asg = Assignment.objects.create(
        course=course,
        title="Pub",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        brief={"stem": "original"},
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user)
    res = client.patch(
        f"/carbon-api/gradevance/assignments/{asg.id}/",
        {"brief": {"stem": "rewritten"}},
        format="json",
    )
    assert res.status_code == 400
    asg.refresh_from_db()
    assert asg.brief.get("stem") == "original"


@pytest.mark.django_db
def test_patch_stem_ok_on_draft(django_user_model):
    user = django_user_model.objects.create_superuser("gv_d", "gv_d@test.local", "x")
    asg = Assignment.objects.create(
        title="Draft",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_DRAFT,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        brief={"stem": "old"},
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user)
    res = client.patch(
        f"/carbon-api/gradevance/assignments/{asg.id}/",
        {"brief": {"stem": "new stem"}},
        format="json",
    )
    assert res.status_code == 200
    asg.refresh_from_db()
    assert asg.brief.get("stem") == "new stem"


@pytest.mark.django_db
def test_upload_and_batch_analyze(django_user_model):
    user = django_user_model.objects.create_superuser("gv_u", "gv_u@test.local", "x")
    asg = Assignment.objects.create(
        title="Upload",
        mode=Assignment.MODE_FORMATIVE,
        status=Assignment.STATUS_PUBLISHED,
        profile_pack_id="naa_cycle1_exam_prep",
        profile_version=1,
        pipeline_config_snapshot={"lct_enabled": True},
        brief={"stem": "s"},
        created_by=user,
    )
    client = APIClient()
    client.force_authenticate(user)
    upload = SimpleUploadedFile("essay.txt", b"I sat the mock exam for two hours and learned density matters.", content_type="text/plain")
    res = client.post(
        "/carbon-api/gradevance/submissions/upload/",
        {"assignment": str(asg.id), "file": upload, "analyze": "false"},
        format="multipart",
    )
    assert res.status_code == 201, res.content
    assert Submission.objects.filter(assignment=asg).count() == 1

    # second text-only submission
    Submission.objects.create(assignment=asg, student_user=user, text="Second draft about reflection.", word_count=4)

    batch = client.post(
        f"/carbon-api/gradevance/assignments/{asg.id}/batch-analyze/",
        {},
        format="json",
    )
    assert batch.status_code == 200, batch.content
    assert batch.data["analyzed"] >= 1
