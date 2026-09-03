"""Phase H1-B — AI action audit trail tests.

Covers:

* ``ai.tool_call`` — one ``AuditLog`` row per completed tool call surfaced in
  the ``send_message_stream`` completion frame (provider mocked).
* ``ai.consent_approved`` / ``ai.consent_declined`` — consent resolution on the
  workspace confirm/decline tool-execution endpoints.
* ``ai.memory_write`` — fact update in ``memory_api``.
* GET /ai/audit/ — 403 for a non-admin, 200 + filtering + secret redaction for
  an admin.
* ``AuditService.log`` never raises even when the DB write would fail.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.audit_service import AuditService
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AuditLog, MemoryLongTerm, ToolExecution


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="audit-user", password="secret123")


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_superuser(username="audit-admin", password="secret123")


@pytest.fixture
def client():
    return APIClient()


def _conversation(user, conversation_type="chat"):
    return AIConversation.objects.create(
        user=user,
        title="audit chat",
        conversation_type=conversation_type,
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )


def _stage_execution(conversation, user):
    return ToolExecution.objects.create(
        conversation_id=str(conversation.id),
        tool_name="create_dq_rule",
        input_params=json.dumps({"body": {"name": "rule-a"}}),
        status="pending_confirmation",
        confirmed_by_user=False,
        host_user_id=str(user.pk),
    )


class _FakeConfirmExecutor:
    """Stand-in for CarbonHostExecutor — returns a success payload so the
    consent-approve path can be exercised without a live host API."""

    def __init__(self, **kwargs):
        pass

    async def confirm_execution(self, execution_id, expected_host_user_id=None):
        return {"data": {"id": "rule-1", "name": "Test rule"}}


# ── 1. Tool-call completion ─────────────────────────────────────────────


@pytest.mark.django_db
def test_tool_call_completion_writes_audit_rows(user):
    conversation = _conversation(user, "chat")

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat_stream.return_value = [
        ("chunk", "Hi"),
        (
            "done",
            {
                "status": "completed",
                "result": {
                    "content": "Hi",
                    "follow_up_questions": [],
                    "tool_trace": [
                        {"step_label": "Searched", "tool_id": "search_knowledge", "duration_ms": 12},
                        {"step_label": "Looked up", "tool_id": "get_entity_details", "duration_ms": 8},
                    ],
                },
            },
        ),
    ]

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    frames = list(ci.send_message_stream(user, str(conversation.id), "hi"))

    assert frames[-1]["type"] == "done"

    rows = list(AuditLog.objects.filter(action="ai.tool_call"))
    assert len(rows) == 2
    assert {row.detail["tool_id"] for row in rows} == {
        "search_knowledge",
        "get_entity_details",
    }
    # Every row is scoped to the requesting user.
    assert all(row.host_user_id == str(user.pk) for row in rows)


# ── 2. Consent resolution ───────────────────────────────────────────────


@pytest.mark.django_db
def test_consent_approve_writes_audit_row(user, monkeypatch):
    monkeypatch.setattr("ai.host_executor.CarbonHostExecutor", _FakeConfirmExecutor)

    conversation = _conversation(user, "chat")
    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        reverse(
            "ai-workspace-conversation-confirm-tool-execution",
            kwargs={"pk": conversation.id},
        ),
        {"execution_id": execution.id},
        format="json",
    )
    assert response.status_code == 200, response.data

    row = AuditLog.objects.filter(action="ai.consent_approved").first()
    assert row is not None
    assert row.target == str(execution.id)
    assert row.detail["tool_id"] == execution.tool_name
    assert row.detail["consent_token"] == execution.id


@pytest.mark.django_db
def test_consent_decline_writes_audit_row(user):
    conversation = _conversation(user, "chat")
    execution = _stage_execution(conversation, user)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        reverse(
            "ai-workspace-conversation-decline-tool-execution",
            kwargs={"pk": conversation.id},
        ),
        {"execution_id": execution.id},
        format="json",
    )
    assert response.status_code == 200, response.data

    row = AuditLog.objects.filter(action="ai.consent_declined").first()
    assert row is not None
    assert row.target == str(execution.id)
    assert row.detail["tool_id"] == execution.tool_name
    assert row.detail["reason"] == "user_declined"


# ── 3. Memory fact write ────────────────────────────────────────────────


@pytest.mark.django_db
def test_memory_write_audits_fact_update(client, user):
    fact = MemoryLongTerm.objects.create(
        instance_id="carbon",
        category="preference",
        content="old content",
        confidence=0.9,
        visibility="private",
        host_user_id=str(user.pk),
    )

    client.force_authenticate(user=user)
    response = client.patch(
        reverse("ai-memory-fact-update", args=[fact.pk]),
        {"content": "new content"},
        format="json",
    )
    assert response.status_code == 200, response.data

    row = AuditLog.objects.filter(action="ai.memory_write").first()
    assert row is not None
    assert row.target == str(fact.pk)
    assert row.detail["category"] == "preference"
    assert row.detail["confidence"] == 0.9
    assert row.detail["content"] == "new content"


# ── 4/5. Audit list API ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_audit_list_forbidden_for_non_admin(client, user):
    client.force_authenticate(user=user)
    response = client.get(reverse("ai-audit-list"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_audit_list_admin_filtered_and_redacted(client, admin_user):
    AuditLog.objects.create(
        instance_id="carbon",
        actor="u1",
        actor_type="user",
        action="ai.tool_call",
        target="t1",
        detail={"tool_id": "search_knowledge", "api_key": "super-secret-value"},
        host_user_id="1",
        visibility="private",
    )
    AuditLog.objects.create(
        instance_id="carbon",
        actor="u1",
        actor_type="user",
        action="ai.memory_write",
        target="t2",
        detail={"category": "preference"},
        host_user_id="1",
        visibility="private",
    )

    client.force_authenticate(user=admin_user)
    response = client.get(reverse("ai-audit-list"), {"action": "ai.tool_call"})
    assert response.status_code == 200

    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1
    result = response.data["results"][0]
    assert result["action"] == "ai.tool_call"
    assert result["detail"]["tool_id"] == "search_knowledge"
    # Secret-hinting keys are blanked.
    assert result["detail"]["api_key"] == "[REDACTED]"


# ── 6. AuditService never raises ────────────────────────────────────────


def test_audit_service_never_raises_on_db_failure(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(AuditLog.objects, "create", _boom)

    # Must not raise — the audit write failure is swallowed.
    AuditService.log(action="ai.tool_call", actor=1, host_user_id="1")
