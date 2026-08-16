"""
Sprint 14 — streaming + interrupt tests.

Covers:
  - non-chat ``send_message_stream`` progress → done framing
  - ``stop_generation`` cancellation event + idempotency
  - mid-stream cancellation → ``stopped`` assistant message (never ``working``)
  - ``regenerate_message`` → new assistant reply with ``parent_message_id``
  - ``edit_message`` → user content update; assistant message rejected
  - provider failure → ``error`` frame + ``failed`` message (never ``working``)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from accounts.models import User
from ai.generation_registry import GENERATIONS
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIMessage


@pytest.fixture
def user(db):
    return User.objects.create_user(username="stream-interrupt", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


@pytest.mark.django_db
def test_non_chat_stream_yields_progress_then_done(user):
    conversation = _make_conversation(user, "dq_suggest", {})

    ci = CarbonIntelligence()

    def _fake_route(*args, **kwargs):
        conversation.status = "completed"
        conversation.save(update_fields=["status"])
        return {"id": "assistant-1", "role": "assistant"}

    ci._route_typed_message = MagicMock(side_effect=_fake_route)

    frames = list(ci.send_message_stream(user, str(conversation.id), "hi"))

    assert [f["type"] for f in frames] == ["progress", "progress", "done"]
    assert frames[0]["stage"] == "start"
    assert frames[0]["message"] == "Analyzing table profile…"
    assert frames[1]["stage"] == "done"
    assert frames[1]["message"] == "Done"
    assert frames[2]["type"] == "done"

    ci._route_typed_message.assert_called_once()
    assert AIMessage.objects.filter(
        conversation=conversation, role="user", content="hi"
    ).exists()
    conversation.refresh_from_db()
    assert conversation.status == "completed"


@pytest.mark.django_db
def test_stop_generation_sets_cancellation_event(user):
    conversation = _make_conversation(user, "chat", {})
    conv_id = str(conversation.id)
    GENERATIONS.start(conv_id)

    ci = CarbonIntelligence()
    assert ci.stop_generation(user, conv_id) == {"stopped": True}
    assert GENERATIONS.is_cancelled(conv_id)

    # Idempotent: nothing running after finish → stopped: false, not an error.
    GENERATIONS.finish(conv_id)
    assert ci.stop_generation(user, conv_id) == {"stopped": False}


@pytest.mark.django_db
def test_cancellation_mid_stream_persists_stopped_message(user):
    conversation = _make_conversation(user, "chat", {})
    conv_id = str(conversation.id)

    def chat_stream(request):
        yield ("chunk", "He")
        GENERATIONS.cancel(conv_id)
        yield ("chunk", "llo")

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat_stream.side_effect = chat_stream

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    frames = list(ci.send_message_stream(user, conv_id, "hi"))

    assert frames[-1]["type"] == "stopped"
    conversation.refresh_from_db()
    assert conversation.status == "completed"

    stopped = AIMessage.objects.filter(
        conversation=conversation, role="assistant", status="stopped"
    )
    assert stopped.exists()
    assert stopped.first().content == "He"

    assert conversation.generations.filter(status="cancelled").exists()


@pytest.mark.django_db
def test_regenerate_message_sets_parent_message_id(user):
    conversation = _make_conversation(user, "chat", {})
    AIMessage.objects.create(
        conversation=conversation, role="user", content="hello",
    )
    target = AIMessage.objects.create(
        conversation=conversation,
        role="assistant",
        content="old reply",
        created_at=timezone.now() + timezone.timedelta(seconds=5),
    )
    new_assistant = AIMessage.objects.create(
        conversation=conversation, role="assistant", content="new reply",
    )

    ci = CarbonIntelligence()
    ci.send_message = MagicMock(
        return_value={"assistant_message": {"id": str(new_assistant.id)}}
    )

    result = ci.regenerate_message(user, str(conversation.id), str(target.id))

    ci.send_message.assert_called_once()
    new_assistant.refresh_from_db()
    assert new_assistant.parent_message_id == target.id
    assert "messages" in result


@pytest.mark.django_db
def test_edit_message_updates_content_and_rejects_assistant(user):
    conversation = _make_conversation(user, "chat", {})
    user_msg = AIMessage.objects.create(
        conversation=conversation, role="user", content="hello",
    )
    assistant_msg = AIMessage.objects.create(
        conversation=conversation, role="assistant", content="reply",
    )

    ci = CarbonIntelligence()
    ci.send_message = MagicMock(
        return_value={"conversation": {}, "user_message": {}, "assistant_message": {}}
    )

    ci.edit_message(
        user, str(conversation.id), str(user_msg.id), "hello edited",
    )
    user_msg.refresh_from_db()
    assert user_msg.content == "hello edited"
    ci.send_message.assert_called_once()

    with pytest.raises(ValueError):
        ci.edit_message(
            user, str(conversation.id), str(assistant_msg.id), "nope",
        )


@pytest.mark.django_db
def test_provider_failure_yields_error_and_persists_failed(user):
    conversation = _make_conversation(user, "chat", {})

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat_stream.return_value = [("error", "provider down")]

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    frames = list(ci.send_message_stream(user, str(conversation.id), "hello"))

    assert any(f["type"] == "error" for f in frames)
    conversation.refresh_from_db()
    assert conversation.status == "failed"
    assert AIMessage.objects.filter(
        conversation=conversation, role="assistant", status="failed"
    ).exists()
    assert conversation.generations.filter(status="failed").exists()
