"""W6-C — End-to-end artifact proof (F-25).

Drives ONE approved plan through the REAL ReActLoop + REAL ExportDocument
plugin + REAL ``store_artifact`` handoff (contextvar + ``sync_to_async``
bridge) and asserts the durable artifact ledger, the serialized step payload
(``output_type == "artifact"`` + ``artifacts[].download_url``), and a 200
attachment download through the plans API.

This is the regression gate for the two W6-C handoff fixes:

1. ``export_document``'s artifact handoff is bridged through
   ``sync_to_async`` — the sync-ORM-inside-async-loop fault that raised
   ``SynchronousOnlyOperation`` and silently dropped every ``RunArtifact``
   row (fail-visible catch in the plugin).
2. ``execute._execute_single_tool`` promotes output-type marker keys (e.g.
   ``files``) from a dict tool result to the wrapper's top level so the
   frozen ``_infer_output_type`` sees the artifact shape instead of "text".

Unlike ``test_plans.py`` (which swaps in a ``_FakeReActLoop``), this test
exercises the REAL loop, REAL executor dispatch, and REAL plugin registry —
the exact path production runs (``AI_STORE_BACKEND=django`` per ``backend/.env``).
"""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from ai.models.core import Run, RunArtifact, RunStep
from ai.plans_service import PlansService
from ai.store import reset_store

User = get_user_model()

ARTIFACT_ARGS = {
    "title": "W6C Carbon Study",
    "format": "docx",
    "content": "# Findings\n\n- Approved emissions 1.2 kt.",
    "table": {"headers": ["Metric", "Value"], "rows": [["CO2e", "1200"]]},
}


class _FakeDraftWitness:
    """Deterministic draft — emits exactly one ``export_document`` tool call."""

    def __init__(self, *args, **kwargs):
        pass

    async def draft(self, **kwargs):
        return SimpleNamespace(
            text="Exporting the study as a Word report.",
            tool_calls=[
                {
                    "id": "call_w6c_export",
                    "type": "function",
                    "function": {
                        "name": "export_document",
                        "arguments": json.dumps(ARTIFACT_ARGS),
                    },
                }
            ],
        )


class _FakeCriticWitness:
    """Deterministic critic — always passes the non-mutating export step."""

    def __init__(self, *args, **kwargs):
        pass

    async def review(self, **kwargs):
        return SimpleNamespace(verdict="pass", flags=[])


def _make_export_run(user) -> Run:
    """Seed an approved plan whose single step calls ``export_document``."""
    run = Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Export this study as a Word report.",
        status="approved",
        plan_json={
            "pattern": "single_step",
            "source": "single_step",
            "skill_name": None,
            "synthesis_instruction": "Summarize the export.",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Export the study as a downloadable report",
                    "tool_name": "export_document",
                    "tool_args": ARTIFACT_ARGS,
                    "depends_on": [],
                    "is_mutation": False,
                    "agent_role": "worker",
                },
            ],
        },
    )
    RunStep.objects.create(
        run_id=run.id,
        step_index=0,
        intent="Export the study as a downloadable report",
        tool_name="export_document",
        tool_args_json=ARTIFACT_ARGS,
        depends_on_json=[],
        status="pending",
    )
    return run


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="w6c-artifact-worker", password="secret123"
    )


@pytest.fixture
def run_cleanup():
    ids: list[str] = []
    yield ids
    RunStep.objects.filter(run_id__in=ids).delete()
    RunArtifact.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()


@pytest.mark.django_db(transaction=True)
def test_plan_export_document_end_to_end_artifact(
    user, api_client, get_token_for_user, tmp_path, run_cleanup
):
    """Real loop → real export_document → RunArtifact row → 200 download."""
    run = _make_export_run(user)
    run_cleanup.append(run.id)

    # The REAL engine path must run against the DjangoStore (mirrors
    # backend/.env AI_STORE_BACKEND=django) so Run/RunStep/RunArtifact are
    # persisted durably through the loop's ``_db`` session. reset_store()
    # clears the cached singleton so the override takes effect.
    with override_settings(
        AI_STORE_BACKEND="django", MEDIA_ROOT=str(tmp_path)
    ):
        reset_store()
        try:
            with patch(
                "ai.engine.cognition.turn.draft.DraftWitness", _FakeDraftWitness
            ), patch(
                "ai.engine.cognition.turn.critic.CriticWitness", _FakeCriticWitness
            ), patch(
                "ai.engine.llm.prompts.build_chat_prompt",
                AsyncMock(return_value="W6C system prompt"),
            ), patch(
                "ai.engine_runtime._carbon_instance_config",
                lambda user_pk: {
                    "display_name": "Carbon",
                    "description": "W6C artifact proof",
                },
            ), patch(
                "ai.engine_runtime._build_chat_user_info",
                lambda user_pk: {
                    "username": user.username,
                    "display_name": user.username,
                    "email": "",
                    "roles": [],
                },
            ):
                service = PlansService()
                frames = list(service._run_plan_frames_sync(user, run.id))
        finally:
            reset_store()

        # ── Gate 1: durable ledger ───────────────────────────────────────
        artifacts = list(
            RunArtifact.objects.filter(run_id=run.id).order_by("created_at")
        )
        assert artifacts, (
            "no RunArtifact row — the engine→store_artifact handoff "
            "silently dropped the artifact (SynchronousOnlyOperation?)"
        )
        assert len(artifacts) == 1, artifacts
        artifact = artifacts[0]
        assert artifact.step_index == 0
        assert artifact.name.endswith(".docx"), artifact.name
        assert artifact.size_bytes > 0, artifact.size_bytes
        with artifact.file.open("rb") as fh:
            assert fh.read(1), "artifact file is empty on disk"

        # ── Gate 2: serialized step payload ──────────────────────────────
        payload = service.get_plan(user, run.id)
        step0 = payload["steps"][0]
        assert step0["output_type"] == "artifact", step0.get("tool_output")
        assert step0["tool_output"]["_output_type"] == "artifact"
        assert len(step0["artifacts"]) == 1, step0
        dl_url = step0["artifacts"][0]["download_url"]
        assert dl_url, "download_url missing from serialized step"

        # ── Gate 3: live frames carry the artifact ───────────────────────
        step_results = [f for f in frames if f["type"] == "step_result"]
        assert step_results, f"no step_result frames: {frames}"
        sr = step_results[0]
        assert sr["output_type"] == "artifact", sr
        assert sr["artifacts"] and sr["artifacts"][0]["download_url"], sr
        assert any(
            f["type"] == "done" and f["status"] == "completed" for f in frames
        ), frames

        # ── Gate 4: GET download_url → 200 + attachment ──────────────────
        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.get(dl_url)
        assert resp.status_code == 200, (resp.status_code, resp.content[:300])
        assert "attachment" in resp.get("Content-Disposition", ""), resp.get(
            "Content-Disposition"
        )
        assert resp.get("Content-Type"), "missing Content-Type"
