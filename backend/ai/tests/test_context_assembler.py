"""Sprint 15 — context engineering + enterprise governance tests.

Covers:
  * tiered/budgeted context assembly (``assemble_context``)
  * ``context_snapshot_json`` telemetry persistence after ``send_message``
  * deterministic conversation summarization
  * JSON + Markdown export
  * per-turn usage attribution persistence + serialization
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from accounts.models import User
from ai.context_assembler import assemble_context
from ai.intelligence import CarbonIntelligence, _serialize_message
from ai.models import AIConversation, AIMessage
from backend.ai.protocol import ChatResponse, Scope


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="context-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", summary=""):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json={},
        scope_json={},
        summary=summary,
    )


def _history_dicts(conversation):
    return list(
        conversation.messages.order_by("created_at").values(
            "role", "content", "created_at",
        )
    )


# ── 1. assemble_context tiering + summary ────────────────────────────────


@pytest.mark.django_db
def test_assemble_context_caps_history_and_prepends_summary(user):
    conversation = _make_conversation(user, "chat", summary="Earlier context summary")
    messages = []
    for i in range(20):
        messages.append(
            AIMessage.objects.create(
                conversation=conversation,
                role="user" if i % 2 == 0 else "assistant",
                content=f"message {i}",
            )
        )

    # Pin strictly increasing timestamps so tiering is deterministic.
    base = timezone.now()
    for i, m in enumerate(messages):
        AIMessage.objects.filter(pk=m.pk).update(
            created_at=base + timedelta(seconds=i)
        )

    result = assemble_context(conversation, _history_dicts(conversation), scope=None, recent_turns=8)

    # Summary adds exactly one leading system message; history is capped at 8.
    assert len(result["messages"]) == 1 + 8
    assert result["messages"][0]["role"] == "system"
    assert "Earlier context summary" in result["messages"][0]["content"]

    # Verbatim history is the most recent 8 turns (oldest 12 dropped).
    verbatim = [m for m in result["messages"] if m["role"] != "system"]
    assert len(verbatim) == 8
    assert verbatim[0]["content"] == "message 12"
    assert verbatim[-1]["content"] == "message 19"


@pytest.mark.django_db
def test_assemble_context_budget_keys_non_negative(user):
    conversation = _make_conversation(user, "chat", summary="summary")
    AIMessage.objects.create(
        conversation=conversation, role="user", content="hello world"
    )

    result = assemble_context(
        conversation,
        _history_dicts(conversation),
        scope=None,
        recent_turns=8,
        summary_budget=1500,
        retrieval_budget=2000,
        memory_budget=1000,
    )

    budget = result["budget"]
    assert set(budget.keys()) == {
        "T2_history", "T2b_summary", "T3_retrieval", "T4_memory",
    }
    for value in budget.values():
        assert value >= 0
    # T3/T4 reserve their configured budgets even though retrieval is stubbed.
    assert budget["T3_retrieval"] == 2000
    assert budget["T4_memory"] == 1000


@pytest.mark.django_db
def test_assemble_context_no_summary_is_history_only(user):
    conversation = _make_conversation(user, "chat", summary="")
    for i in range(5):
        AIMessage.objects.create(
            conversation=conversation, role="user", content=f"m{i}"
        )

    result = assemble_context(
        conversation, _history_dicts(conversation), scope=None, recent_turns=8,
    )

    assert len(result["messages"]) == 5
    assert all(m["role"] != "system" for m in result["messages"])


# ── 2. context_snapshot_json persisted after send_message ────────────────


@pytest.mark.django_db
def test_context_snapshot_json_set_after_send_message(user):
    ci = CarbonIntelligence()

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    conversation_id = conversation["id"]

    scope = Scope(
        user_identifier=str(user.pk),
        is_superuser=True,
        org_unit_ids=["*"],
    )
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation_id, "hello world")

    conv = AIConversation.objects.get(id=conversation_id)
    snapshot = conv.context_snapshot_json
    assert snapshot
    assert "T2_history" in snapshot
    assert snapshot["T2_history"] >= 0


# ── 3. summarize_conversation deterministic ──────────────────────────────


@pytest.mark.django_db
def test_summarize_conversation_deterministic(user):
    conversation = _make_conversation(user, "chat", summary="")
    AIMessage.objects.create(conversation=conversation, role="user", content="First question about DQ rules")
    AIMessage.objects.create(conversation=conversation, role="user", content="Second question about emissions")
    AIMessage.objects.create(conversation=conversation, role="user", content="Third question about catalogs")

    ci = CarbonIntelligence()
    result = ci.summarize_conversation(user, str(conversation.id))

    conversation.refresh_from_db()
    assert result["summary"]
    assert conversation.summary == result["summary"]
    assert "First question" in conversation.summary

    # force=True regenerates — still deterministic, no LLM call.
    result_again = ci.summarize_conversation(user, str(conversation.id), force=True)
    assert result_again["summary"] == result["summary"]


@pytest.mark.django_db
def test_summarize_conversation_skips_when_present(user):
    conversation = _make_conversation(user, "chat", summary="already summarized")
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")

    ci = CarbonIntelligence()
    result = ci.summarize_conversation(user, str(conversation.id))

    conversation.refresh_from_db()
    # Existing summary preserved (no force → no recompute).
    assert result["summary"] == "already summarized"
    assert conversation.summary == "already summarized"


# ── 4. export ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_export_json_returns_conversation_and_messages(user):
    conversation = _make_conversation(user, "chat", summary="")
    AIMessage.objects.create(conversation=conversation, role="user", content="hello")
    AIMessage.objects.create(conversation=conversation, role="assistant", content="hi there")

    ci = CarbonIntelligence()
    result = ci.export_conversation(user, str(conversation.id), fmt="json")

    assert result["format"] == "json"
    content = result["content"]
    assert content["conversation"]["id"] == str(conversation.id)
    assert len(content["messages"]) == 2


@pytest.mark.django_db
def test_export_markdown_contains_title_and_content(user):
    conversation = _make_conversation(user, "chat", summary="")
    conversation.title = "Exported Chat"
    conversation.save(update_fields=["title"])
    AIMessage.objects.create(
        conversation=conversation,
        role="user",
        content="Tell me about GHG scopes",
        metadata_json={"kind": "question"},
    )

    ci = CarbonIntelligence()
    result = ci.export_conversation(user, str(conversation.id), fmt="markdown")

    assert result["format"] == "markdown"
    md = result["content"]
    assert "# Exported Chat" in md
    assert "Tell me about GHG scopes" in md
    assert "**User**" in md
    assert "```json" in md


# ── 5. usage attribution ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_usage_kwarg_persists_and_serializes(user):
    conversation = _make_conversation(user, "chat", summary="")

    ci = CarbonIntelligence()
    usage = {
        "model": "deepseek-chat",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "cost_usd": 0.0001,
        "latency_ms": 123,
    }
    serialized = ci._save_assistant_message(
        conversation,
        "answer",
        metadata={},
        status="completed",
        usage=usage,
    )

    assert serialized["token_usage_json"] == usage

    # Survives the DB round-trip via _serialize_message.
    persisted = AIMessage.objects.get(id=serialized["id"])
    assert _serialize_message(persisted)["token_usage_json"] == usage
