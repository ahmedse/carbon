"""P2-09 — Audit trail unification.

One write path: ``AuditService.log`` is the single seam that both persists an
``AuditLog`` row and emits the ``AI_AUDIT`` structured log line. ``AuditTrail.log``
is a thin delegating wrapper, so guard-chain call sites still work unchanged
while routing through the same path.

These tests prove:

* ``AuditService.log`` writes a row AND emits an ``AI_AUDIT`` log line.
* ``AuditTrail.log`` (with a real ``Scope``) results in a written ``AuditLog``
  row AND an ``AI_AUDIT`` log line (delegation to the single path).
"""

from __future__ import annotations

import json
import logging

import pytest

from ai.audit_service import AuditService
from ai.guards import AuditTrail
from ai.models import AuditLog
from ai.protocol import Scope

AUDIT_LOGGER = "ai.audit"


def _parse_ai_audit(caplog) -> dict:
    """Return the first ``AI_AUDIT`` payload emitted to ``ai.audit`` as a dict."""
    messages = [
        r.getMessage() for r in caplog.records
        if r.name == AUDIT_LOGGER and r.getMessage().startswith("AI_AUDIT ")
    ]
    assert messages, "expected an AI_AUDIT structured log line"
    payload = messages[-1][len("AI_AUDIT "):]
    return json.loads(payload)


@pytest.mark.django_db(transaction=True)
def test_audit_service_log_writes_row_and_emits_log(caplog):
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)

    AuditService.log(
        action="ai.tool_call",
        actor="user-42",
        actor_type="user",
        target="rule-1",
        detail={"tool_id": "search_knowledge"},
        instance_id="carbon",
        host_user_id="42",
        visibility="private",
    )

    row = AuditLog.objects.get(action="ai.tool_call")
    assert row.actor == "user-42"
    assert row.actor_type == "user"
    assert row.target == "rule-1"
    assert row.detail == {"tool_id": "search_knowledge"}
    assert row.instance_id == "carbon"
    assert row.host_user_id == "42"
    assert row.visibility == "private"

    record = _parse_ai_audit(caplog)
    assert record["action"] == "ai.tool_call"
    assert record["actor"] == "user-42"
    assert record["actor_type"] == "user"
    assert record["target"] == "rule-1"
    assert record["detail"] == {"tool_id": "search_knowledge"}
    assert record["instance_id"] == "carbon"
    assert record["host_user_id"] == "42"
    assert record["visibility"] == "private"
    # Timestamp is ISO 8601 (UTC, ends with +00:00).
    assert record["timestamp"].endswith("+00:00")


@pytest.mark.django_db(transaction=True)
def test_audit_service_log_emits_log_even_when_row_fails(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)

    def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(AuditLog.objects, "create", _boom)

    # Must not raise, and the AI_AUDIT log line must still be emitted.
    AuditService.log(
        action="ai.tool_call",
        actor="user-42",
        instance_id="carbon",
        host_user_id="42",
    )

    assert AuditLog.objects.count() == 0
    record = _parse_ai_audit(caplog)
    assert record["action"] == "ai.tool_call"
    assert record["instance_id"] == "carbon"


@pytest.mark.django_db(transaction=True)
def test_audit_trail_log_delegates_to_single_path(caplog):
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)

    scope = Scope(
        user_identifier="user-7",
        app_identifier="emissions",
        org_unit_ids=["*"],
        is_read_only=True,
    )

    AuditTrail.log(
        scope,
        "emissions.explain",
        "dummy-provider",
        123,
        "completed",
        request_fingerprint="fp-abc",
    )

    row = AuditLog.objects.get(action="emissions.explain")
    assert row.actor == "user-7"
    assert row.actor_type == "user"
    assert row.instance_id == "emissions"
    assert row.host_user_id == "user-7"
    assert row.visibility == "private"
    assert row.detail["provider_name"] == "dummy-provider"
    assert row.detail["latency_ms"] == 123
    assert row.detail["status"] == "completed"
    assert row.detail["error_message"] is None
    assert row.detail["request_fingerprint"] == "fp-abc"
    assert row.detail["scope_snapshot"]["user_identifier"] == "user-7"
    assert row.detail["scope_snapshot"]["app_identifier"] == "emissions"

    record = _parse_ai_audit(caplog)
    assert record["action"] == "emissions.explain"
    assert record["actor"] == "user-7"
    assert record["instance_id"] == "emissions"
    assert record["host_user_id"] == "user-7"
    assert record["detail"]["provider_name"] == "dummy-provider"
    assert record["detail"]["scope_snapshot"]["app_identifier"] == "emissions"
