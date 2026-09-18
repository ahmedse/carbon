"""ADR-0041 Ops Canvas / Job Map unit tests."""
from __future__ import annotations

import pytest

from ai.ops_canvas import (
    ARTIFACT_TYPE,
    MODE_AGENT,
    MODE_CHAT,
    build_payload,
    empty_layers,
    layers_from_envelope_and_tools,
    layers_from_plan,
    should_emit_chat_brief,
)


def test_empty_layers_have_five_keys():
    layers = empty_layers(mode=MODE_CHAT, ask="headcount")
    assert set(layers) == {"intent", "job_map", "live_run", "evidence", "outcome"}
    assert layers["intent"]["ask"] == "headcount"
    assert layers["intent"]["contract"] == "advisory"


def test_should_emit_skips_short_lookup():
    assert should_emit_chat_brief(tool_count=1, has_envelope=False) is False
    assert should_emit_chat_brief(tool_count=2) is True
    assert should_emit_chat_brief(tool_count=0, user_asked_map=True) is True


def test_layers_from_plan_steps():
    layers = layers_from_plan(
        {
            "brief": "Onboard leave audit",
            "steps": [
                {"id": 1, "title": "Resolve employee", "tool_name": "resolve_entity"},
                {"id": 2, "title": "List leave", "tool_name": "list_leave_entitlements", "depends_on": [1]},
            ],
        }
    )
    assert layers["intent"]["ask"] == "Onboard leave audit"
    assert len(layers["job_map"]["steps"]) == 2
    assert "resolve_entity" in layers["job_map"]["tools"]


def test_layers_from_envelope_and_tools():
    layers = layers_from_envelope_and_tools(
        ask="leave for 1416",
        envelope={"headline": "Five leave types", "tables": [{"title": "T", "rows": []}]},
        tool_trace=[
            {"tool": "resolve_entity", "step_label": "Resolve"},
            {"tool": "list_leave_entitlements", "step_label": "Leave"},
        ],
    )
    assert layers["evidence"]["headline"] == "Five leave types"
    assert layers["live_run"]["progress_pct"] == 100
    assert len(layers["job_map"]["steps"]) == 2


def test_build_payload_kind():
    payload = build_payload(mode=MODE_AGENT, ask="run payroll check", title="Payroll")
    assert payload["kind"] == "job_map"
    assert payload["mode"] == MODE_AGENT
    assert payload["title"] == "Payroll"
    assert ARTIFACT_TYPE == "job_map"


@pytest.mark.django_db
def test_upsert_and_share_job_map(django_user_model):
    from ai.models import AIConversation
    from ai.ops_canvas import build_payload, issue_share_token, upsert_job_map_artifact

    user = django_user_model.objects.create_user(username="ops-canvas", password="x")
    conv = AIConversation.objects.create(
        user=user,
        conversation_type="chat",
        title="ops",
        status="active",
    )
    payload = build_payload(mode=MODE_CHAT, ask="map leave", conversation_id=str(conv.id))
    art = upsert_job_map_artifact(
        user=user,
        conversation_id=str(conv.id),
        title="Leave Job Brief",
        payload=payload,
    )
    assert art["artifact_type"] == "job_map"
    assert art["content_json"]["layers"]["outcome"]["canvas_id"] == art["id"]

    from ai.models import AIArtifact

    row = AIArtifact.objects.get(id=art["id"])
    token = issue_share_token(row)
    assert token
    row.refresh_from_db()
    assert row.visibility == "shared"
    assert row.content_json["share"]["token"] == token


@pytest.mark.django_db
def test_patch_live_run_qos_from_acceptance(django_user_model):
    from ai.models import AIArtifact, AIConversation
    from ai.ops_canvas import MODE_AGENT, build_payload, patch_live_run_qos

    user = django_user_model.objects.create_user(username="ops-qos", password="x")
    conv = AIConversation.objects.create(
        user=user,
        conversation_type="agent",
        title="qos",
        status="active",
    )
    plan_id = "plan-qos-1"
    payload = build_payload(
        mode=MODE_AGENT,
        ask="run audit",
        conversation_id=str(conv.id),
        plan_id=plan_id,
        title="Agent Job Map",
    )
    art = AIArtifact.objects.create(
        conversation=conv,
        created_by=user,
        title="Agent Job Map",
        artifact_type="job_map",
        content_json=payload,
        visibility="private",
    )
    n = patch_live_run_qos(
        conversation_id=str(conv.id),
        plan_id=plan_id,
        acceptance={
            "status": "met",
            "requirements_total": 2,
            "requirements_met": 2,
            "requirements_partial": 0,
            "requirements_missed": 0,
        },
    )
    assert n == 1
    art.refresh_from_db()
    live = art.content_json["layers"]["live_run"]
    assert live["qos"]["acceptance_status"] == "met"
    assert live["status"] == "completed"
    assert live["progress_pct"] == 100
