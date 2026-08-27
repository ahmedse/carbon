"""
Chat streaming tests — Sprint 8 Phase 8-A.

Covers:
  - ``dispatch_task_stream`` bridge (chunks → done / non-chat error / engine error)
  - ``PulseProvider.chat_stream`` payload + delegation
  - ``CarbonIntelligence.send_message_stream`` persistence + finalization
  - SSE endpoint (``messages/stream``) contract + error framing
  - non-streaming ``messages`` endpoint regression

Imports mirror the existing test suite: ``ai.*`` for the engine runtime and
intelligence, ``backend.ai.*`` for the protocol and provider (the provider is
only ever imported via ``backend.ai.providers.pulse``).
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIMessage
from ai.protocol import ChatRequest, ConversationContext, Scope


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="stream-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


# ── dispatch_task_stream bridge ──────────────────────────────────────────


def test_dispatch_task_stream_chat_yields_chunks_then_done(monkeypatch):
    import ai.engine_runtime as rt

    async def fake_run_chat(instance_id, payload, task_id, *, stream_callback=None):
        assert stream_callback is not None
        await stream_callback("Hel")
        await stream_callback("lo")
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {
                "content": "Hello",
                "follow_up_questions": [],
                "execution_ms": 1,
            },
        }

    monkeypatch.setattr(rt, "_run_chat", fake_run_chat)

    frames = list(rt.dispatch_task_stream("chat", {"message": "hi"}))

    assert [kind for kind, _ in frames] == ["chunk", "chunk", "done"]
    assert frames[0] == ("chunk", "Hel")
    assert frames[1] == ("chunk", "lo")
    assert frames[2][0] == "done"
    assert frames[2][1]["result"]["content"] == "Hello"


def test_dispatch_task_stream_non_chat_yields_single_error():
    import ai.engine_runtime as rt

    frames = list(rt.dispatch_task_stream("dq.validate", {}))

    assert frames == [("error", "streaming not supported for 'dq.validate'")]


def test_dispatch_task_stream_engine_error_yields_error(monkeypatch):
    import ai.engine_runtime as rt

    async def fake_run_chat(instance_id, payload, task_id, *, stream_callback=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(rt, "_run_chat", fake_run_chat)

    frames = list(rt.dispatch_task_stream("chat", {"message": "hi"}))

    assert len(frames) == 1
    assert frames[0][0] == "error"
    assert "boom" in frames[0][1]


def test_dispatch_task_stream_passes_async_callback(monkeypatch):
    import ai.engine_runtime as rt

    captured: dict[str, object] = {}

    async def fake_run_chat(instance_id, payload, task_id, *, stream_callback=None):
        captured["cb"] = stream_callback
        await stream_callback("x")
        return {
            "status": "completed",
            "task_id": task_id,
            "result": {"content": "x", "follow_up_questions": [], "execution_ms": 0},
        }

    monkeypatch.setattr(rt, "_run_chat", fake_run_chat)

    list(rt.dispatch_task_stream("chat", {"message": "hi"}))

    assert inspect.iscoroutinefunction(captured["cb"])


# ── PulseProvider.chat_stream ────────────────────────────────────────────


def test_chat_stream_builds_payload_and_delegates():
    from ai.providers.pulse import PulseProvider

    provider = PulseProvider()
    request = ChatRequest(
        message="hello",
        conversation=ConversationContext(
            conversation_id="conv-1",
            messages=[
                {"role": "user", "content": "hi", "timestamp": "2024-01-01T00:00:00"}
            ],
        ),
        scope=Scope(),
    )

    with patch("ai.providers.pulse.dispatch_task_stream") as ds:
        ds.return_value = iter([("chunk", "He"), ("done", {"status": "completed"})])
        frames = list(provider.chat_stream(request))

    assert frames == [("chunk", "He"), ("done", {"status": "completed"})]
    payload = ds.call_args[0][1]
    assert payload["message"] == "hello"
    assert payload["conversation_history"]["conversation_id"] == "conv-1"


# ── CarbonIntelligence.send_message_stream ───────────────────────────────


@pytest.mark.django_db
def test_send_message_stream_persists_user_message_on_provider_error(user):
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

    assert AIMessage.objects.filter(
        conversation=conversation, role="user", content="hello"
    ).exists()
    conversation.refresh_from_db()
    assert conversation.status == "failed"
    assert any(f["type"] == "error" for f in frames)


@pytest.mark.django_db
def test_send_message_stream_emits_chunks_and_done_and_persists_ai(user):
    conversation = _make_conversation(user, "chat", {})

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat_stream.return_value = [
        ("chunk", "He"),
        ("chunk", "llo"),
        (
            "done",
            {
                "status": "completed",
                "task_id": "t1",
                "result": {
                    "content": "Hello",
                    "follow_up_questions": [],
                    "execution_ms": 1,
                },
            },
        ),
    ]

    ci = CarbonIntelligence()
    ci._provider = provider
    ci._guard_workspace_operation = MagicMock(
        return_value=(MagicMock(), "workspace_chat")
    )

    frames = list(ci.send_message_stream(user, str(conversation.id), "hi"))

    assert [f["type"] for f in frames] == ["chunk", "chunk", "done"]
    assert frames[0]["content"] == "He"
    assert frames[1]["content"] == "llo"
    assert frames[2]["type"] == "done"

    conversation.refresh_from_db()
    assert conversation.status == "completed"
    assert AIMessage.objects.filter(
        conversation=conversation, role="assistant", content="Hello"
    ).exists()


@pytest.mark.django_db
def test_send_message_stream_non_chat_streams_progress(user):
    conversation = _make_conversation(user, "dq_suggest", {})

    ci = CarbonIntelligence()

    def _fake_route(*args, **kwargs):
        conversation.status = "completed"
        conversation.save(update_fields=["status"])
        return {"id": "assistant-1", "role": "assistant"}

    ci._route_typed_message = MagicMock(side_effect=_fake_route)

    frames = list(ci.send_message_stream(user, str(conversation.id), "hi"))

    ci._route_typed_message.assert_called_once()
    types = [f["type"] for f in frames]
    assert types == ["progress", "progress", "done"]
    assert frames[0]["stage"] == "start"
    assert frames[0]["message"] == "Reading your table…"
    assert frames[1]["stage"] == "done"
    assert frames[2]["type"] == "done"

    # The non-chat path persists the user message itself (no sync delegation).
    assert AIMessage.objects.filter(
        conversation=conversation, role="user", content="hi"
    ).exists()
    conversation.refresh_from_db()
    assert conversation.status == "completed"


@pytest.mark.django_db
def test_send_message_stream_guard_rejection_not_stuck_working(user):
    conversation = _make_conversation(user, "chat", {})

    ci = CarbonIntelligence()
    ci._provider = MagicMock()
    ci._guard_workspace_operation = MagicMock(side_effect=ValueError("scope denied"))

    with pytest.raises(ValueError):
        list(ci.send_message_stream(user, str(conversation.id), "hi"))

    conversation.refresh_from_db()
    assert conversation.status == "failed"
    assert AIMessage.objects.filter(
        conversation=conversation, role="user", content="hi"
    ).exists()


# ── SSE endpoint ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_stream_endpoint_returns_sse_and_done_frame(user):
    from django.urls import reverse
    from rest_framework.test import APIClient

    conversation = _make_conversation(user, "chat", {})

    frames = [
        {"type": "chunk", "content": "He"},
        {"type": "done", "conversation": {"id": str(conversation.id), "messages": []}},
    ]
    fake = MagicMock()
    fake.send_message_stream.return_value = iter(frames)

    client = APIClient()
    client.force_authenticate(user=user)

    with patch("ai.workspace_api.CarbonIntelligence", return_value=fake):
        url = reverse(
            "ai-workspace-conversation-send-message-stream",
            kwargs={"pk": conversation.id},
        )
        response = client.post(url, {"content": "hello"}, format="json")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/event-stream")
        # StreamingHttpResponse is lazy — consume the stream while the
        # intelligence mock is still patched.
        body = b"".join(response.streaming_content).decode("utf-8")

    assert '"type": "done"' in body
    assert "He" in body


@pytest.mark.django_db
def test_stream_endpoint_invalid_conversation_emits_error_frame(user):
    from django.urls import reverse
    from rest_framework.test import APIClient

    fake = MagicMock()
    fake.send_message_stream.side_effect = ValueError("Conversation missing not found.")

    client = APIClient()
    client.force_authenticate(user=user)

    with patch("ai.workspace_api.CarbonIntelligence", return_value=fake):
        url = reverse(
            "ai-workspace-conversation-send-message-stream",
            kwargs={"pk": "00000000-0000-0000-0000-000000000000"},
        )
        response = client.post(url, {"content": "hello"}, format="json")
        assert response.status_code == 200
        # Consume the stream while the intelligence mock is still patched.
        body = b"".join(response.streaming_content).decode("utf-8")

    assert '"type": "error"' in body
    assert "not found" in body


@pytest.mark.django_db
def test_non_streaming_endpoint_unchanged(user):
    from django.urls import reverse
    from rest_framework.test import APIClient

    conversation = _make_conversation(user, "chat", {})

    fake = MagicMock()
    fake.send_message.return_value = {
        "conversation": {},
        "user_message": {},
        "assistant_message": {},
    }

    client = APIClient()
    client.force_authenticate(user=user)

    with patch("ai.workspace_api.CarbonIntelligence", return_value=fake):
        url = reverse(
            "ai-workspace-conversation-send-message",
            kwargs={"pk": conversation.id},
        )
        response = client.post(url, {"content": "hello"}, format="json")

    assert response.status_code == 200
    fake.send_message.assert_called_once()
    fake.send_message_stream.assert_not_called()
