"""Sprint 13 — session lifecycle + message pagination tests.

Covers:
  * rename / pin / archive persistence
  * archived conversations excluded from the default list
  * hard delete (and owner-only enforcement)
  * cursor-based message pagination
  * first-message auto-titling
  * cross-user isolation
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from ai.intelligence import CarbonIntelligence
from ai.models import AIConversation, AIMessage
from backend.ai.protocol import ChatResponse, Scope


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(username="lifecycle-worker", password="secret123")


def _make_conversation(user, conversation_type="chat", payload=None) -> AIConversation:
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=payload or {},
        scope_json={},
    )


def _detail_url(conversation) -> str:
    return reverse("ai-workspace-conversation-detail", kwargs={"pk": conversation.id})


def _messages_url(conversation) -> str:
    # GET and POST share conversations/{id}/messages/ (merged action).
    return reverse("ai-workspace-conversation-send-message", kwargs={"pk": conversation.id})


# ── 1. Rename persists ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_rename_conversation_persists(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    updated = ci.update_conversation(user, str(conversation.id), title="Renamed session")
    assert updated["title"] == "Renamed session"

    refetched = ci.get_conversation(user, str(conversation.id))
    assert refetched["title"] == "Renamed session"


# ── 2. Archive excluded from default list ───────────────────────────────


@pytest.mark.django_db
def test_archive_excluded_from_default_list(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    ci.update_conversation(user, str(conversation.id), is_archived=True)

    default_ids = [c["id"] for c in ci.list_conversations(user)]
    assert str(conversation.id) not in default_ids

    archived = ci.list_conversations(user, is_archived=True)
    archived_ids = [c["id"] for c in archived]
    assert str(conversation.id) in archived_ids
    assert archived[0]["is_archived"] is True


# ── 3. Pin/unpin round-trips ────────────────────────────────────────────


@pytest.mark.django_db
def test_pin_unpin_roundtrip(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    pinned = ci.update_conversation(user, str(conversation.id), is_pinned=True)
    assert pinned["is_pinned"] is True

    unpinned = ci.update_conversation(user, str(conversation.id), is_pinned=False)
    assert unpinned["is_pinned"] is False

    refetched = ci.get_conversation(user, str(conversation.id))
    assert refetched["is_pinned"] is False


# ── 4. Delete removes + subsequent get 404 ──────────────────────────────


@pytest.mark.django_db
def test_delete_removes_conversation(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    result = ci.delete_conversation(user, str(conversation.id))
    assert result["deleted"] == str(conversation.id)
    assert not AIConversation.objects.filter(pk=conversation.pk).exists()

    with pytest.raises(ValueError):
        ci.get_conversation(user, str(conversation.id))


# ── 5. Message pagination (before cursor) ───────────────────────────────


@pytest.mark.django_db
def test_message_pagination_before_cursor(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    messages = []
    for i in range(5):
        m = AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=f"message {i}",
        )
        messages.append(m)

    # Pin strictly increasing timestamps so cursor math is deterministic.
    base = timezone.now()
    for i, m in enumerate(messages):
        AIMessage.objects.filter(pk=m.pk).update(created_at=base + timedelta(seconds=i))

    # `before` = messages[3] leaves three older messages (messages[0..2]); a
    # limit=2 page returns the two most recent of those and still has messages[0]
    # to page further (has_more=True).
    result = ci.list_messages(
        user,
        str(conversation.id),
        limit=2,
        before=str(messages[3].id),
    )

    assert len(result["messages"]) == 2
    assert result["has_more"] is True
    assert [m["id"] for m in result["messages"]] == [
        str(messages[2].id),
        str(messages[1].id),
    ]


@pytest.mark.django_db
def test_message_pagination_after_cursor(user):
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    messages = []
    for i in range(5):
        m = AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=f"message {i}",
        )
        messages.append(m)

    base = timezone.now()
    for i, m in enumerate(messages):
        AIMessage.objects.filter(pk=m.pk).update(created_at=base + timedelta(seconds=i))

    result = ci.list_messages(
        user,
        str(conversation.id),
        limit=2,
        after=str(messages[1].id),
    )

    assert len(result["messages"]) == 2
    assert result["has_more"] is True
    assert [m["id"] for m in result["messages"]] == [
        str(messages[2].id),
        str(messages[3].id),
    ]


# ── 6. Auto-title from first user message ───────────────────────────────


@pytest.mark.django_db
def test_auto_title_sets_first_40_chars(user):
    ci = CarbonIntelligence()

    provider = MagicMock()
    provider.provider_name = "dummy"
    provider.chat.return_value = ChatResponse(status="completed", content="ok")
    ci._provider = provider

    conversation = ci.create_conversation(user, "chat")
    conversation_id = conversation["id"]
    assert conversation["title"] == "Chat"

    content = "A" * 80
    scope = Scope(
        user_identifier=str(user.pk),
        is_superuser=True,
        org_unit_ids=["*"],
    )
    with patch("ai.intelligence.build_scope", return_value=scope):
        ci.send_message(user, conversation_id, content)

    conv = AIConversation.objects.get(id=conversation_id)
    assert conv.title == content[:40]


# ── 7. Cross-user isolation ─────────────────────────────────────────────


@pytest.mark.django_db
def test_cross_user_cannot_update_or_delete(user):
    ci = CarbonIntelligence()
    other = User.objects.create_user(username="lifecycle-other", password="secret123")
    conversation = _make_conversation(user, "chat", {})

    with pytest.raises(ValueError):
        ci.update_conversation(other, str(conversation.id), title="hijacked")
    with pytest.raises(ValueError):
        ci.delete_conversation(other, str(conversation.id))

    # Original untouched.
    assert ci.get_conversation(user, str(conversation.id))["title"] == "chat"


# ── Endpoint wiring (Task 5) ────────────────────────────────────────────


@pytest.mark.django_db
def test_patch_rename_endpoint(user):
    client = APIClient()
    client.force_authenticate(user=user)
    conversation = _make_conversation(user, "chat", {})

    response = client.patch(_detail_url(conversation), {"title": "New title"}, format="json")

    assert response.status_code == 200
    assert response.data["title"] == "New title"
    conversation.refresh_from_db()
    assert conversation.title == "New title"


@pytest.mark.django_db
def test_update_requires_at_least_one_field(user):
    client = APIClient()
    client.force_authenticate(user=user)
    conversation = _make_conversation(user, "chat", {})

    response = client.patch(_detail_url(conversation), {}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_endpoint(user):
    client = APIClient()
    client.force_authenticate(user=user)
    conversation = _make_conversation(user, "chat", {})

    response = client.delete(_detail_url(conversation))

    assert response.status_code == 200
    assert response.data["deleted"] == str(conversation.id)
    assert not AIConversation.objects.filter(pk=conversation.pk).exists()


@pytest.mark.django_db
def test_list_messages_endpoint(user):
    client = APIClient()
    client.force_authenticate(user=user)
    conversation = _make_conversation(user, "chat", {})

    for i in range(3):
        AIMessage.objects.create(conversation=conversation, role="user", content=f"m{i}")

    response = client.get(_messages_url(conversation), {"limit": 2})

    assert response.status_code == 200
    assert len(response.data["messages"]) == 2
    assert "has_more" in response.data


@pytest.mark.django_db
def test_cross_user_endpoint_returns_404(user):
    client = APIClient()
    conversation = _make_conversation(user, "chat", {})

    other = User.objects.create_user(username="lifecycle-intruder", password="secret123")
    client.force_authenticate(user=other)

    response = client.patch(
        _detail_url(conversation), {"title": "hijacked"}, format="json"
    )
    assert response.status_code == 404


# ── QA AI Workspace simulation regressions (F2, F3, F4) ─────────────────


@pytest.mark.django_db
def test_pinned_conversation_included_in_default_list(user):
    """F3 — a pinned conversation must not be dropped from the default list."""
    ci = CarbonIntelligence()
    pinned = _make_conversation(user, "chat", {})
    unpinned = _make_conversation(user, "chat", {})
    ci.update_conversation(user, str(pinned.id), is_pinned=True)

    ids = [c["id"] for c in ci.list_conversations(user)]
    assert str(pinned.id) in ids
    assert str(unpinned.id) in ids

    # And the API endpoint (serializer must yield is_pinned=None, not False).
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("ai-workspace-conversation-list"))
    assert response.status_code == 200
    ids = [c["id"] for c in response.data]
    assert str(pinned.id) in ids


@pytest.mark.django_db
def test_first_page_has_more_true(user):
    """F4 — the no-cursor first page must report has_more when more remain."""
    ci = CarbonIntelligence()
    conversation = _make_conversation(user, "chat", {})

    base = timezone.now()
    for i in range(55):
        m = AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=f"message {i}",
        )
        AIMessage.objects.filter(pk=m.pk).update(created_at=base + timedelta(seconds=i))

    result = ci.list_messages(user, str(conversation.id), limit=50)
    assert len(result["messages"]) == 50
    assert result["has_more"] is True


@pytest.mark.django_db
def test_export_fmt_markdown_and_bad_format(user):
    """F2 — ?fmt=markdown → 200, unsupported ?fmt=xml → 400."""
    client = APIClient()
    client.force_authenticate(user=user)
    conversation = _make_conversation(user, "chat", {})
    url = reverse("ai-workspace-conversation-export", kwargs={"pk": conversation.id})

    md = client.get(url, {"fmt": "markdown"})
    assert md.status_code == 200
    assert md.data["format"] == "markdown"

    bad = client.get(url, {"fmt": "xml"})
    assert bad.status_code == 400
