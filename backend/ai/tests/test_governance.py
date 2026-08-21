"""
Phase 24-J — Governance & policy (admin/ops cluster) tests.

Golden set: three policies (an enforced table_delete with usage_count=5, a
never-used org-scoped module_update — stale, a disabled table_update) and
four DQ rules (three bound across validity/completeness/uniqueness, one
active but UNBOUND — drift).

Covers:
  - explain_policy: grounded in the live rule catalog (active rule counts
    by dimension, covered tables, dimension gaps)
  - list_policies: inventory + enabled/scope filters
  - draft_policy_change: requires_confirmation payloads, current-vs-proposed
    diff, never executes (RULE_21 — no GovernancePolicy writes)
  - map_rules_to_policies: rules → policies → dimensions projection
  - flag_policy_drift: unbound rules, stale policies (usage_count 0),
    dimension gaps (zero active rules)
  - capability-gated API endpoints (platform:view_audit reads;
    catalog:manage_policies for drafts)

Design: read-only projections; nothing is ever written.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from ai.knowledge import policy_advisor


# ── Golden governance set ─────────────────────────────────────────────────


@pytest.fixture
def golden(db):
    from catalog.models import GovernancePolicy
    from core.models import Module
    from dataschema.models import DataField, DataTable
    from dq.models import DQRule, RuleFieldAssignment
    from mdm.models import OrgUnit

    org = OrgUnit.objects.create(name="Engineering", slug="eng", org_type="college")
    mod = Module.objects.create(name="emissions", org_unit=org)

    A = DataTable.objects.create(title="Sources", name="sources", module=mod)
    B = DataTable.objects.create(title="Activities", name="activities", module=mod)

    a1 = DataField.objects.create(data_table=A, name="source_id", label="Source ID", type="number", order=0)
    b2 = DataField.objects.create(data_table=B, name="activity_id", label="Activity ID", type="number", order=0)

    def make_rule(name, level, dimension, rule_type, severity):
        return DQRule.objects.create(name=name, definition={
            "schema_version": 1, "name": name, "level": level,
            "dimension": dimension, "type": rule_type, "severity": severity,
            "active": True,
        })

    r1 = make_rule("r1-not-null", "field", "validity", "not_null", "error")
    r2 = DQRule.objects.create(name="r2-range", definition={
        "schema_version": 1, "name": "r2-range", "level": "business",
        "dimension": "completeness", "type": "range", "severity": "warn",
        "active": True, "params": {"min": 0},
    })
    r3 = make_rule("r3-unique", "field", "uniqueness", "unique", "error")
    r4 = DQRule.objects.create(name="r4-unbound", definition={
        "schema_version": 1, "name": "r4-unbound", "level": "field",
        "dimension": "consistency", "type": "regex", "severity": "error",
        "active": True, "params": {"pattern": "^[A-Z]{3}$"},
    })  # drift: no assignment

    RuleFieldAssignment.objects.create(rule=r1, data_table=A, data_field=a1)
    RuleFieldAssignment.objects.create(rule=r2, data_table=B)  # table-level
    RuleFieldAssignment.objects.create(rule=r3, data_table=B, data_field=b2)

    p1 = GovernancePolicy.objects.create(
        policy_type="table_delete", name="Block table delete with dependencies",
        description="Prevents dropping tables that still feed others.",
        enabled=True, scope_type="global", usage_count=5,
        config={"block_with_dependencies": True},
        error_message="This table has downstream consumers.",
        remediation_steps=["Migrate dependent tables", "Re-verify references"],
    )
    p2 = GovernancePolicy.objects.create(
        policy_type="module_update", name="Require review on module update",
        description="Module metadata updates need steward review.",
        enabled=True, scope_type="org_unit", org_unit=org, usage_count=0,
    )
    p3 = GovernancePolicy.objects.create(
        policy_type="table_update", name="Legacy update policy",
        enabled=False, scope_type="global",
    )

    return {
        "org": org, "mod": mod, "A": A, "B": B, "a1": a1, "b2": b2,
        "r1": r1, "r2": r2, "r3": r3, "r4": r4,
        "p1": p1, "p2": p2, "p3": p3,
    }


@pytest.fixture
def authed_client(make_user):
    def _client(username="auditor", **kwargs):
        user = make_user(username, **kwargs)
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user
    return _client


@pytest.fixture
def make_user(db):
    def _make(username, **kwargs):
        user = User.objects.create_user(username=username, password="secret123")
        for k, v in kwargs.items():
            setattr(user, k, v)
        user.save()
        return user
    return _make


# ── explain_policy ────────────────────────────────────────────────────────


def test_explain_policy_grounded_in_rule_catalog(golden):
    result = policy_advisor.explain_policy(golden["p1"].id)
    assert "error" not in result
    policy = result["policy"]
    assert policy["name"] == "Block table delete with dependencies"
    assert policy["policy_type"] == "table_delete"
    assert policy["enabled"] is True
    assert policy["usage_count"] == 5
    assert policy["scope_label"] == "global"
    assert policy["error_message"] == "This table has downstream consumers."
    assert policy["remediation_steps"] == ["Migrate dependent tables", "Re-verify references"]
    assert policy["config"] == {"block_with_dependencies": True}

    ctx = result["catalog_context"]
    assert ctx["active_rule_count"] == 4  # r1..r4
    assert ctx["covered_tables"] == 2  # A and B
    dims = {d["dimension"]: d["rule_count"] for d in ctx["rules_by_dimension"]}
    assert dims["validity"] == 1
    assert dims["completeness"] == 1
    assert dims["uniqueness"] == 1
    assert "timeliness" in ctx["dimension_gaps"]


def test_explain_policy_org_scope_label(golden):
    result = policy_advisor.explain_policy(golden["p2"].id)
    assert result["policy"]["scope_label"] == "org_unit:Engineering"


def test_explain_policy_not_found(db):
    result = policy_advisor.explain_policy(999999)
    assert result["error"]["code"] == "not_found"


# ── list_policies ─────────────────────────────────────────────────────────


def test_list_policies_inventory(golden):
    result = policy_advisor.list_policies()
    assert result["count"] == 3
    names = {p["name"] for p in result["policies"]}
    assert names == {
        "Block table delete with dependencies",
        "Require review on module update",
        "Legacy update policy",
    }


def test_list_policies_filters(golden):
    enabled_only = policy_advisor.list_policies(enabled=True)
    assert enabled_only["count"] == 2
    assert all(p["enabled"] for p in enabled_only["policies"])

    org_scoped = policy_advisor.list_policies(scope_type="org_unit")
    assert org_scoped["count"] == 1
    assert org_scoped["policies"][0]["scope_label"] == "org_unit:Engineering"


# ── draft_policy_change (RULE_21 — never executes) ────────────────────────


def test_draft_policy_change_requires_confirmation(golden):
    from catalog.models import GovernancePolicy

    before = GovernancePolicy.objects.count()
    result = policy_advisor.draft_policy_change(golden["p1"].id, {
        "enabled": False,
        "error_message": "Blocked: migrate dependent tables first.",
    })
    assert result["requires_confirmation"] is True
    assert result["never_executes"] is True
    assert result["type"] == "policy_draft"
    proposal = result["proposal"]
    assert proposal["policy_id"] == golden["p1"].id
    diff = {d["field"]: d for d in proposal["diff"]}
    assert diff["enabled"]["current"] is True
    assert diff["enabled"]["proposed"] is False
    assert diff["enabled"]["changed"] is True
    assert diff["error_message"]["changed"] is True
    assert golden["p1"].__class__.objects.count() == before  # nothing written


def test_draft_policy_change_no_actual_change(golden):
    result = policy_advisor.draft_policy_change(golden["p1"].id, {"enabled": True})
    assert result["requires_confirmation"] is True
    diff = result["proposal"]["diff"]
    assert diff == [{"field": "enabled", "current": True, "proposed": True, "changed": False}]
    assert "no actual changes" in result["summary"]


def test_draft_policy_change_unknown_policy(db):
    result = policy_advisor.draft_policy_change(999999, {"enabled": False})
    assert result["error"]["code"] == "not_found"


def test_draft_policy_change_field_not_draftable(golden):
    result = policy_advisor.draft_policy_change(golden["p1"].id, {"scope_type": "domain"})
    assert result["error"]["code"] == "field_not_draftable"


def test_draft_policy_change_empty(golden):
    result = policy_advisor.draft_policy_change(golden["p1"].id, {})
    assert result["error"]["code"] == "empty_draft"


# ── map_rules_to_policies ─────────────────────────────────────────────────


def test_map_rules_to_policies(golden):
    result = policy_advisor.map_rules_to_policies()
    dims = {d["dimension"]: d for d in result["dimensions"]}
    assert dims["validity"]["rule_count"] == 1
    assert dims["completeness"]["rule_count"] == 1
    assert dims["uniqueness"]["rule_count"] == 1
    assert {r["name"] for r in dims["validity"]["rules"]} == {"r1-not-null"}

    assert result["counts"]["rules"] == 4
    assert result["counts"]["policies"] == 3
    policy_names = {p["name"] for p in result["policies"]}
    assert "Block table delete with dependencies" in policy_names
    p1 = next(p for p in result["policies"] if p["name"] == "Block table delete with dependencies")
    assert p1["dimension_counts"]["validity"] == 1
    assert p1["usage_count"] == 5


# ── flag_policy_drift ─────────────────────────────────────────────────────


def test_flag_policy_drift_flags_match_golden_anomalies(golden):
    result = policy_advisor.flag_policy_drift()
    by_type = {}
    for flag in result["flags"]:
        by_type.setdefault(flag["type"], []).append(flag)

    unbound = by_type.get("unbound_rule", [])
    assert any(f["rule_id"] == golden["r4"].id for f in unbound)  # r4 never bound
    assert not any(f["rule_id"] == golden["r1"].id for f in unbound)  # bound rules clean

    stale = by_type.get("stale_policy", [])
    assert any(f["policy_id"] == golden["p2"].id for f in stale)  # enabled, usage 0
    assert not any(f["policy_id"] == golden["p1"].id for f in stale)  # enforced → not stale

    gaps = {f["dimension"] for f in by_type.get("dimension_gap", [])}
    assert "timeliness" in gaps
    assert "validity" not in gaps  # has an active rule


# ── API gates ─────────────────────────────────────────────────────────────


def test_api_policy_reads_require_capability(golden, authed_client):
    client, user = authed_client("plain_user")
    for url in ("/carbon-api/ai/pulse/policies/", "/carbon-api/ai/pulse/policies/drift/"):
        assert client.get(url).status_code == 403


def test_api_policy_list_and_explain_superuser(golden, authed_client):
    client, _ = authed_client("admin", is_superuser=True)
    resp = client.get("/carbon-api/ai/pulse/policies/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 3

    resp = client.get(f"/carbon-api/ai/pulse/policies/{golden['p1'].id}/")
    assert resp.status_code == 200
    assert resp.json()["policy"]["name"] == "Block table delete with dependencies"

    resp = client.get("/carbon-api/ai/pulse/policies/999999/")
    assert resp.status_code == 404


def test_api_policy_map_and_drift_superuser(golden, authed_client):
    client, _ = authed_client("admin", is_superuser=True)
    resp = client.get("/carbon-api/ai/pulse/policies/map/")
    assert resp.status_code == 200
    assert resp.json()["counts"]["rules"] == 4

    resp = client.get("/carbon-api/ai/pulse/policies/drift/")
    assert resp.status_code == 200
    flags = resp.json()["flags"]
    assert any(f["type"] == "unbound_rule" for f in flags)
    assert any(f["type"] == "stale_policy" for f in flags)
    assert any(f["type"] == "dimension_gap" for f in flags)


def test_api_policy_draft_requires_manage_capability(golden, authed_client):
    client, _ = authed_client("plain_user")
    resp = client.post(
        f"/carbon-api/ai/pulse/policies/{golden['p1'].id}/draft/",
        {"proposed": {"enabled": False}}, format="json",
    )
    assert resp.status_code == 403


def test_api_policy_draft_never_writes(golden, authed_client):
    from catalog.models import GovernancePolicy

    client, _ = authed_client("admin", is_superuser=True)
    before = GovernancePolicy.objects.count()
    resp = client.post(
        f"/carbon-api/ai/pulse/policies/{golden['p1'].id}/draft/",
        {"proposed": {"enabled": False, "error_message": "Blocked: migrate first."}},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_confirmation"] is True
    assert body["never_executes"] is True
    assert GovernancePolicy.objects.count() == before
    # bad payloads → 400 / 404
    assert client.post(
        f"/carbon-api/ai/pulse/policies/{golden['p1'].id}/draft/",
        {"proposed": {"scope_type": "domain"}}, format="json",
    ).status_code == 400
    assert client.post(
        "/carbon-api/ai/pulse/policies/999999/draft/",
        {"proposed": {"enabled": False}}, format="json",
    ).status_code == 404
