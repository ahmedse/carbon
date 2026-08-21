"""
Phase 24-I — Lineage & impact (admin/ops cluster) tests.

Golden set: a chain ``Sources(A) → Activities(B) → Factors(C)`` plus a
``Holding(D)`` table with an inbound reference field to B, and three DQ
rules (field-level on A, table-level on B, field-level on B).

Covers:
  - table_lineage: transitive upstream/downstream with depth + path,
    direct Phase-B envelope, cycle termination
  - field_lineage: feeds / fed-by / implicit reference_table edges
  - impact_analysis_table: downstream consumers, inbound references, bound
    rules (field + table level), lock state
  - impact_analysis_field: rules, table-level rules, relation edges
  - not-found handling + dispatcher
  - capability-gated API endpoints (platform:view_audit)

Design: read-only projections; nothing is ever written.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from ai.knowledge import lineage


# ── Golden lineage set ─────────────────────────────────────────────────────


@pytest.fixture
def golden(db):
    from core.models import Module
    from dataschema.models import DataField, DataTable, TableRelation
    from dq.models import DQRule, RuleFieldAssignment
    from mdm.models import OrgUnit

    org = OrgUnit.objects.create(name="Engineering", slug="eng", org_type="college")
    mod = Module.objects.create(name="emissions", org_unit=org)

    A = DataTable.objects.create(title="Sources", name="sources", module=mod)
    B = DataTable.objects.create(title="Activities", name="activities", module=mod)
    C = DataTable.objects.create(title="Factors", name="factors", module=mod)
    D = DataTable.objects.create(title="Holding", name="holding", module=mod)

    a1 = DataField.objects.create(data_table=A, name="source_id", label="Source ID", type="number", order=0)
    b2 = DataField.objects.create(data_table=B, name="activity_id", label="Activity ID", type="number", order=0)
    c3 = DataField.objects.create(data_table=C, name="factor_code", label="Factor Code", type="string", order=0)
    d4 = DataField.objects.create(
        data_table=D, name="activity_ref", label="Activity Ref", type="reference",
        order=0, reference_table=B,
    )

    rel_ab = TableRelation.objects.create(
        from_table=A, from_field=a1, to_table=B, to_field=b2,
        relation_type="one_to_many", label="source->activity",
    )
    rel_bc = TableRelation.objects.create(
        from_table=B, from_field=b2, to_table=C, to_field=c3,
        relation_type="lookup", label="activity->factor",
    )

    r1 = DQRule.objects.create(name="r1-not-null", definition={
        "schema_version": 1, "name": "r1-not-null", "level": "field",
        "dimension": "validity", "type": "not_null", "severity": "error",
        "active": True,
    })
    r2 = DQRule.objects.create(name="r2-range", definition={
        "schema_version": 1, "name": "r2-range", "level": "business",
        "dimension": "completeness", "type": "range", "severity": "warn",
        "active": True, "params": {"min": 0},
    })
    r3 = DQRule.objects.create(name="r3-unique", definition={
        "schema_version": 1, "name": "r3-unique", "level": "field",
        "dimension": "uniqueness", "type": "unique", "severity": "error",
        "active": True,
    })

    RuleFieldAssignment.objects.create(rule=r1, data_table=A, data_field=a1)
    RuleFieldAssignment.objects.create(rule=r2, data_table=B)  # table-level
    RuleFieldAssignment.objects.create(rule=r3, data_table=B, data_field=b2)

    return {
        "A": A, "B": B, "C": C, "D": D,
        "a1": a1, "b2": b2, "c3": c3, "d4": d4,
        "rel_ab": rel_ab, "rel_bc": rel_bc,
        "r1": r1, "r2": r2, "r3": r3,
    }


@pytest.fixture
def authed_client(db):
    def _client(username="auditor", is_superuser=False):
        user = User.objects.create_user(username=username, password="secret123")
        user.is_superuser = is_superuser
        user.save()
        client = APIClient()
        client.force_authenticate(user=user)
        return client
    return _client


# ── table_lineage ──────────────────────────────────────────────────────────


def test_table_lineage_middle_table(golden):
    result = lineage.table_lineage(golden["B"].id)
    assert "error" not in result
    assert result["table"]["table_id"] == golden["B"].id
    # upstream: A at depth 1; downstream: C at depth 1
    assert [e["table_id"] for e in result["upstream"]] == [golden["A"].id]
    assert result["upstream"][0]["depth"] == 1
    assert [e["table_id"] for e in result["downstream"]] == [golden["C"].id]
    assert result["downstream"][0]["depth"] == 1
    # direct Phase-B envelope
    assert result["direct"]["upstream"][0]["from_table_id"] == golden["A"].id
    assert result["direct"]["downstream"][0]["to_table_id"] == golden["C"].id


def test_table_lineage_transitive_chain(golden):
    # A → downstream contains B (depth 1) and C (depth 2)
    result = lineage.table_lineage(golden["A"].id)
    depths = {e["table_id"]: e["depth"] for e in result["downstream"]}
    assert depths[golden["B"].id] == 1
    assert depths[golden["C"].id] == 2
    # C → upstream contains B (depth 1) and A (depth 2)
    result = lineage.table_lineage(golden["C"].id)
    depths = {e["table_id"]: e["depth"] for e in result["upstream"]}
    assert depths[golden["B"].id] == 1
    assert depths[golden["A"].id] == 2
    # path carries the relation chain
    c_up = next(e for e in result["upstream"] if e["table_id"] == golden["A"].id)
    assert len(c_up["path"]) == 2


def test_table_lineage_cycle_terminates(golden):
    from dataschema.models import TableRelation

    TableRelation.objects.create(
        from_table=golden["B"], to_table=golden["A"], relation_type="lookup",
    )
    result = lineage.table_lineage(golden["A"].id)
    downstream_ids = [e["table_id"] for e in result["downstream"]]
    assert golden["B"].id in downstream_ids
    assert downstream_ids.count(golden["B"].id) == 1  # no revisit
    assert golden["A"].id not in downstream_ids  # self never re-enters


def test_table_lineage_unknown(golden):
    result = lineage.table_lineage(999999)
    assert result["error"]["code"] == "not_found"


# ── field_lineage ──────────────────────────────────────────────────────────


def test_field_lineage_feeds_and_fed_by(golden):
    # b2 is fed by A→B and feeds B→C
    result = lineage.field_lineage(golden["b2"].id)
    assert "error" not in result
    assert result["field"]["field_id"] == golden["b2"].id
    assert [r["relation_id"] for r in result["fed_by"]] == [golden["rel_ab"].id]
    assert [r["relation_id"] for r in result["feeds"]] == [golden["rel_bc"].id]
    assert result["references"] is None


def test_field_lineage_implicit_reference(golden):
    result = lineage.field_lineage(golden["d4"].id)
    assert result["references"] is not None
    assert result["references"]["kind"] == "reference_table"
    assert result["references"]["table"]["table_id"] == golden["B"].id


def test_field_lineage_unknown(golden):
    result = lineage.field_lineage(999999)
    assert result["error"]["code"] == "not_found"


# ── impact_analysis_table ──────────────────────────────────────────────────


def test_impact_table_lists_consumers_rules_and_refs(golden):
    result = lineage.impact_analysis_table(golden["B"].id)
    assert "error" not in result
    assert result["kind"] == "table"
    assert result["blocked"] is False
    # downstream consumers: C
    assert [e["table_id"] for e in result["downstream_tables"]] == [golden["C"].id]
    # inbound reference: D.activity_ref → B
    refs = result["incoming_references"]
    assert [f["field_id"] for f in refs] == [golden["d4"].id]
    # rules: table-level r2 + field-level r3 on B
    table_rule_ids = [r["rule_id"] for r in result["rules"]["table_rules"]]
    field_rule_ids = [r["rule_id"] for r in result["rules"]["field_rules"]]
    assert golden["r2"].id in table_rule_ids
    assert golden["r3"].id in field_rule_ids
    assert result["rule_count"] == 2


def test_impact_table_transitive_consumers(golden):
    result = lineage.impact_analysis_table(golden["A"].id)
    depths = {e["table_id"]: e["depth"] for e in result["downstream_tables"]}
    assert depths[golden["B"].id] == 1
    assert depths[golden["C"].id] == 2
    # only r1 (field-level on A)
    field_rule_ids = [r["rule_id"] for r in result["rules"]["field_rules"]]
    assert golden["r1"].id in field_rule_ids
    assert result["rule_count"] == 1


def test_impact_table_unknown(golden):
    result = lineage.impact_analysis_table(999999)
    assert result["error"]["code"] == "not_found"


# ── impact_analysis_field ──────────────────────────────────────────────────


def test_impact_field_rules_and_relations(golden):
    result = lineage.impact_analysis_field(golden["b2"].id)
    assert "error" not in result
    assert result["kind"] == "field"
    rule_ids = [r["rule_id"] for r in result["rules"]]
    assert golden["r3"].id in rule_ids  # field-level rule on b2
    table_rule_ids = [r["rule_id"] for r in result["table_rules"]]
    assert golden["r2"].id in table_rule_ids  # table-level rule on B
    assert result["rule_count"] == 2
    # relations: feeds B→C, fed by A→B
    assert [r["relation_id"] for r in result["outgoing_relations"]] == [golden["rel_bc"].id]
    assert [r["relation_id"] for r in result["incoming_relations"]] == [golden["rel_ab"].id]


def test_impact_field_unknown(golden):
    result = lineage.impact_analysis_field(999999)
    assert result["error"]["code"] == "not_found"


def test_impact_dispatcher(golden):
    table = lineage.impact_analysis(golden["B"].id, "table")
    field = lineage.impact_analysis(golden["b2"].id, "field")
    assert table["kind"] == "table"
    assert field["kind"] == "field"
    assert lineage.impact_analysis(golden["B"].id, "bogus")["kind"] == "table"


# ── API surface (capability-gated, read-only) ──────────────────────────────


def test_api_lineage_gated(authed_client, golden):
    plain = authed_client("plain-user")
    resp = plain.get(f"/carbon-api/ai/pulse/lineage/table/{golden['B'].id}/")
    assert resp.status_code == 403

    admin = authed_client("root-auditor", is_superuser=True)
    resp = admin.get(f"/carbon-api/ai/pulse/lineage/table/{golden['B'].id}/")
    assert resp.status_code == 200
    assert [e["table_id"] for e in resp.json()["downstream"]] == [golden["C"].id]

    resp = admin.get(f"/carbon-api/ai/pulse/lineage/field/{golden['b2'].id}/")
    assert resp.status_code == 200
    assert resp.json()["field"]["field_id"] == golden["b2"].id


def test_api_impact_gated(authed_client, golden):
    admin = authed_client("root-auditor", is_superuser=True)
    resp = admin.get(f"/carbon-api/ai/pulse/impact/table/{golden['B'].id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert [e["table_id"] for e in body["downstream_tables"]] == [golden["C"].id]
    assert body["rule_count"] == 2

    resp = admin.get(f"/carbon-api/ai/pulse/impact/field/{golden['a1'].id}/")
    assert resp.status_code == 200
    assert [r["rule_id"] for r in resp.json()["rules"]] == [golden["r1"].id]


def test_api_lineage_404(authed_client):
    admin = authed_client("root-auditor", is_superuser=True)
    assert admin.get("/carbon-api/ai/pulse/lineage/table/999999/").status_code == 404
    assert admin.get("/carbon-api/ai/pulse/impact/field/999999/").status_code == 404
