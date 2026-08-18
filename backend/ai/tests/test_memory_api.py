"""Phase 23-A — AI memory & learnt-facts API tests.

Covers:

* auth — all four routes 401 when unauthenticated
* GET /ai/memory/facts/ — returns own private + shared + global facts, hides
  other users' private facts, excludes archived/superseded, supports
  ?category= and ?limit=
* GET /ai/memory/episodes/ — same scoping for raw episodic memory
* GET /ai/memory/relationship/ — computed-on-read shape (memory counts +
  top categories + avg confidence, usage, profile), never persisted, and
  respects the Phase 22-A ``memory_enabled`` flag
* DELETE /ai/memory/facts/{pk}/ — owner forget = 204 + hard delete + cascade
  (superseded_by / superseded: sources) + AuditLog row on every forget;
  other users' private facts = 404; visible-but-not-owned shared facts = 403
  for regular users (superuser/global admin may); unknown id = 404
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from ai.models import (
    AIUserProfile,
    AuditLog,
    MemoryEpisodic,
    MemoryLongTerm,
)


@pytest.fixture
def owner(db) -> User:
    return User.objects.create_user(username="memory-owner", password="secret123")


@pytest.fixture
def other(db) -> User:
    return User.objects.create_user(username="memory-other", password="secret123")


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_superuser(
        username="memory-admin", password="secret123",
    )


@pytest.fixture
def client():
    return APIClient()


def _fact(**overrides) -> MemoryLongTerm:
    base = {
        "instance_id": "carbon",
        "category": "preference",
        "content": "owner prefers CSV exports",
        "confidence": 0.9,
        "visibility": "private",
    }
    base.update(overrides)
    return MemoryLongTerm.objects.create(**base)


def _episode(**overrides) -> MemoryEpisodic:
    from django.utils import timezone

    base = {
        "instance_id": "carbon",
        "event_type": "milestone",
        "summary": "schema change shipped",
        "occurred_at": timezone.now(),
        "visibility": "private",
    }
    base.update(overrides)
    return MemoryEpisodic.objects.create(**base)


def _auth(client, user):
    client.force_authenticate(user=user)
    return client


# ── auth ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_memory_routes_require_auth(client):
    for url_name in (
        "ai-memory-facts",
        "ai-memory-episodes",
        "ai-memory-relationship",
    ):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 401, url_name

    resp = client.delete(reverse("ai-memory-fact-delete", args=["nope"]))
    assert resp.status_code == 401


# ── GET facts ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_facts_scoped_to_owner_shared_global(client, owner, other):
    mine = _fact(
        category="preference", content="mine", host_user_id=str(owner.pk),
        visibility="private",
    )
    shared = _fact(
        category="org", content="shared fact", visibility="shared",
    )
    global_fact = _fact(
        category="learned", content="global fact", visibility="global",
    )
    _fact(
        category="pref", content="other user private", host_user_id=str(other.pk),
        visibility="private",
    )
    _fact(
        category="pref", content="archived", host_user_id=str(owner.pk),
        visibility="private", archived=True,
    )
    _fact(
        category="pref", content="superseded", host_user_id=str(owner.pk),
        visibility="private", superseded_by="replacement-id",
    )

    _auth(client, owner)
    resp = client.get(reverse("ai-memory-facts"))
    assert resp.status_code == 200
    body = resp.json()
    contents = {r["content"] for r in body["results"]}
    assert contents == {"mine", "shared fact", "global fact"}
    assert "other user private" not in contents
    assert "archived" not in contents
    assert "superseded" not in contents

    ids = {r["id"] for r in body["results"]}
    assert {mine.pk, shared.pk, global_fact.pk} <= ids


@pytest.mark.django_db
def test_facts_include_confidence_and_provenance(client, owner):
    fact = _fact(
        category="learned", content="learned fact", confidence=0.42,
        source="user_feedback:msg-123", host_user_id=str(owner.pk),
        visibility="private",
    )
    _auth(client, owner)
    body = client.get(reverse("ai-memory-facts")).json()
    row = next(r for r in body["results"] if r["id"] == fact.pk)
    assert row["confidence"] == 0.42
    assert row["provenance"]["source"] == "user_feedback:msg-123"
    assert row["provenance"]["created_at"] == fact.created_at.isoformat()


@pytest.mark.django_db
def test_facts_category_filter_and_limit(client, owner):
    for i in range(6):
        _fact(
            category="preference" if i % 2 else "learned",
            content=f"fact-{i}",
            host_user_id=str(owner.pk),
            visibility="private",
        )
    _auth(client, owner)
    body = client.get(reverse("ai-memory-facts"), {"category": "preference"}).json()
    assert body["count"] == 3
    assert all(r["category"] == "preference" for r in body["results"])

    body = client.get(reverse("ai-memory-facts"), {"limit": 2}).json()
    assert body["count"] == 2


@pytest.mark.django_db
def test_facts_order_newest_first(client, owner):
    first = _fact(
        content="old", host_user_id=str(owner.pk), visibility="private",
    )
    second = _fact(
        content="new", host_user_id=str(owner.pk), visibility="private",
    )
    _auth(client, owner)
    body = client.get(reverse("ai-memory-facts")).json()
    ids = [r["id"] for r in body["results"]]
    assert ids.index(second.pk) < ids.index(first.pk)


# ── GET episodes ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_episodes_scoped_to_owner_shared_global(client, owner, other):
    mine = _episode(
        event_type="milestone", summary="mine", host_user_id=str(owner.pk),
        visibility="private",
    )
    shared = _episode(event_type="anomaly", summary="shared", visibility="shared")
    _episode(
        event_type="error", summary="other private", host_user_id=str(other.pk),
        visibility="private",
    )
    _episode(
        event_type="error", summary="archived", host_user_id=str(owner.pk),
        visibility="private", archived=True,
    )

    _auth(client, owner)
    body = client.get(reverse("ai-memory-episodes")).json()
    summaries = {r["summary"] for r in body["results"]}
    assert summaries == {"mine", "shared"}
    assert "other private" not in summaries
    assert "archived" not in summaries
    ids = {r["id"] for r in body["results"]}
    assert {mine.pk, shared.pk} <= ids


@pytest.mark.django_db
def test_episodes_event_type_filter(client, owner):
    _episode(event_type="milestone", summary="m1", host_user_id=str(owner.pk))
    _episode(event_type="anomaly", summary="a1", host_user_id=str(owner.pk))
    _auth(client, owner)
    body = client.get(
        reverse("ai-memory-episodes"), {"event_type": "anomaly"}
    ).json()
    assert body["count"] == 1
    assert body["results"][0]["summary"] == "a1"


# ── GET relationship ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_relationship_computed_shape(client, owner):
    _fact(category="preference", content="p1", confidence=0.9,
          host_user_id=str(owner.pk), visibility="private")
    _fact(category="learned", content="l1", confidence=0.5, use_count=3,
          host_user_id=str(owner.pk), visibility="private")
    _episode(event_type="milestone", summary="e1", host_user_id=str(owner.pk))

    _auth(client, owner)
    resp = client.get(reverse("ai-memory-relationship"))
    assert resp.status_code == 200
    body = resp.json()

    assert body["memory_enabled"] is True
    assert body["memory"]["fact_count"] == 2
    assert body["memory"]["episode_count"] == 1
    cats = {c["category"]: c["count"] for c in body["memory"]["top_categories"]}
    assert cats == {"preference": 1, "learned": 1}
    assert body["memory"]["avg_confidence"] == pytest.approx(0.7, abs=0.001)
    assert body["memory"]["total_uses"] == 3

    assert "usage" in body
    assert body["usage"]["total_generations"] == 0
    assert "quota" in body["usage"]

    assert body["profile"]["memory_enabled"] is True
    assert body["profile"]["temperature"] == 0.3
    assert "computed_at" in body


@pytest.mark.django_db
def test_relationship_respects_memory_enabled(client, owner):
    profile, _ = AIUserProfile.objects.get_or_create(user=owner)
    profile.memory_enabled = False
    profile.save()
    _fact(content="f", host_user_id=str(owner.pk), visibility="private")

    _auth(client, owner)
    body = client.get(reverse("ai-memory-relationship")).json()
    assert body["memory_enabled"] is False
    assert body["profile"]["memory_enabled"] is False
    # Reads are never gated by the preference (GDPR visibility) — data shown.
    assert body["memory"]["fact_count"] == 1


# ── DELETE facts/{pk} — forget ──────────────────────────────────────────


@pytest.mark.django_db
def test_forget_own_fact_hard_deletes_and_audits(client, owner):
    fact = _fact(
        category="preference", content="forget me",
        source="user_feedback:msg-1", host_user_id=str(owner.pk),
        visibility="private",
    )
    derived = _fact(
        category="preference", content="derived replacement",
        source=f"superseded:{fact.pk}", host_user_id=str(owner.pk),
        visibility="private",
    )
    older = _fact(
        category="preference", content="older lineage",
        superseded_by=fact.pk, host_user_id=str(owner.pk),
        visibility="private",
    )
    keep = _fact(
        category="learned", content="keep me", host_user_id=str(owner.pk),
        visibility="private",
    )

    _auth(client, owner)
    resp = client.delete(reverse("ai-memory-fact-delete", args=[fact.pk]))
    assert resp.status_code == 204

    # Hard delete — row gone, not soft-deleted.
    assert not MemoryLongTerm.objects.filter(pk=fact.pk).exists()
    # Cascade — derived replacement + older lineage pointing at it are gone.
    assert not MemoryLongTerm.objects.filter(pk=derived.pk).exists()
    assert not MemoryLongTerm.objects.filter(pk=older.pk).exists()
    # Unrelated fact survives.
    assert MemoryLongTerm.objects.filter(pk=keep.pk).exists()

    # Audit log entry on every forget (who/when/what).
    log = AuditLog.objects.filter(action="memory.forget").order_by("-created_at").first()
    assert log is not None
    assert log.actor == str(owner.pk)
    assert log.actor_type == "user"
    assert log.target == str(fact.pk)
    assert log.detail["model"] == "MemoryLongTerm"
    assert set(log.detail["cascade"]) == {fact.pk, derived.pk, older.pk}
    assert log.detail["rows_deleted"] == 3


@pytest.mark.django_db
def test_forget_other_users_private_fact_is_404(client, owner, other):
    fact = _fact(
        content="other private", host_user_id=str(other.pk), visibility="private",
    )
    _auth(client, owner)
    resp = client.delete(reverse("ai-memory-fact-delete", args=[fact.pk]))
    assert resp.status_code == 404
    assert MemoryLongTerm.objects.filter(pk=fact.pk).exists()
    assert not AuditLog.objects.filter(target=str(fact.pk)).exists()


@pytest.mark.django_db
def test_forget_shared_fact_not_owned_is_403(client, owner):
    shared = _fact(content="shared fact", visibility="shared", host_user_id=None)
    _auth(client, owner)
    resp = client.delete(reverse("ai-memory-fact-delete", args=[shared.pk]))
    assert resp.status_code == 403
    assert MemoryLongTerm.objects.filter(pk=shared.pk).exists()
    assert not AuditLog.objects.filter(target=str(shared.pk)).exists()


@pytest.mark.django_db
def test_forget_shared_fact_by_admin_allowed(client, admin_user):
    shared = _fact(content="shared fact", visibility="shared", host_user_id=None)
    _auth(client, admin_user)
    resp = client.delete(reverse("ai-memory-fact-delete", args=[shared.pk]))
    assert resp.status_code == 204
    assert not MemoryLongTerm.objects.filter(pk=shared.pk).exists()
    assert AuditLog.objects.filter(action="memory.forget", target=str(shared.pk)).exists()


@pytest.mark.django_db
def test_forget_unknown_fact_is_404(client, owner):
    _auth(client, owner)
    resp = client.delete(reverse("ai-memory-fact-delete", args=["does-not-exist"]))
    assert resp.status_code == 404
    assert not AuditLog.objects.filter(target="does-not-exist").exists()


@pytest.mark.django_db
def test_forget_never_gated_by_memory_enabled(client, owner):
    """GDPR right to erasure must work even when collection is off."""
    profile, _ = AIUserProfile.objects.get_or_create(user=owner)
    profile.memory_enabled = False
    profile.save()

    fact = _fact(
        content="forget despite disabled", host_user_id=str(owner.pk),
        visibility="private",
    )
    _auth(client, owner)
    resp = client.delete(reverse("ai-memory-fact-delete", args=[fact.pk]))
    assert resp.status_code == 204
    assert not MemoryLongTerm.objects.filter(pk=fact.pk).exists()
    assert AuditLog.objects.filter(action="memory.forget", target=str(fact.pk)).exists()
