"""Sprint 20 W1-B — conversation checkpoint / restore / fork / clear-context.

Covers the intelligence layer + REST surface for the context-lifecycle seam:

  * checkpoint — named, idempotent snapshot of the assembled working context
    (messages + budget + kg_entities + memory); same name overwrites.
  * restore — re-seeds the conversation's *working* context (summary + context
    snapshot) from a checkpoint WITHOUT touching the durable AIMessage log.
  * fork — clones the conversation into a NEW AIConversation row seeded at the
    checkpoint boundary; the new id never aliases the source row.
  * clear-context — resets the working context levers; leaves the message log,
    per-message provenance, and learned facts untouched.
  * CBAC — mutating actions require ``ai:manage_console``; the checkpoints
    read requires ``ai:view_console``.

Acceptance bar (Notes for the Master):
  1. Fork must produce a NEW conversation id — explicit test below.
  2. Clear must leave ``context_snapshot_json`` on existing messages untouched
     — explicit test below (message provenance lives in
     ``metadata_json["context_snapshot"]``).
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts import capabilities as caps_mod
from ai.intelligence import CarbonIntelligence
from ai.models import (
    AIConversation,
    AIMessage,
    ConversationCheckpoint,
)


# ── Fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def owner(db):
    from accounts.models import User

    return User.objects.create_user(username="w1b-owner", password="secret123")


@pytest.fixture
def manager(db, create_scoped_role):
    """Global admin — has ai:manage_console (wildcard admins_group)."""
    from accounts.models import User

    user = User.objects.create_user(username="w1b-manager", password="secret123")
    create_scoped_role(user, "admins_group", org_unit=None, module=None)
    return user


@pytest.fixture
def plain_user(db):
    from accounts.models import User

    return User.objects.create_user(username="w1b-plain", password="secret123")


@pytest.fixture
def view_only_user(db, monkeypatch, create_scoped_role):
    """Has ai:view_console but NOT ai:manage_console."""
    from accounts.models import User

    monkeypatch.setitem(
        caps_mod.GROUP_CAPABILITIES,
        "w1b_ai_console_viewer",
        {caps_mod.AI_VIEW_CONSOLE.key},
    )
    user = User.objects.create_user(username="w1b-viewer", password="secret123")
    create_scoped_role(user, "w1b_ai_console_viewer", org_unit=None, module=None)
    return user


@pytest.fixture
def shared_org(db, create_scoped_role, owner):
    """Org both owner and viewers belong to (shared-conversation access)."""
    from mdm.models import OrgUnit

    org = OrgUnit.objects.create(name="W1B Shared Org", slug="w1b-shared-org")
    create_scoped_role(owner, "viewers_group", org_unit=org)
    return org


def _share_conversation(conversation, org):
    conversation.scope_json = {"org_unit_ids": [str(org.id)]}
    conversation.visibility = "shared"
    conversation.save(update_fields=["scope_json", "visibility"])
    return conversation


def _make_conversation(user, title="Thread", n_messages=0, summary=""):
    conv = AIConversation.objects.create(
        user=user,
        title=title,
        conversation_type="chat",
        visibility="private",
        scope_json={},
        summary=summary,
    )
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        AIMessage.objects.create(
            conversation=conv,
            role=role,
            content=f"message-{i}",
            metadata_json={
                "context_snapshot": {"budget": {"T2_history": i}},
            },
            token_usage_json={},
        )
    return conv


def _checkpoint_url(conversation) -> str:
    return reverse(
        "ai-workspace-conversation-checkpoint-conversation",
        kwargs={"pk": conversation.id},
    )


def _checkpoints_url(conversation) -> str:
    return reverse(
        "ai-workspace-conversation-checkpoints",
        kwargs={"pk": conversation.id},
    )


def _restore_url(conversation) -> str:
    return reverse(
        "ai-workspace-conversation-restore-conversation",
        kwargs={"pk": conversation.id},
    )


def _fork_url(conversation) -> str:
    return reverse(
        "ai-workspace-conversation-fork-conversation",
        kwargs={"pk": conversation.id},
    )


def _clear_url(conversation) -> str:
    return reverse(
        "ai-workspace-conversation-clear-context",
        kwargs={"pk": conversation.id},
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Checkpoint (intelligence layer) ─────────────────────────────────────
@pytest.mark.django_db
def test_checkpoint_persists_assembled_bundle(owner):
    conversation = _make_conversation(owner, n_messages=4, summary="rolling summary")
    ci = CarbonIntelligence()

    result = ci.checkpoint_conversation(
        owner, str(conversation.id), name="v1", note="before the pivot",
    )

    assert result["name"] == "v1"
    assert result["note"] == "before the pivot"
    assert result["conversation_id"] == str(conversation.id)
    assert result["owner_id"] == str(owner.id)
    assert result["message_boundary_id"] is not None

    row = ConversationCheckpoint.objects.get(
        conversation=conversation, name="v1",
    )
    snapshot = row.snapshot_json
    assert "budget" in snapshot
    assert "kg_entities" in snapshot
    assert "context_signature" in snapshot and snapshot["context_signature"]
    assert "summary" in snapshot and snapshot["summary"] == "rolling summary"
    # Snapshot carries the tiered history turns (4 created) + boundary.
    history_contents = [
        m["content"]
        for m in snapshot["messages"]
        if m["role"] in ("user", "assistant")
    ]
    assert history_contents == [
        "message-0", "message-1", "message-2", "message-3",
    ]
    assert snapshot["message_boundary_id"] == str(
        conversation.messages.order_by("-created_at").first().id
    )

    # Picker payload exposes metadata without dumping message bodies.
    assert result["snapshot"]["message_count"] == 4
    assert result["snapshot"]["summary"] == "rolling summary"


@pytest.mark.django_db
def test_checkpoint_same_name_overwrites_idempotently(owner):
    conversation = _make_conversation(owner, n_messages=2)
    ci = CarbonIntelligence()

    first = ci.checkpoint_conversation(owner, str(conversation.id), name="v1", note="old")
    assert ConversationCheckpoint.objects.filter(
        conversation=conversation,
    ).count() == 1

    # Add more messages, then overwrite the same name.
    AIMessage.objects.create(
        conversation=conversation, role="user", content="message-2",
        metadata_json={}, token_usage_json={},
    )
    second = ci.checkpoint_conversation(
        owner, str(conversation.id), name="v1", note="updated",
    )

    assert second["id"] == first["id"]
    assert second["note"] == "updated"
    assert ConversationCheckpoint.objects.filter(
        conversation=conversation,
    ).count() == 1
    row = ConversationCheckpoint.objects.get(conversation=conversation, name="v1")
    history_contents = [
        m["content"]
        for m in row.snapshot_json["messages"]
        if m["role"] in ("user", "assistant")
    ]
    assert history_contents == [
        "message-0", "message-1", "message-2",
    ]


@pytest.mark.django_db
def test_checkpoint_missing_conversation_raises(owner):
    with pytest.raises(ValueError):
        CarbonIntelligence().checkpoint_conversation(
            owner, "00000000-0000-0000-0000-000000000000", name="v1",
        )


@pytest.mark.django_db
def test_list_checkpoints_newest_first(owner):
    conversation = _make_conversation(owner, n_messages=1)
    ci = CarbonIntelligence()
    ci.checkpoint_conversation(owner, str(conversation.id), name="first")
    ci.checkpoint_conversation(owner, str(conversation.id), name="second")

    checkpoints = ci.list_checkpoints(owner, str(conversation.id))
    assert [c["name"] for c in checkpoints] == ["second", "first"]


# ── Restore (intelligence layer) ─────────────────────────────────────────
@pytest.mark.django_db
def test_restore_reseeds_working_context_without_touching_log(owner):
    conversation = _make_conversation(
        owner, n_messages=3, summary="original summary",
    )
    ci = CarbonIntelligence()
    checkpoint = ci.checkpoint_conversation(
        owner, str(conversation.id), name="v1",
    )

    # Drift the working context away from the checkpoint.
    conversation.summary = "drifted summary"
    conversation.context_snapshot_json = {"budget": {"drifted": True}}
    conversation.save(update_fields=["summary", "context_snapshot_json"])

    restored = ci.restore_conversation(
        owner, str(conversation.id), checkpoint["id"],
    )

    assert restored["summary"] == "original summary"
    assert restored["context_snapshot_json"]["restored_from_checkpoint"] == (
        checkpoint["id"]
    )
    assert restored["context_snapshot_json"]["budget"] != {}
    # Durable log untouched: same message rows, same provenance metadata.
    messages = list(conversation.messages.order_by("created_at"))
    assert len(messages) == 3
    assert all(m.metadata_json["context_snapshot"] for m in messages)


@pytest.mark.django_db
def test_restore_missing_checkpoint_raises(owner):
    conversation = _make_conversation(owner, n_messages=1)
    with pytest.raises(ValueError):
        CarbonIntelligence().restore_conversation(
            owner,
            str(conversation.id),
            "00000000-0000-0000-0000-000000000000",
        )


@pytest.mark.django_db
def test_restore_requires_conversation_access(owner, plain_user):
    conversation = _make_conversation(owner, n_messages=1)
    ci = CarbonIntelligence()
    checkpoint = ci.checkpoint_conversation(owner, str(conversation.id), name="v1")

    # A user without access cannot restore someone else's private conversation.
    with pytest.raises(ValueError):
        ci.restore_conversation(plain_user, str(conversation.id), checkpoint["id"])


# ── Fork (intelligence layer) ────────────────────────────────────────────
@pytest.mark.django_db
def test_fork_creates_new_conversation_id_no_aliasing(owner):
    conversation = _make_conversation(
        owner, n_messages=4, summary="seed summary",
    )
    ci = CarbonIntelligence()
    checkpoint = ci.checkpoint_conversation(owner, str(conversation.id), name="v1")

    fork = ci.fork_conversation(owner, str(conversation.id), checkpoint["id"])

    # NEW row — never aliases the source.
    assert fork["id"] != str(conversation.id)
    assert AIConversation.objects.filter(user=owner).count() == 2
    fork_row = AIConversation.objects.get(id=fork["id"])
    assert fork_row.title == "Thread — fork"
    assert fork_row.conversation_type == "chat"
    assert fork_row.scope_json == conversation.scope_json
    # Working context seeded from the checkpoint.
    assert fork_row.summary == "seed summary"
    assert fork_row.context_snapshot_json["forked_from"] == str(conversation.id)
    # Durable log cloned (4 messages, same content/order).
    assert fork_row.messages.count() == 4
    fork_contents = list(
        fork_row.messages.order_by("created_at").values_list("content", flat=True)
    )
    assert fork_contents == [
        "message-0", "message-1", "message-2", "message-3",
    ]


@pytest.mark.django_db
def test_fork_respects_message_boundary(owner):
    conversation = _make_conversation(owner, n_messages=2)
    ci = CarbonIntelligence()
    checkpoint = ci.checkpoint_conversation(owner, str(conversation.id), name="v1")

    # New messages AFTER the checkpoint boundary — not part of the fork.
    for i in (2, 3):
        AIMessage.objects.create(
            conversation=conversation,
            role="user",
            content=f"message-{i}",
            metadata_json={},
            token_usage_json={},
        )

    fork = ci.fork_conversation(owner, str(conversation.id), checkpoint["id"])
    fork_row = AIConversation.objects.get(id=fork["id"])

    assert fork_row.messages.count() == 2
    assert conversation.messages.count() == 4
    assert list(
        fork_row.messages.order_by("created_at").values_list("content", flat=True)
    ) == ["message-0", "message-1"]


@pytest.mark.django_db
def test_fork_missing_checkpoint_raises(owner):
    conversation = _make_conversation(owner, n_messages=1)
    with pytest.raises(ValueError):
        CarbonIntelligence().fork_conversation(
            owner,
            str(conversation.id),
            "00000000-0000-0000-0000-000000000000",
        )


# ── Clear context (intelligence layer) ───────────────────────────────────
@pytest.mark.django_db
def test_clear_context_resets_working_context_keeps_log_and_provenance(owner):
    conversation = _make_conversation(owner, n_messages=3, summary="some summary")
    conversation.context_snapshot_json = {
        "budget": {"T2_history": 3},
        "kg_entities": ["kg-1"],
    }
    conversation.save(update_fields=["context_snapshot_json"])
    message_ids_before = set(
        conversation.messages.values_list("id", flat=True),
    )
    provenance_before = {
        m.id: m.metadata_json.get("context_snapshot")
        for m in conversation.messages.all()
    }

    result = CarbonIntelligence().clear_context(owner, str(conversation.id))

    # Working-context levers reset…
    assert result["summary"] == ""
    assert result["context_snapshot_json"] == {}
    # …but the conversation row, message log, and per-message provenance
    # (metadata_json["context_snapshot"]) are untouched.
    conversation.refresh_from_db()
    assert set(conversation.messages.values_list("id", flat=True)) == (
        message_ids_before
    )
    for message in conversation.messages.all():
        assert message.metadata_json.get("context_snapshot") == (
            provenance_before[message.id]
        )
    assert conversation.visibility == "private"
    assert conversation.title == "Thread"


@pytest.mark.django_db
def test_clear_context_releases_stuck_working_status(owner):
    conversation = _make_conversation(owner, n_messages=1)
    conversation.status = "working"
    conversation.save(update_fields=["status"])

    result = CarbonIntelligence().clear_context(owner, str(conversation.id))

    assert result["status"] == "pending"


# ── REST surface ─────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_checkpoint_endpoint_roundtrip(manager):
    conversation = _make_conversation(manager, n_messages=2)
    client = _client(manager)

    resp = client.post(
        _checkpoint_url(conversation),
        {"name": "v1", "note": "baseline"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data["name"] == "v1"
    assert resp.data["snapshot"]["message_count"] == 2

    listed = client.get(_checkpoints_url(conversation))
    assert listed.status_code == 200
    assert listed.data["checkpoints"][0]["id"] == resp.data["id"]

    restored = client.post(
        _restore_url(conversation),
        {"checkpoint_id": resp.data["id"]},
        format="json",
    )
    assert restored.status_code == 200, restored.content
    assert restored.data["context_snapshot_json"]["restored_from_checkpoint"] == (
        resp.data["id"]
    )

    forked = client.post(
        _fork_url(conversation),
        {"checkpoint_id": resp.data["id"]},
        format="json",
    )
    assert forked.status_code == 201, forked.content
    assert forked.data["id"] != str(conversation.id)
    assert forked.data["title"] == "Thread — fork"

    cleared = client.post(_clear_url(conversation))
    assert cleared.status_code == 200, cleared.content
    assert cleared.data["summary"] == ""
    assert cleared.data["context_snapshot_json"] == {}


@pytest.mark.django_db
def test_checkpoint_endpoint_requires_name(manager):
    conversation = _make_conversation(manager, n_messages=1)
    resp = _client(manager).post(_checkpoint_url(conversation), {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_restore_fork_missing_checkpoint_returns_404(manager):
    conversation = _make_conversation(manager, n_messages=1)
    client = _client(manager)
    missing = "00000000-0000-0000-0000-000000000000"

    assert client.post(
        _restore_url(conversation), {"checkpoint_id": missing}, format="json",
    ).status_code == 404
    assert client.post(
        _fork_url(conversation), {"checkpoint_id": missing}, format="json",
    ).status_code == 404


@pytest.mark.django_db
def test_missing_conversation_returns_404(manager):
    client = _client(manager)
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(
        _checkpoint_url(
            type("C", (), {"id": missing})(),
        ),
        {"name": "v1"},
        format="json",
    ).status_code == 404
    assert client.post(
        _clear_url(type("C", (), {"id": missing})()),
    ).status_code == 404


# ── CBAC gating ──────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_mutating_actions_require_manage_console(owner, plain_user):
    conversation = _make_conversation(owner, n_messages=1)
    ci = CarbonIntelligence()
    checkpoint = ci.checkpoint_conversation(owner, str(conversation.id), name="v1")
    client = _client(plain_user)

    assert client.post(
        _checkpoint_url(conversation), {"name": "x"}, format="json",
    ).status_code == 403
    assert client.post(
        _restore_url(conversation), {"checkpoint_id": checkpoint["id"]}, format="json",
    ).status_code == 403
    assert client.post(
        _fork_url(conversation), {"checkpoint_id": checkpoint["id"]}, format="json",
    ).status_code == 403
    assert client.post(_clear_url(conversation)).status_code == 403


@pytest.mark.django_db
def test_read_actions_require_view_console(owner, plain_user):
    conversation = _make_conversation(owner, n_messages=1)
    client = _client(plain_user)
    assert client.get(_checkpoints_url(conversation)).status_code == 403


@pytest.mark.django_db
def test_view_only_user_can_list_but_not_mutate(
    owner, view_only_user, shared_org, create_scoped_role,
):
    conversation = _make_conversation(owner, n_messages=1)
    _share_conversation(conversation, shared_org)
    create_scoped_role(view_only_user, "viewers_group", org_unit=shared_org)
    ci = CarbonIntelligence()
    ci.checkpoint_conversation(owner, str(conversation.id), name="v1")
    client = _client(view_only_user)

    listed = client.get(_checkpoints_url(conversation))
    assert listed.status_code == 200, listed.content
    assert listed.data["checkpoints"][0]["name"] == "v1"
    # View capability never grants writes.
    assert client.post(
        _checkpoint_url(conversation), {"name": "x"}, format="json",
    ).status_code == 403
    assert client.post(_clear_url(conversation)).status_code == 403


@pytest.mark.django_db
def test_private_conversation_hidden_even_with_capability(owner, manager):
    """Capability alone is not access — owner's private conversation stays 404."""
    conversation = _make_conversation(owner, n_messages=1)
    client = _client(manager)

    resp = client.post(_checkpoint_url(conversation), {"name": "x"}, format="json")
    assert resp.status_code == 404
    assert client.get(_checkpoints_url(conversation)).status_code == 404


@pytest.mark.django_db
def test_manager_can_checkpoint_shared_conversation(
    owner, manager, shared_org, create_scoped_role,
):
    """Manage-capable operator with org access can snapshot a shared thread."""
    conversation = _make_conversation(owner, n_messages=2)
    _share_conversation(conversation, shared_org)
    create_scoped_role(manager, "viewers_group", org_unit=shared_org)
    client = _client(manager)

    resp = client.post(
        _checkpoint_url(conversation), {"name": "v1"}, format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.data["conversation_id"] == str(conversation.id)
    assert resp.data["snapshot"]["message_count"] == 2
