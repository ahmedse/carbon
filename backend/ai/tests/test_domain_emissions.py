"""
Sprint 7 — Emissions domain (GHG vocabulary) tests.

Covers:
  - domain registration + lookup via ai.domain_protocol
  - DomainContext shape (knowledge + config)
  - prompt-prefix injection (with / without app_identifier / unknown domain)
  - _send_chat_message injection seam
  - no-crash paths

Imports mirror test_workspace_context.py: all `ai.*` for the domain registry
(single registry — never `backend.ai.domain_protocol`), while Scope/ChatResponse
come from `backend.ai.protocol` to match what ai.intelligence actually uses.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai.domain.emissions import EmissionsDomainAI
from ai.domain_protocol import (
    get_domain,
    has_domain,
    list_domains,
    register_domain,
)
from ai.intelligence import CarbonIntelligence
from accounts.models import User
from backend.ai.protocol import ChatResponse, ConversationContext, Scope


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="emissions-worker", password="secret123")


# ── Registration & lookup ─────────────────────────────────────────────────


def test_emissions_domain_registered():
    assert has_domain("emissions") is True


def test_get_domain_returns_emissions_class():
    assert get_domain("emissions") is EmissionsDomainAI


def test_get_domain_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        get_domain("nope")


def test_list_domains_includes_emissions():
    assert "emissions" in list_domains()


def test_duplicate_registration_raises():
    with pytest.raises(ValueError):
        register_domain("emissions", EmissionsDomainAI)


# ── DomainContext content ─────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    assert EmissionsDomainAI.app_identifier == "emissions"
    assert EmissionsDomainAI.app_display_name == "Carbon Footprint"


def test_domain_context_knowledge_shape():
    ctx = EmissionsDomainAI().get_domain_context()
    knowledge = ctx.domain_knowledge
    assert knowledge["protocol"] == "GHG Protocol Corporate Standard"
    assert set(knowledge["scopes"].keys()) == {"scope_1", "scope_2", "scope_3"}
    assert knowledge["scopes"]["scope_1"] == (
        "Direct emissions from owned/controlled sources"
    )
    assert knowledge["ar_version"] == "IPCC AR6"
    assert knowledge["units"] == ["tCO2e", "kgCO2e", "MtCO2e"]
    assert knowledge["calculation_methods"] == ["location-based", "market-based"]


def test_domain_context_config_shape():
    ctx = EmissionsDomainAI().get_domain_context()
    config = ctx.domain_config
    assert config["default_gwp_version"] == "AR6"
    assert config["boundary_approaches"] == [
        "operational",
        "equity share",
        "financial control",
    ]


# ── Prompt injection ──────────────────────────────────────────────────────


def _make_ci() -> CarbonIntelligence:
    ci = CarbonIntelligence()
    ci._provider = MagicMock()
    ci._provider.provider_name = "dummy"
    ci._provider.chat.return_value = ChatResponse(
        status="completed", content="ok"
    )
    return ci


def test_prepend_domain_context_emissions():
    ci = _make_ci()
    result = ci._prepend_domain_context(
        Scope(app_identifier="emissions"), "hello"
    )
    assert result.startswith("[Domain: emissions]")
    assert "GHG Protocol Corporate Standard" in result
    assert result.endswith("hello")


def test_prepend_domain_context_no_app_identifier():
    ci = _make_ci()
    assert ci._prepend_domain_context(Scope(), "hello") == "hello"


def test_prepend_domain_context_unknown_domain():
    ci = _make_ci()
    assert ci._prepend_domain_context(Scope(app_identifier="waste"), "hello") == "hello"


def test_prepend_domain_context_none_scope():
    ci = _make_ci()
    assert ci._prepend_domain_context(None, "hello") == "hello"


def test_domain_context_prompt_prefix_renderer():
    from ai.intelligence import _domain_context_prompt_prefix

    ctx = EmissionsDomainAI().get_domain_context()
    prefix = _domain_context_prompt_prefix(ctx)
    assert prefix.startswith("[Domain: emissions]")
    assert "Scopes:" in prefix
    assert "scope_1" in prefix
    assert "GWP version: IPCC AR6" in prefix
    assert "default_gwp_version: AR6" in prefix


# ── _send_chat_message injection seam ─────────────────────────────────────


@pytest.mark.django_db
def test_chat_message_injects_domain_context(user):
    from ai.models import AIConversation

    conversation = AIConversation.objects.create(
        user=user,
        title="chat",
        conversation_type="chat",
        app_identifier="emissions",
        task_payload_json={},
        scope_json={},
    )

    ci = _make_ci()
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    ci._send_chat_message(
        conversation,
        "hello",
        ConversationContext(conversation_id=str(conversation.id)),
        Scope(app_identifier="emissions"),
    )

    sent = ci._provider.chat.call_args[0][0]
    assert "[Domain: emissions]" in sent.message
    assert sent.message.endswith("hello")


@pytest.mark.django_db
def test_chat_message_skips_domain_without_app_identifier(user):
    from ai.models import AIConversation

    conversation = AIConversation.objects.create(
        user=user,
        title="chat",
        conversation_type="chat",
        app_identifier=None,
        task_payload_json={},
        scope_json={},
    )

    ci = _make_ci()
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    ci._send_chat_message(
        conversation,
        "hello",
        ConversationContext(conversation_id=str(conversation.id)),
        Scope(),
    )

    sent = ci._provider.chat.call_args[0][0]
    assert sent.message == "hello"


# ── Manifest layer ────────────────────────────────────────────────────────


def test_manifest_supported_task_types():
    manifest = EmissionsDomainAI()
    assert "chat" in manifest.supported_task_types
    assert "dq_validate" in manifest.supported_task_types
    assert "report_draft" in manifest.supported_task_types
    assert "investigate" in manifest.supported_task_types


def test_manifest_entry_points_have_required_fields():
    for ep in EmissionsDomainAI.entry_points:
        assert "label" in ep
        assert "task_type" in ep
        assert "on_entity" in ep
        assert "icon" in ep


def test_manifest_starter_prompts_have_required_fields():
    prompts = EmissionsDomainAI.starter_prompts
    assert "table" in prompts
    assert "module" in prompts
    assert "default" in prompts
    for section in prompts.values():
        for item in section:
            assert "label" in item
            assert "task_type" in item


def test_manifest_system_prompt_extension_is_non_empty():
    assert len(EmissionsDomainAI.system_prompt_extension) > 50


def test_manifest_validate_task_payload_table_required():
    manifest = EmissionsDomainAI()
    ok, _ = manifest.validate_task_payload("dq_validate", {"table_id": 7})
    assert ok is True
    ok, reason = manifest.validate_task_payload("dq_validate", {})
    assert ok is False
    assert "table_id" in reason


def test_manifest_validate_task_payload_report_requires_module_or_period():
    manifest = EmissionsDomainAI()
    ok, _ = manifest.validate_task_payload("report_draft", {"module_id": 1})
    assert ok is True
    ok, reason = manifest.validate_task_payload("report_draft", {})
    assert ok is False
    assert "module_id" in reason or "period_id" in reason


def test_manifest_validate_chat_always_passes():
    manifest = EmissionsDomainAI()
    ok, _ = manifest.validate_task_payload("chat", {})
    assert ok is True


def test_to_manifest_dict_shape():
    d = EmissionsDomainAI().to_manifest_dict()
    assert d["app_identifier"] == "emissions"
    assert d["display_name"] == "Carbon Footprint"
    assert isinstance(d["supported_task_types"], list)
    assert isinstance(d["entry_points"], list)
    assert isinstance(d["starter_prompts"], dict)
    # system_prompt_extension is never leaked as raw text
    assert isinstance(d["system_prompt_extension"], bool)
    assert d["system_prompt_extension"] is True


def test_all_manifests_includes_emissions():
    from ai.domain_protocol import all_manifests
    ids = [m["app_identifier"] for m in all_manifests()]
    assert "emissions" in ids


def test_get_manifest_returns_dict():
    from ai.domain_protocol import get_manifest
    d = get_manifest("emissions")
    assert d["app_identifier"] == "emissions"


def test_get_manifest_unknown_raises():
    from ai.domain_protocol import get_manifest
    with pytest.raises(KeyError):
        get_manifest("nonexistent_app")


# ── Manifest API endpoints ────────────────────────────────────────────────


@pytest.mark.django_db
def test_manifest_list_endpoint(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken
    token = str(RefreshToken.for_user(user).access_token)
    resp = client.get(
        "/carbon-api/ai/pulse/apps/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "apps" in data
    assert any(a["app_identifier"] == "emissions" for a in data["apps"])


@pytest.mark.django_db
def test_manifest_detail_endpoint(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken
    token = str(RefreshToken.for_user(user).access_token)
    resp = client.get(
        "/carbon-api/ai/pulse/apps/emissions/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert resp.status_code == 200
    assert resp.json()["app_identifier"] == "emissions"


@pytest.mark.django_db
def test_manifest_detail_endpoint_unknown_returns_404(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken
    token = str(RefreshToken.for_user(user).access_token)
    resp = client.get(
        "/carbon-api/ai/pulse/apps/nonexistent/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_manifest_list_endpoint_unauthenticated(client):
    resp = client.get("/carbon-api/ai/pulse/apps/")
    assert resp.status_code == 401
