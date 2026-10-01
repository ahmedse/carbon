# Governed ComplianceRule lifecycle. Published rows are immutable.
# The drafter cannot publish. Version 2026.1 formula bytes stay put.

from datetime import date
from types import SimpleNamespace
from decimal import Decimal

import pytest
from catalog.models import GovernanceEvent

from people.models import ComplianceRule
from people.tests.ref_helpers import ensure_ref

PEOPLE_API = "/carbon-api/people/"
RULES_URL = PEOPLE_API + "compliance-rules/"
DESK_URL = "/carbon-api/catalog/policy-versions/"


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
        return api_client
    return _factory


def _formula():
    return {
        "inputs": ["a", "b"],
        "formula": {"type": "multiply", "params": {"a": "a", "b": "b"}},
    }


def _payload(**overrides):
    ensure_ref("compliance_category", "other")
    ensure_ref("jurisdiction", "KW")
    body = {
        "rule_id": "policy-sample",
        "version": "2026.2",
        "name": "Sample policy",
        "category": "other",
        "jurisdiction": "KW",
        "effective_date": "2026-06-01",
        "source_citation": "sheet example",
        "inputs_schema": _formula(),
        "test_cases": [{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}],
    }
    body.update(overrides)
    return body


def _lead(auth, create_user, create_scoped_role, name):
    user = create_user(name)
    create_scoped_role(user, "people_lead")
    return auth(user), user


def _desk(auth, create_user, create_scoped_role, name):
    """Data Trust publisher: catalog:manage_policies via catalog_lead."""
    user = create_user(name)
    create_scoped_role(user, "catalog_lead")
    return auth(user), user


def _both(auth, create_user, create_scoped_role, name):
    """Preparer who can also open the desk, so same-actor is the refusal."""
    user = create_user(name)
    create_scoped_role(user, "people_lead")
    create_scoped_role(user, "catalog_lead")
    return auth(user), user


@pytest.mark.django_db
def test_people_lead_creates_a_draft(auth, create_user, create_scoped_role):
    client, _user = _lead(auth, create_user, create_scoped_role, "policy_drafter")
    resp = client.post(RULES_URL, _payload(), format="json")
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["lifecycle"] == "draft"
    assert body["is_authoritative"] is False


@pytest.mark.django_db
def test_authoritative_patch_and_delete_refused_and_2026_1_bytes_stay(
    auth, create_user, create_scoped_role,
):
    schema = {
        "inputs": ["basic_salary", "service_years"],
        "formula": {
            "type": "tiered_accrual",
            "params": {"divisor": 26, "tiers": [{"up_to": 5, "days_per_year": 15}]},
        },
    }
    rule = ComplianceRule.objects.create(
        rule_id="kw-eosi-accrual-expat",
        version="2026.1",
        name="Frozen",
        category=ensure_ref("compliance_category", "eosi"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 1, 1),
        inputs_schema=schema,
        source_citation="frozen",
        is_authoritative=True,
    )
    assert rule.lifecycle == ComplianceRule.LIFECYCLE_AUTHORITATIVE
    client, _user = _lead(auth, create_user, create_scoped_role, "policy_editor")
    patched = client.patch(
        f"{RULES_URL}{rule.pk}/",
        {"inputs_schema": {"formula": {"type": "sum", "params": {}}}, "source_citation": "changed"},
        format="json",
    )
    assert patched.status_code == 409
    assert patched.json()["code"] == "immutable_rule"
    deleted = client.delete(f"{RULES_URL}{rule.pk}/")
    assert deleted.status_code == 409
    assert deleted.json()["code"] == "immutable_rule"
    rule.refresh_from_db()
    assert rule.version == "2026.1"
    assert rule.inputs_schema == schema
    assert rule.source_citation == "frozen"
    assert rule.is_authoritative is True


@pytest.mark.django_db
def test_drafter_cannot_publish_second_user_can(auth, create_user, create_scoped_role):
    drafter, drafter_user = _both(auth, create_user, create_scoped_role, "policy_prep")
    created = drafter.post(RULES_URL, _payload(), format="json")
    assert created.status_code == 201, created.content
    pk = created.json()["id"]
    submitted = drafter.post(f"{RULES_URL}{pk}/submit/", {}, format="json")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["lifecycle"] == "in_review"
    frozen = drafter.patch(
        f"{RULES_URL}{pk}/",
        {"name": "renamed after submit"},
        format="json",
    )
    assert frozen.status_code == 409
    assert frozen.json()["code"] == "frozen_draft"
    gone = drafter.post(f"{RULES_URL}{pk}/publish/", {}, format="json")
    assert gone.status_code == 404
    refused = drafter.post(f"{DESK_URL}{pk}/publish/", {}, format="json")
    assert refused.status_code == 403
    assert refused.json()["code"] == "sod_same_actor"
    publisher, publisher_user = _desk(auth, create_user, create_scoped_role, "policy_pub")
    assert publisher_user.pk != drafter_user.pk
    published = publisher.post(f"{DESK_URL}{pk}/publish/", {}, format="json")
    assert published.status_code == 200, published.content
    body = published.json()
    assert body["state"] == "authoritative"
    assert body["publisher_id"] == publisher_user.pk
    assert body["preparer_id"] == drafter_user.pk
    assert body["publisher_id"] != body["preparer_id"]
    rule = ComplianceRule.objects.get(pk=pk)
    assert rule.lifecycle == ComplianceRule.LIFECYCLE_AUTHORITATIVE
    assert rule.is_authoritative is True
    event = GovernanceEvent.objects.filter(
        entity_type="ComplianceRule", entity_id=pk, action="publish",
    ).first()
    assert event is not None
    assert event.before["lifecycle"] == "in_review"
    assert event.after["lifecycle"] == "authoritative"


@pytest.mark.django_db
def test_publish_without_preparer_matches_payroll_code(auth, create_user, create_scoped_role):
    rule = ComplianceRule.objects.create(
        rule_id="policy-noprep",
        version="2026.2",
        name="No preparer",
        category=ensure_ref("compliance_category", "other"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 6, 1),
        source_citation="cited",
        inputs_schema=_formula(),
        test_cases=[{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}],
        lifecycle=ComplianceRule.LIFECYCLE_IN_REVIEW,
        is_authoritative=False,
    )
    client, _user = _desk(auth, create_user, create_scoped_role, "policy_stranger")
    resp = client.post(f"{DESK_URL}{rule.pk}/publish/", {}, format="json")
    assert resp.status_code == 403
    assert resp.json()["code"] == "sod_missing_preparer"


@pytest.mark.django_db
def test_failing_examples_block_publish(auth, create_user, create_scoped_role):
    drafter, _user = _lead(auth, create_user, create_scoped_role, "policy_bad_ex")
    created = drafter.post(
        RULES_URL,
        _payload(test_cases=[{"inputs": {"a": "2", "b": "3"}, "expected": "9.000"}]),
        format="json",
    )
    assert created.status_code == 201, created.content
    pk = created.json()["id"]
    assert drafter.post(f"{RULES_URL}{pk}/submit/", {}, format="json").status_code == 200
    publisher, _other = _desk(auth, create_user, create_scoped_role, "policy_bad_pub")
    refused = publisher.post(f"{DESK_URL}{pk}/publish/", {}, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == "examples_failed"
    rule = ComplianceRule.objects.get(pk=pk)
    assert rule.lifecycle == ComplianceRule.LIFECYCLE_IN_REVIEW


@pytest.mark.django_db
def test_copy_forward_leaves_published_row_unchanged(auth, create_user, create_scoped_role):
    schema = _formula()
    rule = ComplianceRule.objects.create(
        rule_id="policy-live",
        version="2026.1",
        name="Live",
        category=ensure_ref("compliance_category", "other"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 1, 1),
        inputs_schema=schema,
        source_citation="cited",
        test_cases=[{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}],
        is_authoritative=True,
    )
    client, _user = _lead(auth, create_user, create_scoped_role, "policy_copy")
    copied = client.post(f"{RULES_URL}{rule.pk}/copy-forward/", {}, format="json")
    assert copied.status_code == 201, copied.content
    body = copied.json()
    assert body["lifecycle"] == "draft"
    assert body["version"] == "2026.2"
    assert body["inputs_schema"] == schema
    rule.refresh_from_db()
    assert rule.lifecycle == ComplianceRule.LIFECYCLE_AUTHORITATIVE
    assert rule.inputs_schema == schema


@pytest.mark.django_db
def test_publish_event_failure_rolls_back(auth, create_user, create_scoped_role, monkeypatch):
    drafter, _user = _lead(auth, create_user, create_scoped_role, "policy_evt_a")
    created = drafter.post(RULES_URL, _payload(rule_id="policy-evt"), format="json")
    pk = created.json()["id"]
    assert drafter.post(f"{RULES_URL}{pk}/submit/", {}, format="json").status_code == 200

    def boom(*args, **kwargs):
        if kwargs.get("action") == "publish":
            raise RuntimeError("event store down")
        return None

    monkeypatch.setattr("catalog.policy_lifecycle.emit_governance_event", boom)
    publisher, _other = _desk(auth, create_user, create_scoped_role, "policy_evt_b")
    refused = publisher.post(f"{DESK_URL}{pk}/publish/", {}, format="json")
    assert refused.status_code == 500
    rule = ComplianceRule.objects.get(pk=pk)
    assert rule.lifecycle == ComplianceRule.LIFECYCLE_IN_REVIEW
    assert rule.is_authoritative is False


@pytest.mark.django_db
def test_missing_cited_gosi_version_does_not_fall_back():
    from people.validation import _gosi_bounds_finding

    ComplianceRule.objects.create(
        rule_id="kw-gosi",
        version="2026.1",
        name="Live gosi",
        category=ensure_ref("compliance_category", "gosi"),
        jurisdiction=ensure_ref("jurisdiction", "KW"),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "formula": {"type": "sum", "params": {"min_amount": "0", "max_amount": "999"}},
        },
        is_authoritative=True,
    )
    line = SimpleNamespace(
        id=1,
        line_type_id=1,
        line_type=SimpleNamespace(code="gosi"),
        rule_id="kw-gosi",
        rule_version="1999.1",
        amount=Decimal("10.000"),
        inputs={},
    )
    finding = _gosi_bounds_finding([line])
    assert finding is not None
    assert finding["passed"] is False
    assert finding["severity"] == "error"
    assert "1999.1" in finding["sample_failures"][0]
