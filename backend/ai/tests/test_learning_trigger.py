"""Sprint 11 — learning trigger + scheduler + flywheel console tests.

Covers:

  * real-time trigger: POSTing feedback consumes the judgement immediately
    (KgFeedbackRecord + MemoryLongTerm written, learned_at set), and a learning
    failure never fails the feedback response.
  * flywheel status API: GET learning-status/ returns the pending/processed/
    facts shape for an authenticated admin.
  * manual sweep API: POST learning-status/run/ consumes pending rows.
  * run_learning_loop command: --status and --run-once.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from ai.store import reset_store

BASE = "/carbon-api/ai/pulse"


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    """Run the engine against the durable Django (Postgres) Store backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(
        username=f"learning-trigger-{uuid4().hex[:8]}", password="secret123"
    )


@pytest.fixture
def admin_user(db):
    from accounts.models import User

    u = User.objects.create_user(username=f"ai-trigger-{uuid4().hex[:8]}", password="secret123")
    u.is_superuser = True
    u.is_staff = True
    u.save()
    return u


@pytest.fixture
def auth_client(api_client, get_token_for_user, admin_user):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(admin_user)}")
    return api_client


def _make_conversation(user):
    from ai.models import AIConversation

    return AIConversation.objects.create(
        user=user,
        title="chat",
        conversation_type="chat",
        task_payload_json={},
        scope_json={},
    )


def _make_message(conversation, content="AI answer", role="assistant", outcome=None, learned=False, correction_text=""):
    from ai.models import AIMessage
    from django.utils import timezone

    return AIMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content,
        outcome=outcome,
        correction_text=correction_text,
        learned_at=timezone.now() if learned else None,
    )


def _feedback_url(conversation, message):
    return reverse(
        "ai-workspace-conversation-message-feedback",
        kwargs={"pk": conversation.id, "message_id": message.id},
    )


# ── 1. real-time trigger ─────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_feedback_post_triggers_learning(django_store, user):
    from rest_framework.test import APIClient
    from ai.models import KgFeedbackRecord, MemoryLongTerm

    conversation = _make_conversation(user)
    message = _make_message(conversation, content="AI answer")

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        _feedback_url(conversation, message),
        {"outcome": "accepted"},
        format="json",
    )

    assert resp.status_code == 200
    message.refresh_from_db()
    assert message.learned_at is not None

    rec = KgFeedbackRecord.objects.filter(message_id=str(message.id)).get()
    assert rec.signal_type == "explicit_positive"

    assert MemoryLongTerm.objects.filter(category="learned", content="AI answer").exists()


@pytest.mark.django_db(transaction=True)
def test_feedback_learning_failure_does_not_fail_feedback(django_store, user, monkeypatch):
    from rest_framework.test import APIClient
    from ai import learning

    conversation = _make_conversation(user)
    message = _make_message(conversation, content="AI answer")

    def _boom(msg):
        raise RuntimeError("engine down")

    monkeypatch.setattr(learning, "learn_from_message", _boom)

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        _feedback_url(conversation, message),
        {"outcome": "accepted"},
        format="json",
    )

    # Feedback still succeeds; the message stays retryable for the sweep.
    assert resp.status_code == 200
    assert resp.data["outcome"] == "accepted"
    message.refresh_from_db()
    assert message.learned_at is None


# ── 2. flywheel status + run API ─────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_learning_status_reports_flywheel(auth_client, django_store, admin_user):
    conversation = _make_conversation(admin_user)
    _make_message(conversation, content="done", outcome="accepted", learned=True)
    _make_message(conversation, content="todo", outcome="rejected")
    _make_message(conversation, content="ignored", outcome="ignored")

    resp = auth_client.get(f"{BASE}/learning-status/")
    assert resp.status_code == 200
    data = resp.data

    assert data["backend"] == "django"
    assert data["durable"] is True
    assert data["pending"] == 1
    assert data["processed"] == 1
    assert data["by_outcome"] == {"accepted": 1}


@pytest.mark.django_db(transaction=True)
def test_learning_run_consumes_pending(auth_client, django_store, admin_user):
    from ai.models import AIMessage

    conversation = _make_conversation(admin_user)
    _make_message(conversation, content="a", outcome="accepted")
    _make_message(conversation, content="b", outcome="corrected", correction_text="fix b")

    resp = auth_client.post(f"{BASE}/learning-status/run/", {})
    assert resp.status_code == 200
    assert resp.data["sweep"]["processed"] == 2

    assert AIMessage.objects.filter(learned_at__isnull=False).count() == 2
    assert resp.data["status"]["pending"] == 0


@pytest.mark.django_db(transaction=True)
def test_learning_status_requires_auth(api_client):
    assert api_client.get(f"{BASE}/learning-status/").status_code == 401


# ── 3. run_learning_loop command ─────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_run_learning_loop_status(django_store, user):
    from io import StringIO
    import json

    conversation = _make_conversation(user)
    _make_message(conversation, content="a", outcome="accepted")
    _make_message(conversation, content="b", outcome="rejected")

    out = StringIO()
    call_command("run_learning_loop", "--status", stdout=out)
    assert json.loads(out.getvalue()) == {"pending": 2}


@pytest.mark.django_db(transaction=True)
def test_run_learning_loop_run_once(django_store, user):
    from io import StringIO
    import json

    from ai.models import AIMessage

    conversation = _make_conversation(user)
    _make_message(conversation, content="a", outcome="accepted")

    out = StringIO()
    call_command("run_learning_loop", "--run-once", stdout=out)
    stats = json.loads(out.getvalue())
    assert stats["processed"] == 1
    assert AIMessage.objects.filter(learned_at__isnull=False).count() == 1
