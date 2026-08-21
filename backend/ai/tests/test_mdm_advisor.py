"""
Phase 24-K — MDM & data product (admin/ops cluster) tests.

Golden set: an active ``emission_factors`` set with a code-duplicate pair
(CO2/CO2), a unique methane record, an inactive nitrous-oxide record, and a
near-duplicate label; a draft ``unit_uoms`` set with a label-duplicate pair
(Kilogram/KGS); and a ``weather_codes`` set with a fuzzy near-duplicate pair
that only groups at the default threshold.

Covers:
  - explain_entity: master-record explanation (set context, validity status,
    gold-record confidence, near-duplicates)
  - gold_record_confidence: deterministic score components
  - dedup_suggestions: code-duplicate + label-duplicate + fuzzy groups against
    the seeded golden set, canonical gold selection, threshold sensitivity
  - propose_merge: requires_confirmation payloads, never executes
    (RULE_21 — no ReferenceValue writes)
  - capability-gated API endpoints (platform:view_audit reads;
    mdm:manage for propose-merge)

Design: read-only projections; nothing is ever written.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from ai.knowledge import mdm_advisor


# ── Golden MDM set ────────────────────────────────────────────────────────


@pytest.fixture
def golden(db):
    from mdm.models import ReferenceSet, ReferenceValue

    factors = ReferenceSet.objects.create(
        name="emission_factors", description="GHG emission factors",
        version=2, lifecycle_state=ReferenceSet.LIFECYCLE_ACTIVE,
    )
    ef1 = ReferenceValue.objects.create(
        reference_set=factors, code="CO2", label="Carbon Dioxide",
        metadata={"formula": "44.01"}, sort_order=1,
    )
    ef2 = ReferenceValue.objects.create(
        reference_set=factors, code="co2", label="Carbon Dioxide", sort_order=2,
    )
    ef3 = ReferenceValue.objects.create(
        reference_set=factors, code="CH4", label="Methane", sort_order=3,
    )
    ef4 = ReferenceValue.objects.create(
        reference_set=factors, code="N2O", label="Nitrous Oxide",
        is_active=False, sort_order=4,
    )
    ef5 = ReferenceValue.objects.create(
        reference_set=factors, code="CO2E", label="Carbon Dioxide Equivalent",
        sort_order=5,
    )

    uoms = ReferenceSet.objects.create(
        name="unit_uoms", description="Units of measure",
        lifecycle_state=ReferenceSet.LIFECYCLE_DRAFT,
    )
    u1 = ReferenceValue.objects.create(reference_set=uoms, code="KG", label="Kilogram", sort_order=1)
    u2 = ReferenceValue.objects.create(reference_set=uoms, code="KGS", label="Kilogram", sort_order=2)
    u3 = ReferenceValue.objects.create(reference_set=uoms, code="L", label="Liter", sort_order=3)

    weather = ReferenceSet.objects.create(
        name="weather_codes", description="Weather observation codes",
        lifecycle_state=ReferenceSet.LIFECYCLE_ACTIVE,
    )
    w1 = ReferenceValue.objects.create(reference_set=weather, code="TMP", label="Temperature", sort_order=1)
    w2 = ReferenceValue.objects.create(reference_set=weather, code="TEMP", label="Temperatur", sort_order=2)

    return {
        "factors": factors, "uoms": uoms, "weather": weather,
        "ef1": ef1, "ef2": ef2, "ef3": ef3, "ef4": ef4, "ef5": ef5,
        "u1": u1, "u2": u2, "u3": u3,
        "w1": w1, "w2": w2,
    }


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
def authed_client(make_user):
    def _client(username="auditor", **kwargs):
        user = make_user(username, **kwargs)
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user
    return _client


# ── explain_entity ────────────────────────────────────────────────────────


def test_explain_entity_master_record(golden):
    result = mdm_advisor.explain_entity(golden["ef1"].id)
    assert "error" not in result
    entity = result["entity"]
    assert entity["code"] == "CO2"
    assert entity["label"] == "Carbon Dioxide"
    assert entity["is_active"] is True

    mr = result["master_record"]
    assert mr["reference_set"]["name"] == "emission_factors"
    assert mr["reference_set"]["version"] == 2
    assert mr["reference_set"]["lifecycle_state"] == "active"
    assert mr["status"] == "current"
    assert mr["currently_valid"] is True

    assert result["gold_record_confidence"] == 0.55  # active+valid+meta, dup label penalty, active set
    near_ids = {d["value_id"] for d in result["near_duplicates"]}
    assert near_ids == {golden["ef2"].id, golden["ef5"].id}
    assert "Carbon Dioxide" in result["explanation"]


def test_explain_entity_inactive_status(golden):
    result = mdm_advisor.explain_entity(golden["ef4"].id)
    assert result["master_record"]["status"] == "inactive"
    assert result["master_record"]["currently_valid"] is False
    assert result["gold_record_confidence"] == 0.20  # inactive but active set


def test_explain_entity_not_found(db):
    result = mdm_advisor.explain_entity(999999)
    assert result["error"]["code"] == "not_found"


# ── gold_record_confidence ────────────────────────────────────────────────


def test_gold_record_confidence_scores(golden):
    assert mdm_advisor.gold_record_confidence(golden["ef3"].id) == 0.95  # active+valid+unique+active set
    assert mdm_advisor.gold_record_confidence(golden["ef1"].id) == 0.55  # metadata, dup penalty
    assert mdm_advisor.gold_record_confidence(golden["u3"].id) == 0.75  # draft set → no set bonus
    assert mdm_advisor.gold_record_confidence(golden["u1"].id) == 0.30  # label dup in draft set
    assert mdm_advisor.gold_record_confidence(999999) == 0.0


# ── dedup_suggestions ─────────────────────────────────────────────────────


def test_dedup_suggestions_golden(golden):
    result = mdm_advisor.dedup_suggestions()
    assert result["count"] == 3  # factors code-dup, uoms label-dup, weather fuzzy

    by_set = {s["reference_set"]["name"]: s for s in result["suggestions"]}

    factors = by_set["emission_factors"]
    assert factors["member_count"] == 2
    assert factors["canonical_value_id"] == golden["ef1"].id  # higher confidence than ef2
    assert factors["canonical_confidence"] == 0.55
    assert "same normalized code" in factors["reason"]

    uoms = by_set["unit_uoms"]
    assert uoms["canonical_value_id"] == golden["u1"].id  # tie-break: older id
    assert uoms["canonical_confidence"] == 0.30
    assert "Kilogram" in uoms["reason"]

    weather = by_set["weather_codes"]
    assert weather["member_count"] == 2
    assert "similarity" in weather["reason"]
    assert weather["action"] == "review_merge"


def test_dedup_suggestions_set_filter(golden):
    result = mdm_advisor.dedup_suggestions(set_id=golden["uoms"].id)
    assert result["count"] == 1
    assert result["suggestions"][0]["reference_set"]["name"] == "unit_uoms"


def test_dedup_suggestions_threshold_sensitivity(golden):
    strict = mdm_advisor.dedup_suggestions(set_id=golden["weather"].id, threshold=0.97)
    assert strict["count"] == 0  # fuzzy pair drops below strict threshold
    default = mdm_advisor.dedup_suggestions(set_id=golden["weather"].id)
    assert default["count"] == 1  # same-code/same-label pairs survive anyway


def test_dedup_suggestions_unknown_set(db):
    result = mdm_advisor.dedup_suggestions(set_id=999999)
    assert result["error"]["code"] == "not_found"


# ── propose_merge (RULE_21 — never executes) ──────────────────────────────


def test_propose_merge_requires_confirmation(golden):
    from mdm.models import ReferenceValue

    before = ReferenceValue.objects.count()
    result = mdm_advisor.propose_merge(
        set_id=golden["factors"].id,
        duplicate_value_id=golden["ef2"].id,
        gold_value_id=golden["ef1"].id,
    )
    assert result["requires_confirmation"] is True
    assert result["never_executes"] is True
    assert result["type"] == "mdm_merge_draft"
    proposal = result["proposal"]
    assert proposal["reference_set"]["name"] == "emission_factors"
    assert proposal["duplicate"]["code"] == "co2"
    assert proposal["gold"]["value_id"] == golden["ef1"].id
    assert proposal["gold_confidence"] == 0.55
    assert proposal["action"] == "deprecate_duplicate_keep_gold"
    assert any("Deactivate" in e for e in proposal["effects"])
    assert ReferenceValue.objects.count() == before  # nothing written


def test_propose_merge_errors(golden):
    bad_set = mdm_advisor.propose_merge(
        set_id=999999, duplicate_value_id=golden["ef2"].id, gold_value_id=golden["ef1"].id,
    )
    assert bad_set["error"]["code"] == "not_found"

    cross_set = mdm_advisor.propose_merge(
        set_id=golden["factors"].id,
        duplicate_value_id=golden["u1"].id,  # different set
        gold_value_id=golden["ef1"].id,
    )
    assert cross_set["error"]["code"] == "not_found"

    same = mdm_advisor.propose_merge(
        set_id=golden["factors"].id,
        duplicate_value_id=golden["ef1"].id,
        gold_value_id=golden["ef1"].id,
    )
    assert same["error"]["code"] == "same_record"


# ── API gates ─────────────────────────────────────────────────────────────


def test_api_mdm_reads_require_capability(golden, authed_client):
    client, _ = authed_client("plain_user")
    assert client.get(f"/carbon-api/ai/pulse/mdm/entity/{golden['ef1'].id}/").status_code == 403
    assert client.get("/carbon-api/ai/pulse/mdm/dedup/").status_code == 403


def test_api_mdm_explain_and_dedup_superuser(golden, authed_client):
    client, _ = authed_client("admin", is_superuser=True)
    resp = client.get(f"/carbon-api/ai/pulse/mdm/entity/{golden['ef1'].id}/")
    assert resp.status_code == 200
    assert resp.json()["entity"]["code"] == "CO2"

    resp = client.get("/carbon-api/ai/pulse/mdm/entity/999999/")
    assert resp.status_code == 404

    resp = client.get("/carbon-api/ai/pulse/mdm/dedup/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 3

    resp = client.get(f"/carbon-api/ai/pulse/mdm/dedup/?set_id={golden['uoms'].id}")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_api_mdm_propose_merge_requires_capability(golden, authed_client):
    client, _ = authed_client("plain_user")
    resp = client.post(
        "/carbon-api/ai/pulse/mdm/dedup/propose-merge/",
        {"set_id": golden["factors"].id, "duplicate_value_id": golden["ef2"].id, "gold_value_id": golden["ef1"].id},
        format="json",
    )
    assert resp.status_code == 403


def test_api_mdm_propose_merge_never_writes(golden, authed_client):
    from mdm.models import ReferenceValue

    client, _ = authed_client("admin", is_superuser=True)
    before = ReferenceValue.objects.count()
    resp = client.post(
        "/carbon-api/ai/pulse/mdm/dedup/propose-merge/",
        {"set_id": golden["factors"].id, "duplicate_value_id": golden["ef2"].id, "gold_value_id": golden["ef1"].id},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_confirmation"] is True
    assert body["never_executes"] is True
    assert ReferenceValue.objects.count() == before

    # unknown set → 404
    resp = client.post(
        "/carbon-api/ai/pulse/mdm/dedup/propose-merge/",
        {"set_id": 999999, "duplicate_value_id": golden["ef2"].id, "gold_value_id": golden["ef1"].id},
        format="json",
    )
    assert resp.status_code == 404
