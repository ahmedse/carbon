"""Agent bank S4 CI gates — heartbeat + unified audit export.

Sprint S4 (QA-CHAT-AGENTIC-SCENARIO-BANK): metabolism P0 + audit completeness.
Extends existing oracles only — ``run_pulse_maintenance``, ``PulseHeartbeat``,
``GET /ai/pulse/sweeps/``, ``AuditService`` / consent audit rows, ``GET /ai/audit/``.
Does **not** invent a second export API (AuditPanel CSV consumes the list).

Bank IDs: PA-071 · PA-091 · PA-240 · unified audit export contract.

Run::

    cd backend && ../.venv/bin/python -m pytest ai/tests/test_agent_bank_s4_gates.py -q
"""

from __future__ import annotations

import json
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from ai.audit_service import AuditService
from ai.models import AIConversation, AuditLog, PulseHeartbeat, ToolExecution
from ai.models.core import Instance

# Columns AuditPanel Export CSV expects (unified export contract).
AUDIT_EXPORT_FIELDS = ("timestamp", "actor", "action", "target", "detail")


@pytest.fixture
def seeded_instance(db):
    return Instance.objects.create(
        id="nibras",
        name="nibras",
        display_name="Nibras",
        host_db_url="postgres://localhost/nibras_dev",
        host_api_url="https://nibras.local",
        status="active",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username=f"s4-admin-{uuid4().hex[:6]}", password="secret123"
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username=f"s4-user-{uuid4().hex[:6]}", password="secret123"
    )


class _FakeConfirmExecutor:
    def __init__(self, **kwargs):
        pass

    async def confirm_execution(self, execution_id, expected_host_user_id=None):
        return {"data": {"id": "rule-1", "name": "Test rule"}}

    async def decline_execution(self, execution_id, expected_host_user_id=None):
        return {"ok": True}


def _conversation(owner):
    return AIConversation.objects.create(
        user=owner,
        title="s4 audit",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )


def _stage_execution(conversation, owner):
    return ToolExecution.objects.create(
        conversation_id=str(conversation.id),
        tool_name="create_dq_rule",
        input_params=json.dumps({"body": {"name": "rule-s4"}}),
        status="pending_confirmation",
        confirmed_by_user=False,
        host_user_id=str(owner.pk),
    )


def _csv_from_audit_rows(rows: list[dict]) -> str:
    """Mirror AuditPanel.handleExportCsv field set (no FE dependency)."""

    def _field(value):
        s = "" if value is None else str(value)
        return f'"{s.replace(chr(34), chr(34)+chr(34))}"'

    lines = [",".join(AUDIT_EXPORT_FIELDS)]
    for row in rows:
        lines.append(
            ",".join(
                _field(row.get(k) if k != "detail" else json.dumps(row.get("detail") or {}))
                for k in AUDIT_EXPORT_FIELDS
            )
        )
    return "\n".join(lines)


# ── PA-071 Heartbeat tick recorded ────────────────────────────────────────


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_pa071_heartbeat_tick_recorded(monkeypatch, seeded_instance):
    """PA-071: maintenance run writes terminal PulseHeartbeat rows per loop."""
    from ai.management.commands.run_pulse_maintenance import Command

    monkeypatch.setattr(Command, "_run_loop", lambda self, **kw: 1)
    call_command("run_pulse_maintenance", stdout=StringIO())

    rows = list(PulseHeartbeat.objects.filter(instance_id="nibras"))
    assert len(rows) == 4
    assert {r.loop for r in rows} == {"proactive", "consolidation", "distill", "decay"}
    assert all(r.status == "ok" for r in rows)
    assert all(r.finished_at is not None for r in rows)


@pytest.mark.django_db
def test_pa071_sweeps_exposes_latest_heartbeats(admin_user, seeded_instance):
    """PA-071 health surface: GET sweeps/ includes heartbeats[] (existing API)."""
    now = timezone.now()
    PulseHeartbeat.objects.create(
        instance_id="nibras",
        loop="consolidation",
        started_at=now,
        finished_at=now,
        status="ok",
        items_produced=2,
    )
    client = APIClient()
    client.force_authenticate(user=admin_user)
    resp = client.get(reverse("ai-pulse-sweeps"))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "heartbeats" in body
    hits = [
        h for h in body["heartbeats"]
        if h.get("instance_id") == "nibras" and h.get("loop") == "consolidation"
    ]
    assert hits, body.get("heartbeats")
    assert hits[0]["status"] == "ok"
    assert hits[0]["items_produced"] == 2


# ── PA-091 / PA-240 Audit ledger completeness + export ────────────────────


@pytest.mark.django_db
def test_pa091_confirm_and_deny_both_leave_audit_rows(user, monkeypatch):
    """PA-091 / PA-240: every confirm and deny writes an AuditLog row."""
    monkeypatch.setattr("ai.host_executor.CarbonHostExecutor", _FakeConfirmExecutor)
    client = APIClient()
    client.force_authenticate(user=user)

    conv_ok = _conversation(user)
    exec_ok = _stage_execution(conv_ok, user)
    approve = client.post(
        reverse(
            "ai-workspace-conversation-confirm-tool-execution",
            kwargs={"pk": conv_ok.id},
        ),
        {"execution_id": exec_ok.id},
        format="json",
    )
    assert approve.status_code == 200, approve.data
    approved = AuditLog.objects.filter(action="ai.consent_approved").first()
    assert approved is not None
    assert approved.actor
    assert approved.detail.get("tool_id") == exec_ok.tool_name
    # target may be PII-scrubbed (UUID segments can match civil_id heuristics)
    assert approved.target

    conv_no = _conversation(user)
    exec_no = _stage_execution(conv_no, user)
    decline = client.post(
        reverse(
            "ai-workspace-conversation-decline-tool-execution",
            kwargs={"pk": conv_no.id},
        ),
        {"execution_id": exec_no.id},
        format="json",
    )
    assert decline.status_code == 200, decline.data
    declined = AuditLog.objects.filter(action="ai.consent_declined").first()
    assert declined is not None
    assert declined.detail.get("tool_id") == exec_no.tool_name
    assert declined.detail.get("reason") == "user_declined"
    assert declined.target


@pytest.mark.django_db
def test_s4_unified_audit_list_export_contract(admin_user):
    """S4: GET /ai/audit/ returns fields AuditPanel CSV export consumes."""
    AuditService.log(
        action="ai.consent_approved",
        actor="s4-actor",
        actor_type="user",
        target="exec-1",
        detail={"tool_id": "create_dq_rule", "api_key": "should-redact"},
        instance_id="nibras",
        host_user_id="1",
        visibility="private",
    )
    client = APIClient()
    client.force_authenticate(user=admin_user)
    resp = client.get(reverse("ai-audit-list"))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["count"] >= 1
    row = body["results"][0]
    for key in AUDIT_EXPORT_FIELDS:
        assert key in row, f"export contract missing {key}"

    # Secrets redacted before they leave the process (export-safe).
    assert row["detail"].get("api_key") == "[REDACTED]"

    csv = _csv_from_audit_rows(body["results"])
    assert csv.startswith("timestamp,actor,action,target,detail")
    assert "ai.consent_approved" in csv
    assert "should-redact" not in csv
    assert "[REDACTED]" in csv


@pytest.mark.django_db
def test_s4_audit_service_is_single_write_path():
    """S4 unification: AuditService.log persists the row used by export."""
    before = AuditLog.objects.count()
    AuditService.log(
        action="ai.tool_call",
        actor="s4-unify",
        actor_type="user",
        target="t-s4",
        detail={"tool_id": "search_knowledge"},
        instance_id="nibras",
        host_user_id="9",
        visibility="private",
    )
    assert AuditLog.objects.count() == before + 1
    row = AuditLog.objects.filter(actor="s4-unify").latest("created_at")
    assert row.action == "ai.tool_call"
    assert row.detail["tool_id"] == "search_knowledge"
