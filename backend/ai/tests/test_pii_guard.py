"""Wave I5-B — PII server-side gate tests.

Covers the pure :class:`ai.pii_guard.PIIGuard` redaction primitives and the
three integration points: auto-memory persistence, audit writes, and the
insights read layer.  The pure tests need no Django DB; the integration tests
reuse the established fixture patterns from ``test_audit_trail.py`` /
``test_insights_api.py``.
"""

from __future__ import annotations

import json
import types
from unittest.mock import AsyncMock

import pytest
from django.utils import timezone

from ai.audit_service import AuditService
from ai.engine.cognition.auto_memory import AutoMemoryExtractor
from ai.engine.memory.long_term import LongTermMemory
from ai.insights_api import _serialize_insight
from ai.models import AuditLog
from ai.pii_guard import PIIGuard


# ── 1-5. Pure text redaction ────────────────────────────────────────────


def test_redact_civil_id():
    out = PIIGuard.redact("civil 123456789012 ok")
    assert "[REDACTED:civil_id]" in out
    assert "123456789012" not in out


def test_redact_passport():
    out = PIIGuard.redact("passport A12345678 ok")
    assert "[REDACTED:passport]" in out


def test_redact_email():
    out = PIIGuard.redact("mail me a@b.co")
    assert "[REDACTED:email]" in out


def test_redact_preserves_short_numbers():
    out = PIIGuard.redact("emissions 142 tCO2e, phone 5551234")
    assert "142" in out
    assert "5551234" in out
    assert "[REDACTED:civil_id]" not in out


def test_redact_non_pii_passthrough():
    text = "normal text about emissions scope 1 and 2"
    assert PIIGuard.redact(text) == text


# ── 6-7. Structured redaction ────────────────────────────────────────────


def test_redact_nested_dict_keys():
    out = PIIGuard.redact_dict(
        {"civil_id": "123456789012", "notes": {"email": "a@b.co", "ok": "fine"}}
    )
    assert out["civil_id"] == "[REDACTED:civil_id]"
    assert out["notes"]["email"] == "[REDACTED:email]"
    assert out["notes"]["ok"] == "fine"


def test_redact_dict_does_not_mutate_input():
    original = {"civil_id": "123456789012", "notes": {"email": "a@b.co"}}
    PIIGuard.redact_dict(original)
    assert original == {"civil_id": "123456789012", "notes": {"email": "a@b.co"}}


# ── 8. Auto-memory redacts before persistence ────────────────────────────


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_auto_memory_redacts_before_store(monkeypatch):
    monkeypatch.setattr(
        "ai.engine.cognition.auto_memory.route_chat",
        AsyncMock(return_value={"content": "context"}),
    )
    store_fact = AsyncMock()
    monkeypatch.setattr(LongTermMemory, "store_fact", store_fact)

    await AutoMemoryExtractor.try_extract("my civil id is 123456789012", "carbon", "1", None)

    store_fact.assert_called_once()
    content = store_fact.call_args.kwargs["content"]
    assert "[REDACTED:civil_id]" in content
    assert "123456789012" not in content


# ── 9. Audit service redacts detail before write ─────────────────────────


@pytest.mark.django_db
def test_audit_service_redacts_detail():
    AuditService.log(
        action="ai.memory_write",
        actor=1,
        host_user_id="1",
        detail={"content": "civil 123456789012"},
    )

    row = AuditLog.objects.filter(action="ai.memory_write").first()
    assert row is not None
    assert "[REDACTED:civil_id]" in row.detail["content"]
    assert "123456789012" not in row.detail["content"]


# ── 10. Insights serializer redacts narrative ────────────────────────────


def test_serialize_insight_redacts_narrative():
    insight = types.SimpleNamespace(
        id="insight-1",
        title="Test insight",
        narrative="civil 123456789012",
        severity="warning",
        insight_type="threshold_alert",
        recommended_actions_json=json.dumps(["act"]),
        context_json=json.dumps({"table": "x"}),
        disposition="pending",
        created_at=timezone.now(),
    )

    out = _serialize_insight(insight)

    assert "[REDACTED:civil_id]" in out["narrative"]
    assert "123456789012" not in out["narrative"]
