"""Sprint 10 (Phase 10-D) — learning bridge tests.

Covers the outcome→signal mapping, the end-to-end ``learn_from_message`` bridge
(engine ``KgFeedbackRecord`` + ``MemoryLongTerm`` writes), idempotency via
``learned_at``, failure-retryability, ``learn_all_pending`` batching, and the
``learn_from_feedback`` management command.

The store seam is pinned to the Django backend (durable) via an autouse
fixture that resets the cached Store singleton before and after each test.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from django.core.management import call_command

from accounts.models import User
from ai.models import AIConversation, AIMessage, KgFeedbackRecord, MemoryLongTerm
from ai.store import reset_store


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _django_store(settings):
    settings.AI_STORE_BACKEND = "django"
    reset_store()
    yield
    reset_store()


@pytest.fixture
def user(db):
    return User.objects.create_user(username=f"learning-worker-{uuid4().hex[:8]}", password="secret123")


def _make_conversation(user, conversation_type="chat"):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json={},
        scope_json={},
    )


def _make_message(conversation, content="AI answer", role="assistant", outcome=None, correction_text=""):
    return AIMessage.objects.create(
        conversation=conversation,
        role=role,
        content=content,
        outcome=outcome,
        correction_text=correction_text,
    )


# ── 1. Pure mapping ──────────────────────────────────────────────────────


def test_outcome_signal_map_is_pure():
    from ai.learning import OUTCOME_SIGNAL_MAP, LEARNABLE_OUTCOMES

    assert OUTCOME_SIGNAL_MAP == {
        "accepted": "explicit_positive",
        "rejected": "explicit_negative",
        "corrected": "correction",
    }
    assert LEARNABLE_OUTCOMES == ["accepted", "rejected", "corrected"]
    assert "ignored" not in LEARNABLE_OUTCOMES


# ── 2. accepted ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_accepted_learns_feedback_and_memory(user):
    from ai.learning import learn_from_message

    content = f"AI answer {uuid4().hex[:10]}"
    conversation = _make_conversation(user)
    message = _make_message(conversation, content=content, outcome="accepted")

    assert learn_from_message(message) is True

    message.refresh_from_db()
    assert message.learned_at is not None

    recs = KgFeedbackRecord.objects.filter(message_id=str(message.id))
    assert recs.count() == 1
    assert recs.get().signal_type == "explicit_positive"

    facts = MemoryLongTerm.objects.filter(category="learned", content=content)
    assert facts.count() == 1


# ── 3. corrected ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_corrected_learns_correction_feedback_and_memory(user):
    from ai.learning import learn_from_message

    correction = f"Actually, it's {uuid4().hex[:10]}."
    conversation = _make_conversation(user)
    message = _make_message(
        conversation,
        content=f"AI answer {uuid4().hex[:10]}",
        outcome="corrected",
        correction_text=correction,
    )

    assert learn_from_message(message) is True

    message.refresh_from_db()
    assert message.learned_at is not None

    rec = KgFeedbackRecord.objects.filter(message_id=str(message.id)).get()
    assert rec.signal_type == "correction"
    assert rec.user_comment == correction
    assert rec.corrected_sql is None

    facts = MemoryLongTerm.objects.filter(category="correction", content=correction)
    assert facts.count() == 1


# ── 4. rejected ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_rejected_records_feedback_without_memory(user):
    from ai.learning import learn_from_message

    content = f"AI answer {uuid4().hex[:10]}"
    conversation = _make_conversation(user)
    message = _make_message(conversation, content=content, outcome="rejected")

    assert learn_from_message(message) is True

    rec = KgFeedbackRecord.objects.filter(message_id=str(message.id)).get()
    assert rec.signal_type == "explicit_negative"

    assert not MemoryLongTerm.objects.filter(content=content).exists()


# ── 5. ignored / unset outcome are no-ops ────────────────────────────────


@pytest.mark.django_db
def test_ignored_and_unset_outcome_are_noop(user):
    from ai.learning import learn_from_message

    conversation = _make_conversation(user)
    ignored = _make_message(conversation, content="x", outcome="ignored")
    unset = _make_message(conversation, content="y", outcome=None)

    assert learn_from_message(ignored) is False
    assert learn_from_message(unset) is False

    ignored.refresh_from_db()
    unset.refresh_from_db()
    assert ignored.learned_at is None
    assert unset.learned_at is None

    ids = [str(ignored.id), str(unset.id)]
    assert not KgFeedbackRecord.objects.filter(message_id__in=ids).exists()


# ── 6. failure leaves retryable ──────────────────────────────────────────


@pytest.mark.django_db
def test_failure_leaves_retryable(user, monkeypatch):
    from ai import learning

    async def _boom(message, signal_type, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(learning, "_learn_async", _boom)

    conversation = _make_conversation(user)
    message = _make_message(conversation, content="AI answer", outcome="accepted")

    with pytest.raises(RuntimeError):
        learning.learn_from_message(message)

    message.refresh_from_db()
    assert message.learned_at is None


# ── 6b. retry after partial failure is idempotent ────────────────────────


@pytest.mark.django_db
def test_retry_after_partial_failure_does_not_duplicate_feedback(user, monkeypatch):
    """A retry re-runs the memory write but never duplicates KgFeedbackRecord.

    The feedback write commits before the memory write; if the memory write
    fails the message stays retryable (``learned_at IS NULL``).  The retry must
    skip the already-recorded feedback instead of inserting a second row.
    """
    from ai import learning

    real_long_term_memory = learning.LongTermMemory

    class _FlakyMemory:
        calls = 0

        def __init__(self, session):
            self._real = real_long_term_memory(session)

        async def store_fact(self, **kwargs):
            type(self).calls += 1
            if type(self).calls == 1:
                raise RuntimeError("memory write boom")
            await self._real.store_fact(**kwargs)

    monkeypatch.setattr(learning, "LongTermMemory", _FlakyMemory)

    content = f"AI answer {uuid4().hex[:10]}"
    conversation = _make_conversation(user)
    message = _make_message(conversation, content=content, outcome="accepted")

    # First attempt: feedback write commits, memory write fails → retryable.
    with pytest.raises(RuntimeError):
        learning.learn_from_message(message)

    message.refresh_from_db()
    assert message.learned_at is None
    assert KgFeedbackRecord.objects.filter(message_id=str(message.id)).count() == 1
    assert not MemoryLongTerm.objects.filter(category="learned", content=content).exists()

    # Second attempt (retry): feedback already recorded → skipped; memory written.
    assert learning.learn_from_message(message) is True

    message.refresh_from_db()
    assert message.learned_at is not None
    assert KgFeedbackRecord.objects.filter(message_id=str(message.id)).count() == 1
    assert MemoryLongTerm.objects.filter(category="learned", content=content).count() == 1


# ── 7. learn_all_pending idempotency ─────────────────────────────────────


@pytest.mark.django_db
def test_learn_all_pending_is_idempotent(user):
    from ai.learning import learn_all_pending

    conversation = _make_conversation(user)
    _make_message(conversation, content="a", outcome="accepted")
    _make_message(conversation, content="b", outcome="corrected", correction_text="fix b")
    _make_message(conversation, content="c", outcome="rejected")
    _make_message(conversation, content="d", outcome="ignored")
    _make_message(conversation, content="e", outcome=None)

    stats = learn_all_pending()
    assert stats["processed"] == 3
    assert stats["accepted"] == 1
    assert stats["corrected"] == 1
    assert stats["rejected"] == 1
    assert stats["errors"] == 0

    second = learn_all_pending()
    assert second["processed"] == 0
    assert second["errors"] == 0


# ── 8. management command ────────────────────────────────────────────────


@pytest.mark.django_db
def test_management_command_limit_and_dry_run(user):
    from io import StringIO

    conversation = _make_conversation(user)
    _make_message(conversation, content="a", outcome="accepted")
    _make_message(conversation, content="b", outcome="rejected")
    _make_message(conversation, content="c", outcome="corrected", correction_text="fix c")

    # dry-run reports count and writes nothing.
    out = StringIO()
    call_command("learn_from_feedback", "--dry-run", stdout=out)
    assert "pending: 3" in out.getvalue()
    assert AIMessage.objects.filter(learned_at__isnull=True).count() == 3

    # --limit 2 processes at most 2.
    out = StringIO()
    call_command("learn_from_feedback", "--limit", "2", stdout=out)
    assert AIMessage.objects.filter(learned_at__isnull=False).count() == 2
    assert AIMessage.objects.filter(learned_at__isnull=True).count() == 1
