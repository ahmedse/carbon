"""Phase 5 — proactive suggestions + resume catch-up tests.

Covers:
  * ``list_proactive_suggestions`` (CBAC scoping, pending/unexpired filter)
  * ``resume_conversation`` (last_viewed_at bump, >24h catch-up summary)
  * catch-up summary content: memory facts, suggestions, DQ violations, anomalies
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import (
    AIConversation,
    KgProactiveInsight,
    MemoryLongTerm,
)
from core.models import Module
from dataschema.models import DataTable
from dq.models import DQAnomaly, DQResult, DQRule
from mdm.models import OrgUnit


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="proactive-worker", password="secret123")


def _make_conversation(user, scope_json=None) -> AIConversation:
    return AIConversation.objects.create(
        user=user,
        title="chat",
        conversation_type="chat",
        task_payload_json={},
        scope_json=scope_json or {},
    )


# ── 1. proactive suggestions ────────────────────────────────────────────


@pytest.mark.django_db
def test_list_proactive_suggestions_pending_unexpired_and_scoped(user):
    ci = CarbonIntelligence()

    # Visible: pending, unexpired, shared.
    KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Visible suggestion",
        narrative="do the thing",
        severity="warning",
        insight_type="threshold_alert",
        disposition="pending",
        visibility="shared",
        recommended_actions_json=["a"],
    )
    # Expired → excluded.
    KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Expired suggestion",
        narrative="stale",
        severity="info",
        disposition="pending",
        visibility="shared",
        expires_at=timezone.now() - timedelta(hours=1),
    )
    # Already dismissed → excluded.
    KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Dismissed suggestion",
        narrative="gone",
        severity="info",
        disposition="dismissed",
        visibility="shared",
    )
    # Another user's private suggestion → excluded.
    KgProactiveInsight.objects.create(
        instance_id="carbon",
        title="Other private",
        narrative="secret",
        severity="critical",
        disposition="pending",
        visibility="private",
        host_user_id="99999",
    )

    suggestions = ci.list_proactive_suggestions(user)

    assert len(suggestions) == 1
    assert suggestions[0]["title"] == "Visible suggestion"
    assert suggestions[0]["severity"] == "warning"
    assert suggestions[0]["recommended_actions"] == ["a"]
    assert set(suggestions[0].keys()) == {
        "id", "severity", "title", "narrative", "insight_type",
        "recommended_actions", "context", "created_at",
    }


@pytest.mark.django_db
def test_list_proactive_suggestions_verifies_conversation_access(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user)

    result = ci.list_proactive_suggestions(user, conversation_id=str(conversation.id))
    assert result == []

    with pytest.raises(ValueError):
        ci.list_proactive_suggestions(user, conversation_id="00000000-0000-0000-0000-000000000000")


# ── 2. resume catch-up ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_resume_returns_catch_up_after_24h(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user)

    since = timezone.now() - timedelta(hours=25)
    conversation.last_viewed_at = since
    conversation.save(update_fields=["last_viewed_at"])

    # New durable memory fact + proactive suggestion since the last view.
    MemoryLongTerm.objects.create(
        instance_id="carbon", category="learned", content="user likes CSV",
        confidence=1.0, host_user_id=str(user.pk), visibility="private",
    )
    KgProactiveInsight.objects.create(
        instance_id="carbon", title="New suggestion", narrative="act now",
        disposition="pending", visibility="shared",
    )

    result = ci.resume_conversation(user, str(conversation.id))

    assert result["conversation"]["id"] == str(conversation.id)
    assert result["conversation"]["last_viewed_at"] is not None
    assert result["catch_up"] is not None

    catch_up = result["catch_up"]
    assert catch_up["hours_since_last_view"] >= 24
    assert catch_up["new_memory_facts"] == 1
    assert catch_up["new_suggestions"] == 1
    assert catch_up["new_dq_violations"] == 0
    assert catch_up["new_anomalies"] == 0
    assert any("memory fact" in line for line in catch_up["summary_lines"])
    assert any("suggestion" in line for line in catch_up["summary_lines"])

    conversation.refresh_from_db()
    assert conversation.last_viewed_at >= since + timedelta(hours=25)


@pytest.mark.django_db
def test_resume_no_catch_up_when_recent(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user)
    conversation.last_viewed_at = timezone.now() - timedelta(hours=1)
    conversation.save(update_fields=["last_viewed_at"])

    result = ci.resume_conversation(user, str(conversation.id))
    assert result["catch_up"] is None


@pytest.mark.django_db
def test_resume_no_catch_up_on_first_open(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user)  # last_viewed_at=None

    result = ci.resume_conversation(user, str(conversation.id))
    assert result["catch_up"] is None

    conversation.refresh_from_db()
    assert conversation.last_viewed_at is not None


@pytest.mark.django_db
def test_resume_catch_up_counts_dq_and_anomalies_global(user):
    ci = CarbonIntelligence()
    # Global scope → DQ/anomaly counts are not org-filtered.
    conversation = _make_conversation(user, scope_json={"org_unit_ids": ["*"]})
    conversation.last_viewed_at = timezone.now() - timedelta(hours=25)
    conversation.save(update_fields=["last_viewed_at"])

    org_unit = OrgUnit.objects.create(name="OU", code="OU", org_type="division")
    module = Module.objects.create(name="M", org_unit=org_unit)
    table = DataTable.objects.create(name="t", title="T", module=module)
    rule = DQRule.objects.create(
        name="r", rule_level="field_validation", rule_type="not_null",
        severity="error", is_active=True,
    )
    DQResult.objects.create(rule=rule, status="failed")
    DQAnomaly.objects.create(data_table=table, metric="row_count", observed=999.0)

    result = ci.resume_conversation(user, str(conversation.id))
    catch_up = result["catch_up"]

    assert catch_up["new_dq_violations"] == 1
    assert catch_up["new_anomalies"] == 1
    assert any("DQ violation" in line for line in catch_up["summary_lines"])
    assert any("anomal" in line for line in catch_up["summary_lines"])


@pytest.mark.django_db
def test_resume_unknown_conversation_raises(user):
    ci = CarbonIntelligence()
    with pytest.raises(ValueError):
        ci.resume_conversation(user, "00000000-0000-0000-0000-000000000000")
