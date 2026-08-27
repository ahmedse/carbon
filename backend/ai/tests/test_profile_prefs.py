"""Phase 22-A — user preference (AIUserProfile) tests.

Covers:

* preference field defaults (temperature 0.3, auto_title, memory_enabled,
  usage_alert_threshold 80, default_model_id null)
* GET /ai/profile/ — auth required + resolved effective defaults (system
  default inherited when the profile sets no model preference)
* PATCH /ai/profile/ — upsert + validation bounds (temperature 0.0-2.0,
  usage_alert_threshold 1-100, unknown catalog model rejected, null clears)
* resolution order (system default → domain manifest → user profile →
  per-message override): per-message wins over profile, profile beats domain
  manifest, domain manifest beats the system default
* send_message resolves the profile default into the ChatRequest (model +
  temperature), per-message model still wins
* auto_title preference gates auto-titling
* memory_enabled preference gates the T4 memory tier in assemble_context
* usage_alert_threshold overrides the soft-warning percent in quota_snapshot
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import MagicMock, patch

from accounts.models import User
from ai.context_assembler import assemble_context
from ai.intelligence import CarbonIntelligence
from ai.models import (
    AIConversation,
    AIMessage,
    AIUserProfile,
    MemoryLongTerm,
    ModelCatalog,
)
from ai.usage_service import AIUsage
from ai.protocol import ChatResponse, Scope


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="prefs-worker", password="secret123")


def _model(**overrides) -> ModelCatalog:
    base = {
        "model_id": "claude-haiku-4.5",
        "display_name": "Claude Haiku 4.5",
        "description": "Fast test model.",
        "tier": "fast",
        "version": "anthropic/claude-haiku-4.5",
        "context_window": 200000,
        "input_cost_per_1m": "1.00",
        "output_cost_per_1m": "5.00",
        "deprecated": False,
        "capabilities": [],
    }
    base.update(overrides)
    return ModelCatalog.objects.create(**base)


@pytest.fixture
def catalog(db):
    ModelCatalog.objects.all().delete()
    haiku = _model()
    brain = _model(
        model_id="gpt-4o", display_name="GPT-4o", tier="brain",
        version="openai/gpt-4o",
        input_cost_per_1m="2.50", output_cost_per_1m="10.00",
    )
    return {"haiku": haiku, "brain": brain}


def _make_conversation(user, conversation_type="chat", title="Chat"):
    return AIConversation.objects.create(
        user=user,
        title=title,
        conversation_type=conversation_type,
        task_payload_json={},
        scope_json={},
    )


def _history_dicts(conversation):
    return list(
        conversation.messages.order_by("created_at").values(
            "role", "content", "created_at",
        )
    )


# ── model defaults ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_preference_defaults(user):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    assert profile.temperature == 0.3
    assert profile.auto_title is True
    assert profile.memory_enabled is True
    assert profile.usage_alert_threshold == 80
    assert profile.default_model_id_id is None


# ── GET /ai/profile/ ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_endpoint_requires_auth(db):
    client = APIClient()
    assert client.get(reverse("ai-user-profile")).status_code == 401
    assert client.patch(
        reverse("ai-user-profile"), {"temperature": 0.5}, format="json"
    ).status_code == 401


@pytest.mark.django_db
def test_profile_get_returns_resolved_effective_defaults(user):
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get(reverse("ai-user-profile"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model_id"] is None
    assert data["temperature"] == 0.3
    assert data["auto_title"] is True
    assert data["memory_enabled"] is True
    assert data["usage_alert_threshold"] == 80
    # Inherited system default is reported so the UI can render it.
    from ai.engine.llm.router import get_model_for_task

    assert data["resolved_model_id"] == get_model_for_task("chat")


@pytest.mark.django_db
def test_profile_get_reflects_stored_preferences(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.default_model_id = catalog["haiku"]
    profile.temperature = 0.7
    profile.auto_title = False
    profile.memory_enabled = False
    profile.usage_alert_threshold = 50
    profile.save()

    client = APIClient()
    client.force_authenticate(user=user)
    data = client.get(reverse("ai-user-profile")).json()
    assert data["default_model_id"] == "claude-haiku-4.5"
    assert data["resolved_model_id"] == "claude-haiku-4.5"
    assert data["temperature"] == 0.7
    assert data["auto_title"] is False
    assert data["memory_enabled"] is False
    assert data["usage_alert_threshold"] == 50


# ── PATCH /ai/profile/ ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_patch_upserts_and_returns_stored(user, catalog):
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.patch(
        reverse("ai-user-profile"),
        {
            "default_model_id": "gpt-4o",
            "temperature": 0.7,
            "auto_title": False,
            "memory_enabled": False,
            "usage_alert_threshold": 50,
        },
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_model_id"] == "gpt-4o"
    assert data["resolved_model_id"] == "gpt-4o"
    assert data["temperature"] == 0.7
    assert data["usage_alert_threshold"] == 50

    profile = AIUserProfile.objects.get(user=user)
    assert profile.default_model_id.model_id == "gpt-4o"
    assert profile.temperature == 0.7
    assert profile.auto_title is False
    assert profile.memory_enabled is False
    assert profile.usage_alert_threshold == 50


@pytest.mark.django_db
def test_profile_patch_validates_temperature_bounds(user):
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.patch(
        reverse("ai-user-profile"), {"temperature": 2.5}, format="json"
    ).status_code == 400
    assert client.patch(
        reverse("ai-user-profile"), {"temperature": -0.1}, format="json"
    ).status_code == 400


@pytest.mark.django_db
def test_profile_patch_validates_threshold_bounds(user):
    client = APIClient()
    client.force_authenticate(user=user)

    assert client.patch(
        reverse("ai-user-profile"), {"usage_alert_threshold": 0}, format="json"
    ).status_code == 400
    assert client.patch(
        reverse("ai-user-profile"), {"usage_alert_threshold": 101}, format="json"
    ).status_code == 400


@pytest.mark.django_db
def test_profile_patch_rejects_unknown_model(user):
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.patch(
        reverse("ai-user-profile"), {"default_model_id": "not-a-model"}, format="json"
    )
    assert resp.status_code == 400
    # The platform wraps DRF validation errors in an {error, message} envelope.
    body = resp.json()
    assert "default_model_id" in body["message"]


@pytest.mark.django_db
def test_profile_patch_clears_default_model(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.default_model_id = catalog["haiku"]
    profile.save()

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.patch(
        reverse("ai-user-profile"), {"default_model_id": None}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["default_model_id"] is None
    profile.refresh_from_db()
    assert profile.default_model_id_id is None


# ── resolution order (system → domain manifest → profile → per-message) ─


@pytest.mark.django_db
def test_resolution_per_message_beats_profile(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.default_model_id = catalog["haiku"]
    profile.save()

    ci = CarbonIntelligence()
    # Per-message override is the highest tier — wins over the profile.
    assert ci._resolve_preferred_model(user, "gpt-4o", "emissions") == "gpt-4o"
    # No per-message override → profile default wins.
    assert ci._resolve_preferred_model(user, None, "emissions") == "claude-haiku-4.5"


@pytest.mark.django_db
def test_resolution_profile_beats_domain_manifest(user, catalog, monkeypatch):
    from ai.domain.emissions import EmissionsDomainAI

    monkeypatch.setattr(EmissionsDomainAI, "default_model_id", "gpt-4o")
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.default_model_id = catalog["haiku"]
    profile.save()

    ci = CarbonIntelligence()
    # Profile default wins over the domain manifest default.
    assert ci._resolve_preferred_model(user, None, "emissions") == "claude-haiku-4.5"


@pytest.mark.django_db
def test_resolution_domain_manifest_beats_system_default(user, monkeypatch):
    from ai.domain.emissions import EmissionsDomainAI

    monkeypatch.setattr(EmissionsDomainAI, "default_model_id", "gpt-4o")
    ci = CarbonIntelligence()
    # No profile preference → the domain manifest default is used.
    assert ci._resolve_preferred_model(user, None, "emissions") == "gpt-4o"
    # No manifest opinion either → None → engine falls back to system default.
    assert ci._resolve_preferred_model(user, None, None) is None


@pytest.mark.django_db
def test_resolve_preferred_temperature(user):
    ci = CarbonIntelligence()
    assert ci._resolve_preferred_temperature(user) is None

    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.temperature = 0.7
    profile.save()
    assert ci._resolve_preferred_temperature(user) == 0.7


# ── send_message resolution integration ─────────────────────────────────


@pytest.mark.django_db
def test_send_message_uses_profile_model_and_temperature(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.default_model_id = catalog["haiku"]
    profile.temperature = 0.9
    profile.save()

    ci = CarbonIntelligence()
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    scope = Scope(user_identifier=str(user.pk), is_superuser=True, org_unit_ids=["*"])
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation["id"], "hello")

    request = provider.chat.call_args[0][0]
    assert request.model == "claude-haiku-4.5"
    assert request.temperature == 0.9


@pytest.mark.django_db
def test_send_message_per_message_model_wins_over_profile(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.default_model_id = catalog["haiku"]
    profile.save()

    ci = CarbonIntelligence()
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    scope = Scope(user_identifier=str(user.pk), is_superuser=True, org_unit_ids=["*"])
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation["id"], "hello", model="gpt-4o")

    request = provider.chat.call_args[0][0]
    assert request.model == "gpt-4o"


# ── auto_title ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_autotitle_disabled_by_preference(user):
    conversation = _make_conversation(user, "chat", title="Chat")
    ci = CarbonIntelligence()

    ci._maybe_autotitle(conversation, "My important question", enabled=False)
    assert conversation.title == "Chat"

    ci._maybe_autotitle(conversation, "My important question", enabled=True)
    conversation.refresh_from_db()
    assert conversation.title == "My important question"


# ── memory_enabled gates the T4 tier ────────────────────────────────────


@pytest.mark.django_db
def test_memory_enabled_gates_t4_tier(user):
    MemoryLongTerm.objects.create(
        instance_id="carbon", category="pref",
        content="owner prefers CSV exports",
        confidence=1.0, host_user_id=str(user.pk), visibility="private",
    )
    scope = Scope(user_identifier=str(user.pk), is_superuser=False, org_unit_ids=["*"])
    conversation = _make_conversation(user)
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    def t4_messages(result):
        return [
            m for m in result["messages"]
            if m["role"] == "system" and "[Long-Term Memory]" in m["content"]
        ]

    # Preference ON (default) → T4 facts injected.
    result = assemble_context(conversation, _history_dicts(conversation), scope=scope)
    assert len(t4_messages(result)) == 1
    assert result["budget"]["T4_memory"] > 0

    # Preference OFF → T4 tier skipped entirely.
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.memory_enabled = False
    profile.save()
    result = assemble_context(conversation, _history_dicts(conversation), scope=scope)
    assert t4_messages(result) == []
    assert result["budget"]["T4_memory"] == 0


# ── usage_alert_threshold overrides soft warning ────────────────────────


@pytest.mark.django_db
def test_usage_alert_threshold_overrides_soft_warning(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.monthly_token_limit = 1000
    profile.usage_alert_threshold = 50
    profile.save()
    conv = _make_conversation(user)
    from ai.models import AIGeneration
    from django.utils import timezone

    AIGeneration.objects.create(
        conversation=conv, status="completed", completed_at=timezone.now(),
        model_id="claude-haiku-4.5", prompt_tokens=600, completion_tokens=0,
        total_tokens=600,
    )

    snapshot = AIUsage(user).quota_snapshot()
    # 60% used, threshold lowered to 50 → soft warning fires.
    assert snapshot["used"] == 600
    assert snapshot["pct"] == 60.0
    assert snapshot["soft_warning"] is True
    assert snapshot["soft_warning_pct"] == 50
    assert snapshot["hard_exceeded"] is False


@pytest.mark.django_db
def test_usage_alert_threshold_default_80(user, catalog):
    profile = AIUserProfile.objects.get_or_create(user=user)[0]
    profile.monthly_token_limit = 1000
    profile.save()
    conv = _make_conversation(user)
    from ai.models import AIGeneration
    from django.utils import timezone

    AIGeneration.objects.create(
        conversation=conv, status="completed", completed_at=timezone.now(),
        model_id="claude-haiku-4.5", prompt_tokens=600, completion_tokens=0,
        total_tokens=600,
    )

    snapshot = AIUsage(user).quota_snapshot()
    # 60% used, default threshold 80 → no soft warning yet.
    assert snapshot["soft_warning"] is False
    assert snapshot["soft_warning_pct"] == 80
