"""
Phase 15 — AI User Profile Injection.

Proves ``_user_profile_message`` derives a compact ``[User Profile]`` system
message server-side from ``user`` + ``scope`` (RULE_20), never leaks the
numeric ``user_identifier`` (RULE_23), respects the ~300-char budget, and that
``assemble_context`` injects it first (before ``[Workspace Context]``) while
skipping anonymous scopes entirely.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group

from accounts.models import ScopedRole, User
from ai.context_assembler import _user_profile_message, assemble_context
from ai.models import AIConversation
from backend.ai.protocol import Scope
from core.models import Module
from mdm.models import OrgUnit


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="profile-worker",
        password="secret123",
        first_name="Amina",
        last_name="Hassan",
    )


def _make_conversation(user, conversation_type="chat", task_payload=None):
    return AIConversation.objects.create(
        user=user,
        title=conversation_type,
        conversation_type=conversation_type,
        task_payload_json=task_payload or {},
        scope_json={},
    )


# ── (a) name + roles + org-unit + read-only flag ────────────────────────


@pytest.mark.django_db
def test_profile_includes_name_roles_org_and_read_only_flag(user):
    group = Group.objects.create(name="profile_viewer_group")
    ScopedRole.objects.create(user=user, group=group, is_active=True)
    org = OrgUnit.objects.create(name="Profile Facilities", code="FAC", org_type="division")
    module = Module.objects.create(name="Profile Emissions Module", org_unit=org)

    scope = Scope(
        user_identifier=str(user.pk),
        org_unit_ids=[str(org.id)],
        module_ids=[str(module.id)],
        is_read_only=True,
    )

    msg = _user_profile_message(scope, user)
    assert msg is not None
    assert msg["role"] == "system"
    content = msg["content"]
    assert "[User Profile]" in content
    assert "Amina Hassan" in content              # first + last name
    assert "profile_viewer_group" in content      # role name
    assert "Profile Facilities" in content        # org-unit name
    assert "Profile Emissions Module" in content  # module name
    assert "read-only" in content
    assert str(user.pk) not in content            # RULE_23: no numeric id


# ── (b) superuser marker ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_superuser_includes_marker(user):
    scope = Scope(
        user_identifier=str(user.pk),
        org_unit_ids=["*"],
        is_superuser=True,
        is_read_only=False,
    )
    msg = _user_profile_message(scope, user)
    assert msg is not None
    assert "superuser" in msg["content"]
    assert "can write" in msg["content"]


# ── (c) anonymous/empty scope → no profile ──────────────────────────────


@pytest.mark.django_db
def test_anonymous_scope_emits_no_profile(user):
    # Empty scope (no user_identifier) → None.
    assert _user_profile_message(Scope(), user) is None
    assert _user_profile_message(None, user) is None

    # assemble_context does not inject a [User Profile] message either.
    conversation = _make_conversation(user)
    result = assemble_context(conversation, [], scope=None)
    assert all("[User Profile]" not in m["content"] for m in result["messages"])


# ── (d) token budget ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_respects_token_budget(user):
    # A pathological profile (long name, many roles, long org name) must truncate.
    org = OrgUnit.objects.create(name="O" * 100, code="LONG", org_type="division")
    for i in range(20):
        group = Group.objects.create(name=f"very_long_role_name_{i:03d}")
        ScopedRole.objects.create(user=user, group=group, is_active=True)

    scope = Scope(
        user_identifier=str(user.pk),
        org_unit_ids=[str(org.id)],
        is_read_only=False,
    )
    msg = _user_profile_message(scope, user)
    assert msg is not None
    assert len(msg["content"]) <= 300
    assert "[User Profile]" in msg["content"]


# ── wiring: [User Profile] precedes [Workspace Context] ──────────────────


@pytest.mark.django_db
def test_assemble_context_orders_profile_before_workspace(user):
    org = OrgUnit.objects.create(name="Profile Ops", code="OPS", org_type="division")
    conversation = _make_conversation(
        user,
        task_payload={
            "workspace_context": {"workspace": "dq", "current_view": "rule_list"},
        },
    )
    scope = Scope(
        user_identifier=str(user.pk),
        org_unit_ids=[str(org.id)],
        is_read_only=False,
    )

    result = assemble_context(conversation, [], scope=scope)
    contents = [m["content"] for m in result["messages"]]

    profile_idx = next(i for i, c in enumerate(contents) if "[User Profile]" in c)
    workspace_idx = next(i for i, c in enumerate(contents) if "[Workspace Context]" in c)
    assert profile_idx < workspace_idx
