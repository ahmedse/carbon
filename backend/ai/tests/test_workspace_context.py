"""
WorkspaceContext tests — Sprint 6 Phases 6-A + 6-C.

Covers:
  - ``WorkspaceContext.from_dict`` (None / empty / valid / unknown-key filtering)
  - ``WorkspaceContext.to_prompt_prefix``
  - ``create_conversation`` persistence (with / without workspace_context)
  - ``_send_chat_message`` prompt prefix (prepends when present, ignores when absent)
  - intent-aware first assistant opener (create+rule / debug / explore / edit)
  - malformed context never fails a conversation

The pure dataclass tests need no DB; the orchestration tests use a real user.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIMessage
from backend.ai.protocol import (
    ChatResponse,
    ConversationContext,
    Scope,
    WorkspaceContext,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="wc-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


# ── from_dict ─────────────────────────────────────────────────────────────


def test_from_dict_none_returns_none():
    assert WorkspaceContext.from_dict(None) is None


def test_from_dict_empty_dict_returns_none():
    assert WorkspaceContext.from_dict({}) is None


def test_from_dict_missing_workspace_returns_none():
    # A dict with fields but no "workspace" key is not a valid context.
    assert WorkspaceContext.from_dict({"intent_signal": "explore"}) is None


def test_from_dict_missing_current_view_defaults_to_empty():
    # F1 regression: a context with "workspace" but no "current_view" must not
    # raise TypeError (previously crashed assemble_context -> edit/regenerate).
    ctx = WorkspaceContext.from_dict({"workspace": "dq", "entity_type": "table"})
    assert ctx is not None
    assert ctx.workspace == "dq"
    assert ctx.current_view == ""


def test_from_dict_valid_populates_fields():
    ctx = WorkspaceContext.from_dict(
        {
            "workspace": "dq",
            "current_view": "rule_detail",
            "entity_type": "rule",
            "entity_id": "42",
            "entity_name": "email_not_null",
            "form_state": {"severity": "error"},
            "recent_actions": ["opened table", "clicked create"],
            "mentions": [
                {"kind": "table", "id": "123", "name": "emissions_fuel"},
                {"kind": "rule", "id": "456", "name": "email_not_null"},
            ],
            "intent_signal": "debug",
            "app_identifier": "dq",
        }
    )
    assert ctx is not None
    assert ctx.workspace == "dq"
    assert ctx.current_view == "rule_detail"
    assert ctx.entity_type == "rule"
    assert ctx.entity_id == "42"
    assert ctx.entity_name == "email_not_null"
    assert ctx.form_state == {"severity": "error"}
    assert ctx.recent_actions == ["opened table", "clicked create"]
    assert ctx.mentions == [
        {"kind": "table", "id": "123", "name": "emissions_fuel"},
        {"kind": "rule", "id": "456", "name": "email_not_null"},
    ]
    assert ctx.intent_signal == "debug"
    assert ctx.app_identifier == "dq"


def test_from_dict_filters_unknown_keys():
    ctx = WorkspaceContext.from_dict(
        {
            "workspace": "dq",
            "current_view": "rule_list",
            "bogus_key": "should-not-leak",
        }
    )
    assert ctx is not None
    assert not hasattr(ctx, "bogus_key")


# ── to_prompt_prefix ──────────────────────────────────────────────────────


def test_to_prompt_prefix_includes_entity_and_intent():
    ctx = WorkspaceContext(
        workspace="dq",
        current_view="rule_list",
        entity_type="table",
        entity_name="emissions_fuel",
        intent_signal="explore",
    )
    prefix = ctx.to_prompt_prefix()
    assert "dq workspace" in prefix
    assert "rule_list" in prefix
    assert "emissions_fuel" in prefix
    assert "explore" in prefix


def test_to_prompt_prefix_includes_mention_summary():
    ctx = WorkspaceContext(
        workspace="dq",
        current_view="rule_detail",
        mentions=[
            {"kind": "table", "id": "123", "name": "emissions_fuel"},
            {"kind": "rule", "id": "456", "name": "email_not_null"},
        ],
    )
    prefix = ctx.to_prompt_prefix()
    assert "mentions:" in prefix
    assert "table emissions_fuel" in prefix
    assert "rule email_not_null" in prefix


def test_to_prompt_prefix_empty_workspace_is_empty():
    ctx = WorkspaceContext(workspace="", current_view="rule_list")
    assert ctx.to_prompt_prefix() == ""


# ── create_conversation persistence ───────────────────────────────────────


@pytest.mark.django_db
def test_create_conversation_persists_workspace_context(user):
    ci = CarbonIntelligence()
    wc = {
        "workspace": "dq",
        "current_view": "rule_list",
        "intent_signal": "explore",
    }
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        result = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context=wc,
        )

    conv = AIConversation.objects.get(id=result["id"])
    assert conv.task_payload_json["workspace_context"] == wc


@pytest.mark.django_db
def test_create_conversation_omits_workspace_context_when_absent(user):
    ci = CarbonIntelligence()
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        result = ci.create_conversation(
            user=user,
            conversation_type="chat",
            task_payload={"table_name": "emissions_fuel"},
        )

    conv = AIConversation.objects.get(id=result["id"])
    assert "workspace_context" not in conv.task_payload_json
    assert conv.task_payload_json == {"table_name": "emissions_fuel"}


# ── _send_chat_message prompt prefix ──────────────────────────────────────


@pytest.mark.django_db
def test_send_chat_message_prepends_context_prefix(user):
    conversation = _make_conversation(
        user,
        "chat",
        {
            "workspace_context": {
                "workspace": "dq",
                "current_view": "rule_list",
                "entity_type": "table",
                "entity_name": "emissions_fuel",
                "intent_signal": "explore",
            }
        },
    )
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    ci._send_chat_message(
        conversation,
        "hello",
        ConversationContext(conversation_id=str(conversation.id)),
        Scope(),
    )

    sent = provider.chat.call_args[0][0]
    assert "User is in the dq workspace" in sent.message
    assert "emissions_fuel" in sent.message
    assert sent.message.endswith("hello")


@pytest.mark.django_db
def test_send_chat_message_ignores_absent_context(user):
    conversation = _make_conversation(user, "chat", {})
    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    ci._send_chat_message(
        conversation,
        "hello",
        ConversationContext(conversation_id=str(conversation.id)),
        Scope(),
    )

    sent = provider.chat.call_args[0][0]
    assert sent.message == "hello"


# ── Intent-aware opener ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_intent_aware_opener_for_create_rule(user):
    ci = CarbonIntelligence()
    wc = {
        "workspace": "dq",
        "current_view": "rule_list",
        "entity_type": "rule",
        "entity_name": "emissions_fuel",
        "intent_signal": "create",
    }
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        result = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context=wc,
        )

    conv = AIConversation.objects.get(id=result["id"])
    openers = AIMessage.objects.filter(conversation=conv, role="assistant")
    assert openers.count() == 1
    opener = openers.get()
    assert "I see you want to create a new DQ rule" in opener.content
    assert "emissions_fuel" in opener.content
    assert opener.metadata_json.get("type") == "workspace_context_opener"
    assert conv.status == "needs_input"


@pytest.mark.django_db
def test_intent_aware_opener_for_debug(user):
    ci = CarbonIntelligence()
    wc = {
        "workspace": "dq",
        "current_view": "rule_detail",
        "entity_type": "rule",
        "entity_name": "email_not_null",
        "intent_signal": "debug",
    }
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        result = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context=wc,
        )

    conv = AIConversation.objects.get(id=result["id"])
    opener = AIMessage.objects.get(conversation=conv, role="assistant")
    assert "debugging" in opener.content
    assert "email_not_null" in opener.content


@pytest.mark.django_db
def test_intent_aware_opener_for_explore_references_entity(user):
    ci = CarbonIntelligence()
    wc = {
        "workspace": "catalog",
        "current_view": "table_detail",
        "entity_type": "table",
        "entity_name": "emissions_fuel",
        "intent_signal": "explore",
    }
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        result = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context=wc,
        )

    conv = AIConversation.objects.get(id=result["id"])
    opener = AIMessage.objects.get(conversation=conv, role="assistant")
    assert "emissions_fuel" in opener.content


@pytest.mark.django_db
def test_no_opener_when_intent_absent(user):
    ci = CarbonIntelligence()
    wc = {
        "workspace": "dq",
        "current_view": "rule_list",
        "intent_signal": None,
    }
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        result = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context=wc,
        )

    conv = AIConversation.objects.get(id=result["id"])
    assert AIMessage.objects.filter(conversation=conv, role="assistant").count() == 0
    assert conv.status == "pending"


# ── Malformed context never crashes ───────────────────────────────────────


@pytest.mark.django_db
def test_malformed_context_does_not_crash(user):
    ci = CarbonIntelligence()
    with patch("ai.intelligence.build_scope", return_value=Scope()):
        # Wrong type (list) — from_dict returns None, creation succeeds.
        result_list = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context=["not", "a", "dict"],
        )
        # Wrong-type intent_signal (dict) — opener helper swallows the error.
        result_bad = ci.create_conversation(
            user=user,
            conversation_type="chat",
            workspace_context={
                "workspace": "dq",
                "intent_signal": {"nested": "dict"},
            },
        )

    assert result_list["id"]
    assert result_bad["id"]

    bad_conv = AIConversation.objects.get(id=result_bad["id"])
    # No opener seeded for malformed intent, and no crash.
    assert AIMessage.objects.filter(conversation=bad_conv, role="assistant").count() == 0
