"""Phase 19-A — message operations + retry/resume resilience tests.

Covers:
  * ``assemble_context`` filters soft-deleted messages before windowing
  * opaque ``context_signature`` (message-id vector + model + profile)
  * ``delete_message`` soft-delete + thread-cut (user turn vs. single reply)
  * ``edit_message`` with ``regenerate=False`` (text-only edit)
  * ``retry_message`` rebuilds context from the turn *snapshot* (not live tail)
    and links the fresh reply via ``parent_id`` + ``parent_message_id``
  * ``retry_message_stream`` streams a fresh reply and links it
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from accounts.models import User
from ai.context_assembler import assemble_context
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIMessage


@pytest.fixture
def user(db):
    return User.objects.create_user(username="retry-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


def _pin_created_at(message, ts):
    """Pin a deterministic created_at (created in quick succession otherwise)."""
    AIMessage.objects.filter(pk=message.pk).update(created_at=ts)


# ── context assembler: deleted-filtering + signature ─────────────────────


@pytest.mark.django_db
def test_assemble_context_filters_deleted_and_signs_window(user):
    conversation = _make_conversation(user, "chat")
    base = timezone.now()
    live = AIMessage.objects.create(
        conversation=conversation, role="user", content="live",
    )
    dead = AIMessage.objects.create(
        conversation=conversation, role="assistant", content="dead",
    )
    _pin_created_at(live, base)
    _pin_created_at(dead, base + timedelta(seconds=1))
    AIMessage.objects.filter(pk=dead.pk).update(is_deleted=True)

    history = list(
        conversation.messages.order_by("created_at").values(
            "id", "role", "content", "created_at", "is_deleted",
        )
    )

    result = assemble_context(conversation, history, scope=None, recent_turns=8)

    contents = [m["content"] for m in result["messages"]]
    assert "live" in contents
    assert "dead" not in contents

    signature = result["context_signature"]
    assert isinstance(signature, str)
    assert len(signature) == 64

    # Same window but a different model → different signature.
    other = assemble_context(
        conversation, history, scope=None, recent_turns=8, model="gpt-different",
    )
    assert other["context_signature"] != signature


# ── delete: soft-delete + thread-cut ─────────────────────────────────────


@pytest.mark.django_db
def test_delete_user_turn_soft_deletes_descendants(user):
    conversation = _make_conversation(user, "chat")
    turn = AIMessage.objects.create(
        conversation=conversation, role="user", content="question",
    )
    reply = AIMessage.objects.create(
        conversation=conversation, role="assistant", content="answer", parent=turn,
    )
    later = AIMessage.objects.create(
        conversation=conversation, role="user", content="later",
    )

    ci = CarbonIntelligence()
    ci.delete_message(user, str(conversation.id), str(turn.id))

    turn.refresh_from_db()
    reply.refresh_from_db()
    later.refresh_from_db()
    assert turn.is_deleted is True
    assert reply.is_deleted is True
    assert later.is_deleted is False


@pytest.mark.django_db
def test_delete_assistant_reply_soft_deletes_only_that(user):
    conversation = _make_conversation(user, "chat")
    turn = AIMessage.objects.create(
        conversation=conversation, role="user", content="question",
    )
    reply = AIMessage.objects.create(
        conversation=conversation, role="assistant", content="answer", parent=turn,
    )

    ci = CarbonIntelligence()
    ci.delete_message(user, str(conversation.id), str(reply.id))

    turn.refresh_from_db()
    reply.refresh_from_db()
    assert reply.is_deleted is True
    assert turn.is_deleted is False


# ── edit: regenerate=False is a text-only edit ───────────────────────────


@pytest.mark.django_db
def test_edit_message_regenerate_false_only_edits(user):
    conversation = _make_conversation(user, "chat")
    turn = AIMessage.objects.create(
        conversation=conversation, role="user", content="hello",
    )
    AIMessage.objects.create(
        conversation=conversation, role="assistant", content="reply", parent=turn,
    )

    ci = CarbonIntelligence()
    ci.send_message = MagicMock()

    ci.edit_message(
        user, str(conversation.id), str(turn.id), "hello edited",
        regenerate=False,
    )

    turn.refresh_from_db()
    assert turn.content == "hello edited"
    ci.send_message.assert_not_called()
    assert AIMessage.objects.filter(conversation=conversation).count() == 2


# ── retry: snapshot reuse + linkage ──────────────────────────────────────


@pytest.mark.django_db
def test_retry_message_uses_context_snapshot_not_live_tail(user):
    conversation = _make_conversation(user, "chat")
    base = timezone.now()

    t1 = AIMessage.objects.create(conversation=conversation, role="user", content="turn 1")
    _pin_created_at(t1, base)
    a1 = AIMessage.objects.create(conversation=conversation, role="assistant", content="reply 1", parent=t1)
    _pin_created_at(a1, base + timedelta(seconds=1))
    t2 = AIMessage.objects.create(conversation=conversation, role="user", content="turn 2")
    _pin_created_at(t2, base + timedelta(seconds=2))
    a2 = AIMessage.objects.create(conversation=conversation, role="assistant", content="reply 2", parent=t2)
    _pin_created_at(a2, base + timedelta(seconds=3))
    t3 = AIMessage.objects.create(conversation=conversation, role="user", content="turn 3")
    _pin_created_at(t3, base + timedelta(seconds=4))

    captured = {}

    ci = CarbonIntelligence()

    def _fake_route(conv, content, conv_ctx, scope, model=None):
        captured["messages"] = conv_ctx.messages
        return ci._save_assistant_message(
            conv, "fresh", metadata={}, status="completed",
        )

    ci._route_typed_message = MagicMock(side_effect=_fake_route)

    ci.retry_message(user, str(conversation.id), str(t2.id))

    verbatim = [
        m["content"]
        for m in captured["messages"]
        if m["role"] in ("user", "assistant")
    ]
    # The later turn must NOT leak into a retry of turn 2.
    assert "turn 2" in verbatim
    assert "turn 3" not in verbatim


@pytest.mark.django_db
def test_retry_message_links_and_signs_reply(user):
    conversation = _make_conversation(user, "chat")
    base = timezone.now()

    turn = AIMessage.objects.create(conversation=conversation, role="user", content="question")
    _pin_created_at(turn, base)
    old = AIMessage.objects.create(conversation=conversation, role="assistant", content="old", parent=turn)
    _pin_created_at(old, base + timedelta(seconds=1))

    ci = CarbonIntelligence()

    def _fake_route(conv, content, conv_ctx, scope, model=None):
        return ci._save_assistant_message(
            conv, "fresh", metadata={}, status="completed",
        )

    ci._route_typed_message = MagicMock(side_effect=_fake_route)

    result = ci.retry_message(user, str(conversation.id), str(turn.id))

    fresh_id = result["assistant_message"]["id"]
    fresh = AIMessage.objects.get(id=fresh_id)
    assert fresh.parent_id == turn.id
    assert fresh.parent_message_id == old.id
    assert fresh.context_signature
    assert len(fresh.context_signature) == 64


@pytest.mark.django_db
def test_retry_message_stream_streams_and_links(user):
    conversation = _make_conversation(user, "chat")
    base = timezone.now()

    turn = AIMessage.objects.create(conversation=conversation, role="user", content="question")
    _pin_created_at(turn, base)
    old = AIMessage.objects.create(conversation=conversation, role="assistant", content="old", parent=turn)
    _pin_created_at(old, base + timedelta(seconds=1))

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat_stream.return_value = [
        ("chunk", "fr"),
        ("chunk", "esh"),
        (
            "done",
            {
                "status": "completed",
                "result": {"content": "fresh", "follow_up_questions": []},
            },
        ),
    ]

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    frames = list(ci.retry_message_stream(user, str(conversation.id), str(turn.id)))

    assert frames[-1]["type"] == "done"
    fresh = AIMessage.objects.filter(
        conversation=conversation, role="assistant", content="fresh",
    ).first()
    assert fresh is not None
    assert fresh.parent_id == turn.id
    assert fresh.parent_message_id == old.id
