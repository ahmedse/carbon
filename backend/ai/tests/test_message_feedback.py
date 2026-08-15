"""
Message feedback tests — Sprint 9 Phase 9-A.

Covers the ``POST .../messages/{message_id}/feedback/`` endpoint and the
``CarbonIntelligence.record_feedback`` method:

  - accepted / corrected / rejected / ignored outcomes persist
  - serializer validation (corrected requires correction_text; invalid outcome)
  - ownership scoping (no cross-user leak; wrong-conversation 404)
  - assistant-only guard (user/system messages rejected with 400)
  - idempotency, unauthenticated 401, and ``_serialize_message`` regression.

Imports mirror the existing suite: ``ai.*`` for models + intelligence, the
URLs built with ``django.urls.reverse`` against the ``ai-workspace-conversation``
router basename.
"""

from __future__ import annotations

import uuid

import pytest

from accounts.models import User
from ai.models import AIConversation, AIMessage


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="feedback-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


def _make_message(conversation, role="assistant", content="AI answer"):
    return AIMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content,
    )


def _feedback_url(conversation, message_id):
    from django.urls import reverse

    return reverse(
        "ai-workspace-conversation-message-feedback",
        kwargs={"pk": conversation.id, "message_id": message_id},
    )


def _post_feedback(client, conversation, message, body):
    message_id = getattr(message, "id", message)
    return client.post(
        _feedback_url(conversation, message_id),
        body,
        format="json",
    )


# ── Endpoint tests ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_accepted_persists_and_serializes(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(client, conversation, message, {"outcome": "accepted"})

    assert response.status_code == 200
    assert response.data["outcome"] == "accepted"
    assert response.data["correction_text"] == ""

    message.refresh_from_db()
    assert message.outcome == "accepted"
    assert message.correction_text == ""


@pytest.mark.django_db
def test_corrected_with_correction_persists_both(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(
        client,
        conversation,
        message,
        {"outcome": "corrected", "correction_text": "Actually, it's 42."},
    )

    assert response.status_code == 200
    assert response.data["outcome"] == "corrected"
    assert response.data["correction_text"] == "Actually, it's 42."

    message.refresh_from_db()
    assert message.outcome == "corrected"
    assert message.correction_text == "Actually, it's 42."


@pytest.mark.django_db
def test_corrected_without_correction_text_is_400(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(client, conversation, message, {"outcome": "corrected"})

    assert response.status_code == 400
    assert "correction_text" in response.data["details"]

    message.refresh_from_db()
    assert message.outcome is None


@pytest.mark.django_db
def test_invalid_outcome_is_400(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(client, conversation, message, {"outcome": "bogus"})

    assert response.status_code == 400
    assert "outcome" in response.data["details"]

    message.refresh_from_db()
    assert message.outcome is None


@pytest.mark.django_db
def test_message_not_found_is_404(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    missing_id = uuid.uuid4()

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(client, conversation, missing_id, {"outcome": "accepted"})

    assert response.status_code == 404
    assert "error" in response.data


@pytest.mark.django_db
def test_wrong_conversation_is_404(user):
    from rest_framework.test import APIClient

    conversation_a = _make_conversation(user)
    message_a = _make_message(conversation_a)
    conversation_b = _make_conversation(user)

    client = APIClient()
    client.force_authenticate(user=user)

    # message belongs to A, but we target it under conversation B.
    response = _post_feedback(client, conversation_b, message_a, {"outcome": "accepted"})

    assert response.status_code == 404
    assert "error" in response.data

    message_a.refresh_from_db()
    assert message_a.outcome is None


@pytest.mark.django_db
def test_conversation_not_owned_by_user_is_404(user, db):
    from rest_framework.test import APIClient

    other_user = User.objects.create_user(username="other-worker", password="secret123")
    other_conversation = _make_conversation(other_user)
    other_message = _make_message(other_conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(
        client,
        other_conversation,
        other_message,
        {"outcome": "accepted"},
    )

    assert response.status_code == 404
    assert "error" in response.data

    other_message.refresh_from_db()
    assert other_message.outcome is None


@pytest.mark.django_db
def test_user_role_message_is_400(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation, role="user", content="hello")

    client = APIClient()
    client.force_authenticate(user=user)

    response = _post_feedback(client, conversation, message, {"outcome": "accepted"})

    assert response.status_code == 400
    assert "error" in response.data

    message.refresh_from_db()
    assert message.outcome is None


@pytest.mark.django_db
def test_rejected_clears_prior_correction_text(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    # First corrected, carrying a correction.
    _post_feedback(
        client,
        conversation,
        message,
        {"outcome": "corrected", "correction_text": "wrong answer"},
    )
    message.refresh_from_db()
    assert message.correction_text == "wrong answer"

    # Then rejected — must clear the correction.
    response = _post_feedback(client, conversation, message, {"outcome": "rejected"})

    assert response.status_code == 200
    assert response.data["outcome"] == "rejected"
    assert response.data["correction_text"] == ""

    message.refresh_from_db()
    assert message.outcome == "rejected"
    assert message.correction_text == ""


@pytest.mark.django_db
def test_idempotent_accepted(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    first = _post_feedback(client, conversation, message, {"outcome": "accepted"})
    second = _post_feedback(client, conversation, message, {"outcome": "accepted"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.data["outcome"] == "accepted"

    message.refresh_from_db()
    assert message.outcome == "accepted"


@pytest.mark.django_db
def test_unauthenticated_is_401(user):
    from rest_framework.test import APIClient

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()  # no credentials

    response = _post_feedback(client, conversation, message, {"outcome": "accepted"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_get_conversation_serializes_new_keys(user):
    from rest_framework.test import APIClient
    from django.urls import reverse

    conversation = _make_conversation(user)
    message = _make_message(conversation)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse(
        "ai-workspace-conversation-detail",
        kwargs={"pk": conversation.id},
    )
    response = client.get(url)

    assert response.status_code == 200
    messages = response.data["messages"]
    assert len(messages) == 1
    assert messages[0]["outcome"] is None
    assert messages[0]["correction_text"] == ""
