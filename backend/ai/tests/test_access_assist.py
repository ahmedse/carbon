"""
Phase 24-H — Access & CBAC assistance (admin/ops cluster) tests.

Covers:
  - effective_capabilities: global / org-subtree / expansion / superuser
  - users_with_capability: reverse lookup + org scoping + unknown keys
  - propose_grant: least-privilege group selection, already-has, unknown
    keys/users, and the NEVER-EXECUTES guarantee (no ScopedRole writes)
  - flag_access_anomalies: over-granted (global wildcard) + dormant grants
  - capability-gated API endpoints (platform:view_audit / platform:manage_access)

Design: results are read-only; the golden "grant this user X" intents yield
a correct capability + confirmation payload and never mutate the store.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from accounts.models import ScopedRole, User
from ai.knowledge import access_assist


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def make_user(db):
    def _make(username, **kwargs):
        user = User.objects.create_user(username=username, password="secret123")
        for k, v in kwargs.items():
            setattr(user, k, v)
        user.save()
        return user
    return _make


@pytest.fixture
def make_role(db):
    def _make(user, group_name, org=None, module=None, active=True):
        group, _ = Group.objects.get_or_create(name=group_name)
        return ScopedRole.objects.create(
            user=user, group=group, org_unit=org, module=module, is_active=active
        )
    return _make


@pytest.fixture
def make_org(db):
    def _make(name, parent=None, slug=None):
        from mdm.models import OrgUnit

        return OrgUnit.objects.create(
            name=name,
            slug=slug or name.lower().replace(" ", "-"),
            org_type="college",
            parent=parent,
        )
    return _make


@pytest.fixture
def authed_client(make_user):
    def _client(username="auditor", **kwargs):
        user = make_user(username, **kwargs)
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user
    return _client


# ── effective_capabilities ───────────────────────────────────────────────


def test_effective_capabilities_global_role(make_user, make_role):
    user = make_user("dq-owner")
    make_role(user, "dq_lead")
    result = access_assist.effective_capabilities(user.id)
    assert "dq:manage_rules" in result["capabilities"]
    assert result["role_count"] == 1
    assert result["org_unit_ids"] is None


def test_effective_capabilities_org_subtree_includes_scoped(
    make_user, make_role, make_org
):
    org = make_org("Engineering")
    user = make_user("eng-dq")
    make_role(user, "dq_lead", org=org)
    result = access_assist.effective_capabilities(user.id, org_unit_ids=[org.id])
    assert "dq:manage_rules" in result["capabilities"]
    assert result["org_unit_ids"] == [org.id]
    assert result["role_count"] == 1


def test_effective_capabilities_excludes_outside_subtree(
    make_user, make_role, make_org
):
    org = make_org("Engineering")
    other = make_org("Marketing")
    user = make_user("eng-dq")
    make_role(user, "dq_lead", org=org)
    result = access_assist.effective_capabilities(user.id, org_unit_ids=[other.id])
    assert "dq:manage_rules" not in result["capabilities"]
    assert result["role_count"] == 0


def test_effective_capabilities_expands_descendants(make_user, make_role, make_org):
    root = make_org("University")
    child = make_org("Engineering", parent=root)
    user = make_user("eng-dq")
    make_role(user, "dq_lead", org=child)
    # Query scoped to the parent expands to the child subtree.
    result = access_assist.effective_capabilities(user.id, org_unit_ids=[root.id])
    assert "dq:manage_rules" in result["capabilities"]
    assert set(result["org_unit_ids"]) == {root.id, child.id}


def test_effective_capabilities_superuser(make_user):
    user = make_user("root", is_superuser=True)
    result = access_assist.effective_capabilities(user.id)
    assert result["capabilities"] == ["*"]


def test_effective_capabilities_unknown_user(db):
    result = access_assist.effective_capabilities(999999)
    assert result["error"]["code"] == "not_found"


# ── users_with_capability ────────────────────────────────────────────────


def test_users_with_capability_reverse_lookup(make_user, make_role):
    user = make_user("dq-owner")
    make_role(user, "dq_lead")
    result = access_assist.users_with_capability("dq:manage_rules")
    assert result["known"] is True
    assert any(u["username"] == "dq-owner" for u in result["users"])
    hit = next(u for u in result["users"] if u["username"] == "dq-owner")
    assert {"group": "dq_lead", "scope": "global"} in hit["granted_via"]


def test_users_with_capability_unknown_key(db):
    result = access_assist.users_with_capability("no:such_capability")
    assert result["known"] is False
    assert result["users"] == []


def test_users_with_capability_scoped(make_user, make_role, make_org):
    org = make_org("Engineering")
    other = make_org("Marketing")
    user = make_user("eng-dq")
    make_role(user, "dq_lead", org=org)
    in_scope = access_assist.users_with_capability(
        "dq:manage_rules", org_unit_ids=[org.id]
    )
    out_of_scope = access_assist.users_with_capability(
        "dq:manage_rules", org_unit_ids=[other.id]
    )
    assert any(u["username"] == "eng-dq" for u in in_scope["users"])
    assert not any(u["username"] == "eng-dq" for u in out_of_scope["users"])


# ── propose_grant (golden intents — never executes) ──────────────────────


def test_propose_grant_least_privilege_group(make_user, db):
    """'grant this user carbon:enter_data' → smallest non-wildcard role."""
    from accounts.capabilities import GROUP_CAPABILITIES

    user = make_user("data-owner-candidate")
    before = ScopedRole.objects.count()
    result = access_assist.propose_grant(user.id, "carbon:enter_data")
    assert result["requires_confirmation"] is True
    assert result["never_executes"] is True
    prop = result["proposal"]
    # carbon_lead is the smallest non-wildcard group granting carbon:enter_data;
    # counts come from the live GROUP_CAPABILITIES registry so the invariant
    # (not a hardcoded count) is what we lock in.
    lead_count = len(GROUP_CAPABILITIES["carbon_lead"])
    owners_count = len(GROUP_CAPABILITIES["dataowners_group"])
    assert prop["group"] == "carbon_lead"
    assert prop["group_capability_count"] == lead_count
    assert lead_count < owners_count  # least-privilege invariant
    assert prop["capability"] == "carbon:enter_data"
    assert prop["scope"] == {"scope": "global"}
    assert ScopedRole.objects.count() == before  # nothing was written


def test_propose_grant_respects_org_scope(make_user, make_org):
    org = make_org("Engineering")
    user = make_user("data-owner-candidate")
    result = access_assist.propose_grant(
        user.id, "carbon:enter_data", org_unit_ids=[org.id]
    )
    assert result["proposal"]["scope"] == {"org_unit_ids": [org.id]}


def test_propose_grant_already_has(make_user, make_role):
    user = make_user("dq-owner")
    make_role(user, "dq_lead")
    result = access_assist.propose_grant(user.id, "dq:manage_rules")
    assert result["requires_confirmation"] is False
    assert result["proposal"] is None
    assert "already has" in result["summary"]


def test_propose_grant_unknown_capability(make_user):
    user = make_user("anyone")
    result = access_assist.propose_grant(user.id, "no:such_capability")
    assert result["error"]["code"] == "unknown_capability"


def test_propose_grant_unknown_user(db):
    result = access_assist.propose_grant(999999, "dq:manage_rules")
    assert result["error"]["code"] == "not_found"


def test_propose_grant_wildcard_only_capability(make_user):
    """platform:admin is only granted by wildcard roles → falls back cleanly."""
    user = make_user("platform-candidate")
    result = access_assist.propose_grant(user.id, "platform:admin")
    assert result["requires_confirmation"] is True
    assert result["proposal"]["group"] in ("admin", "admins_group")
    assert result["proposal"]["group_capability_count"] is None


# ── flag_access_anomalies ────────────────────────────────────────────────


def test_flag_access_anomalies_over_grant(make_user, make_role):
    user = make_user("suspicious-admin")
    make_role(user, "admin")  # global wildcard
    result = access_assist.flag_access_anomalies()
    hits = [f for f in result["flags"] if f["username"] == "suspicious-admin"]
    assert any(f["type"] == "over_grant" for f in hits)


def test_flag_access_anomalies_dormant_grant(make_user, make_role, make_org):
    org = make_org("Engineering")
    user = make_user("inactive-dq", is_active=False)
    make_role(user, "dq_lead", org=org)
    result = access_assist.flag_access_anomalies()
    hits = [f for f in result["flags"] if f["username"] == "inactive-dq"]
    assert any(f["type"] == "dormant_grant" for f in hits)


def test_flag_access_anomalies_respects_scope(make_user, make_role, make_org):
    org = make_org("Engineering")
    other = make_org("Marketing")
    user = make_user("scoped-admin")
    make_role(user, "admin", org=org)  # scoped wildcard — NOT an over_grant
    scoped = access_assist.flag_access_anomalies(org_unit_ids=[other.id])
    assert not any(f["username"] == "scoped-admin" for f in scoped["flags"])


# ── API surface (capability-gated, read-only) ────────────────────────────


def test_api_effective_capabilities_gated(authed_client, make_user, make_role):
    target = make_user("target")
    make_role(target, "dq_lead")
    # Plain user without platform:view_audit → 403
    client, _ = authed_client("plain-user")
    resp = client.get(f"/carbon-api/ai/pulse/access-assist/users/{target.id}/capabilities/")
    assert resp.status_code == 403
    # Superuser auditor → 200
    client, _ = authed_client("root-auditor", is_superuser=True)
    resp = client.get(f"/carbon-api/ai/pulse/access-assist/users/{target.id}/capabilities/")
    assert resp.status_code == 200
    assert "dq:manage_rules" in resp.json()["capabilities"]


def test_api_propose_grant_never_writes(authed_client, make_user):
    client, _ = authed_client("root-approver", is_superuser=True)
    target = make_user("candidate")
    before = ScopedRole.objects.count()
    resp = client.post(
        "/carbon-api/ai/pulse/access-assist/propose-grant/",
        {"user_id": target.id, "capability_key": "carbon:enter_data"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_confirmation"] is True
    assert body["proposal"]["group"] == "carbon_lead"
    assert ScopedRole.objects.count() == before


def test_api_propose_grant_requires_capability(authed_client):
    client, _ = authed_client("plain-user")
    resp = client.post(
        "/carbon-api/ai/pulse/access-assist/propose-grant/",
        {"user_id": 1, "capability_key": "dq:manage_rules"},
        format="json",
    )
    assert resp.status_code == 403


def test_api_users_with_capability(authed_client, make_user, make_role):
    make_role(make_user("dq-owner"), "dq_lead")
    client, _ = authed_client("root-auditor", is_superuser=True)
    resp = client.get(
        "/carbon-api/ai/pulse/access-assist/capability/dq:manage_rules/users/"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["known"] is True
    assert any(u["username"] == "dq-owner" for u in body["users"])


def test_api_anomalies(authed_client, make_user, make_role):
    make_role(make_user("suspicious-admin"), "admin")
    client, _ = authed_client("root-auditor", is_superuser=True)
    resp = client.get("/carbon-api/ai/pulse/access-assist/anomalies/")
    assert resp.status_code == 200
    body = resp.json()
    assert any(f["type"] == "over_grant" for f in body["flags"])
