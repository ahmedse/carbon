"""Sprint "fly to rule detail" — tool-action surfacing + confirm/decline API.

Covers:
  * deterministic action extraction from executed tools (``_extract_tool_actions``)
  * anti-fabrication grounded outcome note (``_grounded_outcome_note``)
  * Carbon instance config for the engine turn
  * confirm/decline tool-execution endpoints (ownership, status, persistence)
"""
from __future__ import annotations

import json

import pytest

from ai.engine_runtime import (
    _carbon_instance_config,
    _extract_tool_actions,
    _grounded_outcome_note,
)


# ── Unit: action extraction ─────────────────────────────────────────────


def test_extract_tool_actions_navigate():
    tools = [
        {
            "tool_name": "execute_navigate_to",
            "result": json.dumps({
                "action": "navigate",
                "route": "/dq/rules/abc-123",
                "label": "View rule",
                "summary": "Rule found.",
            }),
        },
    ]
    actions, pending = _extract_tool_actions(tools)
    assert len(actions) == 1
    assert actions[0]["type"] == "navigate"
    assert actions[0]["route"] == "/dq/rules/abc-123"
    assert pending == []


def test_extract_tool_actions_pending_confirmation():
    tools = [
        {
            "tool_name": "create_dq_rule",
            "result": json.dumps({
                "requires_confirmation": True,
                "execution_id": "ex-9",
                "proposed_rule": {"name": "employee-number", "type": "range"},
                "validation": {"passed": True},
            }),
        },
    ]
    actions, pending = _extract_tool_actions(tools)
    assert actions == []
    assert len(pending) == 1
    assert pending[0]["execution_id"] == "ex-9"
    assert pending[0]["tool"] == "create_dq_rule"
    assert pending[0]["proposed_rule"]["name"] == "employee-number"


def test_extract_tool_actions_dedupes_navigate_routes():
    tools = [
        {"tool_name": "t", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/a", "label": "A"})},
        {"tool_name": "t", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/a", "label": "A again"})},
        {"tool_name": "t", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/b", "label": "B"})},
    ]
    actions, _ = _extract_tool_actions(tools)
    assert [a["route"] for a in actions] == ["/dq/rules/a", "/dq/rules/b"]


def test_extract_tool_actions_skips_errors_and_bad_json():
    tools = [
        {"tool_name": "t", "error": "boom", "result": None},
        {"tool_name": "t", "result": "not json {{{"},
        {"tool_name": "t", "result": json.dumps({"action": "navigate", "route": " "})},
    ]
    actions, pending = _extract_tool_actions(tools)
    assert actions == []
    assert pending == []


# ── Unit: grounded outcome note (anti-fabrication) ──────────────────────


def test_grounded_note_staged_not_created():
    tools = [
        {
            "tool_name": "create_dq_rule",
            "result": json.dumps({
                "requires_confirmation": True,
                "execution_id": "ex-9",
                "proposed_rule": {"name": "employee-number", "type": "range"},
            }),
        },
    ]
    note = _grounded_outcome_note(tools)
    assert "validated and staged" in note
    assert "nothing was created yet" in note
    assert "Confirm" in note


def test_grounded_note_error_line():
    tools = [{"tool_name": "create_dq_rule", "error": "Rule validation failed"}]
    note = _grounded_outcome_note(tools)
    assert "⚠️" in note
    assert "Rule validation failed" in note


def test_grounded_note_navigate_summary():
    tools = [
        {"tool_name": "execute_navigate_to", "result": json.dumps(
            {"action": "navigate", "route": "/dq/rules/a", "summary": "Opened rule."})},
    ]
    note = _grounded_outcome_note(tools)
    assert "Opened rule." in note


def test_grounded_note_empty():
    assert _grounded_outcome_note([]) == ""


# ── Unit: Carbon instance config ────────────────────────────────────────


def test_carbon_instance_config_includes_host_user_id():
    config = _carbon_instance_config("7")
    assert config["host_user_id"] == "7"
    assert config["display_name"]
    assert any(r["name"] == "dq_rule_detail" for r in config["navigation_routes"])


def test_carbon_instance_config_no_user():
    config = _carbon_instance_config(None)
    assert config["host_user_id"] is None


# ── Endpoint: confirm / decline tool executions ─────────────────────────


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="ai-worker", password="secret123")


@pytest.fixture
def conversation(db, user):
    from ai.models import AIConversation

    return AIConversation.objects.create(
        user=user,
        title="Rule chat",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )


def _stage_execution(conversation, user, *, body=None, status="pending_confirmation"):
    from ai.models import ToolExecution

    execution = ToolExecution.objects.create(
        conversation_id=str(conversation.id),
        tool_name="create_dq_rule",
        input_params=json.dumps({
            "method": "POST",
            "endpoint": "/carbon-api/dq/rules/",
            "params": None,
            "body": body or {
                "name": "employee-number",
                "rule_type": "range",
                "rule_level": "field_validation",
                "severity": "error",
                "dimension": "validity",
                "is_active": True,
                "definition": {
                    "schema_version": 1,
                    "name": "employee-number",
                    "level": "field",
                    "dimension": "validity",
                    "type": "range",
                    "severity": "error",
                    "active": True,
                    "params": {"min": 1000, "max": 9999},
                },
            },
        }),
        status=status,
        confirmed_by_user=False,
        host_user_id=str(user.pk),
    )
    return execution


def _confirm_url(conversation):
    from django.urls import reverse

    return reverse(
        "ai-workspace-conversation-confirm-tool-execution",
        kwargs={"pk": conversation.id},
    )


def _decline_url(conversation):
    from django.urls import reverse

    return reverse(
        "ai-workspace-conversation-decline-tool-execution",
        kwargs={"pk": conversation.id},
    )


@pytest.mark.django_db
def test_confirm_creates_rule_and_appends_grounded_message(user, conversation):
    from rest_framework.test import APIClient

    from ai.models import AIMessage
    from dq.models import DQRule

    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == "confirmed"
    assert response.data["rule_id"]
    assert response.data["action"]["type"] == "navigate"
    assert response.data["action"]["route"] == f"/dq/rules/{response.data['rule_id']}"

    # The rule really exists.
    rule = DQRule.objects.get(pk=response.data["rule_id"])
    assert rule.name == "employee-number"
    assert rule.rule_type == "range"

    # The staged execution transitioned.
    execution.refresh_from_db()
    assert execution.status == "confirmed"
    assert execution.confirmed_by_user is True

    # A grounded assistant message with the navigate action was appended.
    messages = AIMessage.objects.filter(conversation=conversation, role="assistant")
    assert messages.exists()
    last = messages.order_by("-created_at").first()
    assert "created" in (last.content or "").lower()
    assert last.metadata_json["action"]["route"] == f"/dq/rules/{rule.pk}"


@pytest.mark.django_db
def test_decline_marks_execution_declined_and_appends_message(user, conversation):
    from rest_framework.test import APIClient

    from ai.models import AIMessage

    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _decline_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == "declined"

    execution.refresh_from_db()
    assert execution.status == "declined"

    messages = AIMessage.objects.filter(conversation=conversation, role="assistant")
    assert messages.exists()
    assert "nothing was created" in messages.order_by("-created_at").first().content


@pytest.mark.django_db
def test_confirm_rejects_other_users_execution(user, conversation):
    from accounts.models import User
    from rest_framework.test import APIClient

    other = User.objects.create_user(username="other-user", password="secret123")
    execution = _stage_execution(conversation, other)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_confirm_rejects_non_pending_execution(user, conversation):
    from rest_framework.test import APIClient

    execution = _stage_execution(conversation, user, status="confirmed")

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_confirm_404_when_execution_not_in_conversation(user, conversation):
    from ai.models import AIConversation
    from rest_framework.test import APIClient

    other_conv = AIConversation.objects.create(
        user=user,
        title="Other",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )
    execution = _stage_execution(other_conv, user)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        _confirm_url(conversation),
        {"execution_id": execution.id},
        format="json",
    )

    assert response.status_code == 404
