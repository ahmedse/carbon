"""
W5-C — plan artifact delivery tests.

Covers:
  - store_artifact: writes the file + creates a RunArtifact row, returns
    public metadata (artifact_id, name, size_bytes, download_url).
  - list endpoint: GET /plans/{id}/artifacts/ returns owner-scoped artifacts.
  - download endpoint: streams the file with Content-Disposition attachment.
  - owner scoping (CBAC): another user cannot list or download artifacts.
  - serialization: step payload gains ``artifacts`` + ``output_type``, and
    ``tool_output`` gains ``_output_type``.

Artifacts are written under a temp MEDIA_ROOT so tests never pollute the real
media store.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import override_settings

from accounts.models import User
from ai.models.core import Run, RunArtifact, RunStep
from ai.plans_service import PlansService, _infer_output_type


@pytest.fixture
def user(db):
    return User.objects.create_user(username="artifact-worker", password="secret123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="artifact-other", password="secret123")


def _make_run(user, status="completed"):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Produce a downloadable report",
        status=status,
        plan_json={"steps": [{"step_id": 0, "intent": "Export a report"}]},
    )


def _store(run, step_index=0, name="report.docx", content=b"hello artifact", mime="application/octet-stream"):
    return PlansService.store_artifact(
        run_id=run.id,
        step_index=step_index,
        name=name,
        content_bytes=content,
        mime_type=mime,
    )


# ── Service: store_artifact ──────────────────────────────────────────────


@pytest.mark.django_db
def test_store_artifact_creates_file_and_record(user, tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        run = _make_run(user)
        RunStep.objects.create(
            run_id=run.id,
            step_index=0,
            intent="Export a report",
            tool_name="export_document",
            status="completed",
        )

        meta = _store(run, step_index=0, name="report.docx", content=b"abc123")

        artifact = RunArtifact.objects.get(id=meta["artifact_id"])
        assert artifact.run_id == run.id
        assert artifact.step_index == 0
        assert artifact.name == "report.docx"
        assert artifact.size_bytes == 6

        # The file actually exists on disk (temp MEDIA_ROOT).
        assert artifact.file.name
        with artifact.file.open("rb") as fh:
            assert fh.read() == b"abc123"

        # Public metadata matches the spec shape.
        assert meta["name"] == "report.docx"
        assert meta["size_bytes"] == 6
        assert meta["download_url"].endswith(
            f"/ai/plans/{run.id}/artifacts/{artifact.id}/download/"
        )


# ── API: list + download (owner-scoped) ──────────────────────────────────


@pytest.mark.django_db
def test_artifact_list_endpoint_owner_scoped(
    api_client, get_token_for_user, user, tmp_path
):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        run = _make_run(user)
        _store(run, step_index=0, name="report.docx")

        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.get(f"/carbon-api/ai/plans/{run.id}/artifacts/")

        assert resp.status_code == 200, resp.content
        payload = resp.json()
        assert payload["plan_id"] == run.id
        assert payload["count"] == 1
        assert payload["artifacts"][0]["name"] == "report.docx"
        assert payload["artifacts"][0]["download_url"]


@pytest.mark.django_db
def test_artifact_download_streams_file(
    api_client, get_token_for_user, user, tmp_path
):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        run = _make_run(user)
        meta = _store(run, step_index=0, name="report.docx", content=b"stream-me")

        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.get(
            f"/carbon-api/ai/plans/{run.id}/artifacts/{meta['artifact_id']}/download/"
        )

        assert resp.status_code == 200, resp.content
        assert b"stream-me" in b"".join(resp.streaming_content)
        disposition = resp.get("Content-Disposition", "")
        assert "attachment" in disposition


@pytest.mark.django_db
def test_cross_user_artifact_access_denied(
    api_client, get_token_for_user, user, other_user, tmp_path
):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        run = _make_run(user)
        meta = _store(run, step_index=0, name="report.docx")

        token = get_token_for_user(other_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        list_resp = api_client.get(f"/carbon-api/ai/plans/{run.id}/artifacts/")
        assert list_resp.status_code == 404

        dl_resp = api_client.get(
            f"/carbon-api/ai/plans/{run.id}/artifacts/{meta['artifact_id']}/download/"
        )
        assert dl_resp.status_code == 404


# ── Serialization: output_type + artifacts in the step payload ───────────


@pytest.mark.django_db
def test_serialize_run_includes_output_type_and_artifacts(user, tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        run = _make_run(user)
        RunStep.objects.create(
            run_id=run.id,
            step_index=0,
            intent="Export a report",
            tool_name="export_document",
            status="completed",
            tool_output_json={
                "action": "download",
                "title": "Report",
                "files": [{"filename": "report.docx"}],
            },
        )
        _store(run, step_index=0, name="report.docx")

        payload = PlansService().get_plan(user, run.id)
        step = payload["steps"][0]
        assert step["output_type"] == "artifact"
        assert step["tool_output"]["_output_type"] == "artifact"
        assert len(step["artifacts"]) == 1
        assert step["artifacts"][0]["name"] == "report.docx"
        assert step["artifacts"][0]["download_url"]


def test_infer_output_type_shapes():
    assert _infer_output_type({"result": "a prose summary"}) == "text"
    assert _infer_output_type({"headers": ["a"], "rows": [[1]]}) == "table"
    assert _infer_output_type({"series": [1, 2, 3], "labels": ["x"]}) == "chart"
    assert _infer_output_type({"files": [{"filename": "r.xlsx"}]}) == "artifact"
    assert _infer_output_type({"nested": {"key": "value"}}) == "json"
    assert _infer_output_type(None) is None
    assert _infer_output_type({}) is None
