"""Phase F — CBAC capability-gating + visibility scoping for the AI read surface.

Covers:
  * plain authenticated user (no capability, no global admin role) → 403
  * superuser → 200 (bypass)
  * global admin (admins_group @ org_unit=None) → 200 (bypass)
  * ``scope_ai_queryset`` unit behaviour: private rows hidden from other users,
    shared + own-private rows visible, global admin sees everything.
"""

import pytest

from accounts.ai_scoping import scope_ai_queryset
from ai.models.knowledge_graph import KnowledgeNode

BASE = "/carbon-api/ai/pulse"

# Representative sample of the gated read surface (all 10 paths are gated the
# same way; we assert a broad sample to prove the class is applied).
PROTECTED_PATHS = [
    f"{BASE}/health/",
    f"{BASE}/modules/",
    f"{BASE}/tasks/nope/",
    f"{BASE}/inventory/",
    f"{BASE}/data/knowledge/",
    f"{BASE}/archetypes/",
    f"{BASE}/graph/",
    f"{BASE}/usage/",
    f"{BASE}/settings/",
    f"{BASE}/sweeps/",
]


@pytest.fixture
def plain_client(api_client, create_user, get_token_for_user):
    """Authenticated client for a plain user with no capability or admin role."""
    user = create_user("ai-cbac-plain")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


@pytest.fixture
def super_client(api_client, create_user, get_token_for_user):
    user = create_user("ai-cbac-super", is_superuser=True)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


@pytest.fixture
def global_admin_client(api_client, create_user, create_scoped_role, get_token_for_user):
    user = create_user("ai-cbac-globaladmin")
    create_scoped_role(user, "admins_group", org_unit=None, module=None)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


@pytest.mark.django_db
def test_plain_user_is_forbidden(plain_client):
    for path in PROTECTED_PATHS:
        resp = plain_client.get(path)
        assert resp.status_code == 403, f"expected 403 for {path}, got {resp.status_code}"


@pytest.mark.django_db
def test_superuser_is_allowed(super_client):
    for path in [f"{BASE}/health/", f"{BASE}/inventory/", f"{BASE}/graph/"]:
        assert super_client.get(path).status_code == 200, path


@pytest.mark.django_db
def test_global_admin_is_allowed(global_admin_client):
    for path in [f"{BASE}/health/", f"{BASE}/inventory/", f"{BASE}/graph/"]:
        assert global_admin_client.get(path).status_code == 200, path


@pytest.mark.django_db
def test_scope_queryset_hides_other_users_private_rows(create_user):
    owner = create_user("ai-cbac-owner")
    other = create_user("ai-cbac-other")

    KnowledgeNode.objects.create(
        instance_id="scope-inst", node_type="ENTITY", name="shared-node", visibility="shared"
    )
    KnowledgeNode.objects.create(
        instance_id="scope-inst",
        node_type="ENTITY",
        name="private-owner",
        visibility="private",
        host_user_id=str(owner.id),
    )
    KnowledgeNode.objects.create(
        instance_id="scope-inst",
        node_type="ENTITY",
        name="private-other",
        visibility="private",
        host_user_id=str(other.id),
    )

    visible_names = set(
        scope_ai_queryset(KnowledgeNode.objects, owner).values_list("name", flat=True)
    )
    assert "shared-node" in visible_names
    assert "private-owner" in visible_names
    assert "private-other" not in visible_names


@pytest.mark.django_db
def test_scope_queryset_global_admin_sees_all(create_user, create_scoped_role):
    owner = create_user("ai-cbac-owner2")
    admin = create_user("ai-cbac-admin2")
    create_scoped_role(admin, "admins_group", org_unit=None, module=None)

    KnowledgeNode.objects.create(
        instance_id="scope-inst-2", node_type="ENTITY", name="shared-node-2", visibility="shared"
    )
    KnowledgeNode.objects.create(
        instance_id="scope-inst-2",
        node_type="ENTITY",
        name="private-owner-2",
        visibility="private",
        host_user_id=str(owner.id),
    )

    visible_names = set(
        scope_ai_queryset(KnowledgeNode.objects, admin).values_list("name", flat=True)
    )
    assert "shared-node-2" in visible_names
    assert "private-owner-2" in visible_names


@pytest.mark.django_db
def test_scope_queryset_plain_user_sees_only_null_org(create_user):
    """A user with no admin org role only sees null-org rows (shared rows)."""
    user = create_user("ai-cbac-plain2")

    KnowledgeNode.objects.create(
        instance_id="scope-inst-3",
        node_type="ENTITY",
        name="null-org-node",
        org_unit_id=None,
        visibility="shared",
    )
    KnowledgeNode.objects.create(
        instance_id="scope-inst-3",
        node_type="ENTITY",
        name="org-node",
        org_unit_id=9999,
        visibility="shared",
    )

    visible_names = set(
        scope_ai_queryset(KnowledgeNode.objects, user).values_list("name", flat=True)
    )
    assert "null-org-node" in visible_names
    assert "org-node" not in visible_names
