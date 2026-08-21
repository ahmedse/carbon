"""
Phase 24-G — Platform Administration domain (admin/ops cluster) tests.

Covers:
  - domain registration + lookup via ai.domain_protocol
  - DomainContext shape (knowledge + config)
  - manifest surface (task types → conversation registry, entry points,
    starter prompts, system prompt extension)
  - build_workspace_context entity resolution (user/group/org_unit/table/policy)
  - validate_task_payload fail-fast rules
  - manifest API endpoints (GET /carbon-api/ai/pulse/apps/ + .../apps/admin/)

Imports mirror test_domain_emissions.py: `ai.*` for the domain registry and
`backend.ai.protocol` for the protocol types.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from accounts.models import User
from ai.domain.admin import AdminDomainAI
from ai.domain_protocol import (
    get_domain,
    has_domain,
    list_domains,
    register_domain,
    supported_conversation_types,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="admin-worker", password="secret123")


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def org_unit(db):
    from mdm.models import OrgUnit

    return OrgUnit.objects.create(name="Engineering", org_type="college")


@pytest.fixture
def group(db):
    return Group.objects.create(name="dq_lead")


# ── Registration & lookup ─────────────────────────────────────────────────


def test_admin_domain_registered():
    assert has_domain("admin") is True


def test_get_domain_returns_admin_class():
    assert get_domain("admin") is AdminDomainAI


def test_get_domain_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        get_domain("nope")


def test_list_domains_includes_admin():
    assert "admin" in list_domains()


def test_duplicate_registration_raises():
    with pytest.raises(ValueError):
        register_domain("admin", AdminDomainAI)


# ── DomainContext content ─────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    assert AdminDomainAI.app_identifier == "admin"
    assert AdminDomainAI.app_display_name == "Platform Administration"


def test_domain_context_knowledge_shape():
    ctx = AdminDomainAI().get_domain_context()
    knowledge = ctx.domain_knowledge
    assert knowledge["access_model"] == "Capability-Based Access Control"
    assert set(knowledge["grant_units"]) == {"global", "org_unit", "module"}
    assert knowledge["principle"] == "least privilege"
    assert "mutation_rule" in knowledge
    assert "surfaces" in knowledge


def test_domain_context_config_shape():
    ctx = AdminDomainAI().get_domain_context()
    config = ctx.domain_config
    assert config["capability_gate_manage"] == "platform:manage_access"
    assert config["capability_gate_view"] == "platform:view_audit"
    assert config["read_only"] is True
    assert config["confirmation_required"] is True


# ── Manifest surface ──────────────────────────────────────────────────────


def test_manifest_task_types_declared():
    types = AdminDomainAI.supported_task_types
    for task_type in (
        "access_query", "lineage_trace", "impact_analysis",
        "policy_explain", "policy_draft", "mdm_explain", "mdm_dedup",
    ):
        assert task_type in types


def test_admin_task_types_flow_into_conversation_registry():
    allowed = supported_conversation_types()
    for task_type in ("access_query", "lineage_trace", "impact_analysis", "mdm_dedup"):
        assert task_type in allowed


def test_entry_points_shape():
    for ep in AdminDomainAI.entry_points:
        assert ep["label"]
        assert ep["task_type"] in AdminDomainAI.supported_task_types
        assert ep["icon"]
        assert ep["on_entity"]


def test_starter_prompts_cover_admin_surfaces():
    prompts = AdminDomainAI.starter_prompts
    for key in ("user", "group", "org_unit", "table", "policy", "entity", "default"):
        assert key in prompts
    for chip in prompts["user"]:
        assert chip["label"] and chip["prompt"] and chip["task_type"]


def test_system_prompt_extension_grounds_no_mutation():
    ext = AdminDomainAI.system_prompt_extension
    assert ext
    assert "never" in ext and "confirm" in ext


# ── Workspace context enrichment ──────────────────────────────────────────


def test_build_workspace_context_user(db, user):
    ctx = AdminDomainAI().build_workspace_context(user, "user", user.id)
    assert ctx["username"] == user.username
    assert ctx["is_active"] is True
    assert ctx["scoped_role_count"] == 0


def test_build_workspace_context_group(db, group):
    ctx = AdminDomainAI().build_workspace_context(None, "group", group.id)
    assert ctx["group_name"] == "dq_lead"
    assert ctx["member_count"] == 0


def test_build_workspace_context_org_unit(db, org_unit):
    ctx = AdminDomainAI().build_workspace_context(None, "org_unit", org_unit.id)
    assert ctx["org_unit_name"] == "Engineering"
    assert ctx["org_unit_type"] == "college"


def test_build_workspace_context_table(db, org_unit):
    from core.models import Module
    from dataschema.models import DataTable

    module = Module.objects.create(name="Campus Ops", org_unit=org_unit)
    table = DataTable.objects.create(title="Energy", name="energy", module=module)
    ctx = AdminDomainAI().build_workspace_context(None, "table", table.id)
    assert ctx["table_name"] == "energy"
    assert ctx["module_name"] == "Campus Ops"


def test_build_workspace_context_policy(db):
    from catalog.models import GovernancePolicy

    policy = GovernancePolicy.objects.create(
        policy_type="table_delete", name="No deletes", enabled=True
    )
    ctx = AdminDomainAI().build_workspace_context(None, "policy", policy.id)
    assert ctx["policy_name"] == "No deletes"
    assert ctx["policy_type"] == "table_delete"
    assert ctx["policy_enabled"] is True


def test_build_workspace_context_unknown_entity_returns_empty(user):
    ctx = AdminDomainAI().build_workspace_context(user, "user", 999999)
    assert ctx == {}
    ctx = AdminDomainAI().build_workspace_context(user, None, None)
    assert ctx == {}


# ── Payload validation ────────────────────────────────────────────────────


def test_validate_task_payload_access_query_requires_user_id():
    ok, _ = AdminDomainAI().validate_task_payload("access_query", {"user_id": 1})
    assert ok is True
    ok, reason = AdminDomainAI().validate_task_payload("access_query", {})
    assert ok is False and "user_id" in reason


def test_validate_task_payload_lineage_and_impact_require_table_id():
    for task_type in ("lineage_trace", "impact_analysis"):
        ok, _ = AdminDomainAI().validate_task_payload(task_type, {"table_id": 1})
        assert ok is True
        ok, reason = AdminDomainAI().validate_task_payload(task_type, {})
        assert ok is False and "table_id" in reason


def test_validate_task_payload_policy_requires_policy_ref():
    ok, _ = AdminDomainAI().validate_task_payload("policy_explain", {"policy_id": 1})
    assert ok is True
    ok, _ = AdminDomainAI().validate_task_payload("policy_draft", {"policy_type": "table_delete"})
    assert ok is True
    ok, reason = AdminDomainAI().validate_task_payload("policy_explain", {})
    assert ok is False and "policy_id" in reason


def test_validate_task_payload_mdm_requires_entity_ref():
    ok, _ = AdminDomainAI().validate_task_payload("mdm_explain", {"entity_type": "entity", "entity_id": 1})
    assert ok is True
    ok, _ = AdminDomainAI().validate_task_payload("mdm_dedup", {"reference_set_id": 1, "code": "X"})
    assert ok is True
    ok, reason = AdminDomainAI().validate_task_payload("mdm_explain", {})
    assert ok is False and "entity_type" in reason


def test_validate_task_payload_chat_always_passes():
    ok, reason = AdminDomainAI().validate_task_payload("chat", {})
    assert ok is True and reason == ""


# ── Manifest API endpoints ────────────────────────────────────────────────


def test_manifest_list_includes_admin(authed_client):
    resp = authed_client.get("/carbon-api/ai/pulse/apps/")
    assert resp.status_code == 200
    ids = [m["app_identifier"] for m in resp.data["apps"]]
    assert "admin" in ids


def test_manifest_detail_returns_admin(authed_client):
    resp = authed_client.get("/carbon-api/ai/pulse/apps/admin/")
    assert resp.status_code == 200
    assert resp.data["app_identifier"] == "admin"
    assert resp.data["display_name"] == "Platform Administration"
    assert "access_query" in resp.data["supported_task_types"]
