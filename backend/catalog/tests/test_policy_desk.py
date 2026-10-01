# Data Trust policy desk. The lifecycle module stays free of host-domain words.
# The list is the publish surface; the preparer is not the publisher.

import inspect

import pytest

import catalog.policy_lifecycle as policy_lifecycle
from catalog.policy_lifecycle import list_versions
from people.policy_service import create_draft, submit
from people.tests.ref_helpers import ensure_ref

DESK_URL = "/carbon-api/catalog/policy-versions/"

_FORBIDDEN = (
    "kuwait",
    "payroll",
    "leave",
    "indemnity",
    "gosi",
    "nibras",
    "eduos",
    "carbon",
    "people",
)


def test_lifecycle_module_is_domain_free():
    text = inspect.getsource(policy_lifecycle).lower()
    for word in _FORBIDDEN:
        assert word not in text, word


@pytest.mark.django_db
def test_desk_lists_a_version_and_publisher_is_not_preparer(
    api_client, create_user, create_scoped_role, get_token_for_user,
):
    ensure_ref("compliance_category", "other")
    ensure_ref("jurisdiction", "KW")
    preparer = create_user("desk_preparer")
    publisher = create_user("desk_publisher")
    create_scoped_role(publisher, "catalog_lead")
    rule = create_draft({
        "rule_id": "desk-sample",
        "version": "2026.4",
        "name": "Desk sample",
        "category": "other",
        "jurisdiction": "KW",
        "effective_date": "2026-07-01",
        "source_citation": "cited text",
        "inputs_schema": {
            "formula": {"type": "multiply", "params": {"a": "a", "b": "b"}},
        },
        "test_cases": [{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}],
    }, preparer)
    submit(rule, preparer)

    lead = create_user("desk_lead_only")
    create_scoped_role(lead, "people_lead")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(lead)}")
    refused = api_client.get(DESK_URL)
    assert refused.status_code == 403

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(publisher)}")
    listed = api_client.get(DESK_URL)
    assert listed.status_code == 200, listed.content
    row = next(item for item in listed.json()["results"] if item["id"] == rule.pk)
    assert row["policy"] == "desk-sample"
    assert row["version"] == "2026.4"
    assert row["state"] == "in_review"
    assert row["preparer_id"] == preparer.pk
    assert row["publisher_id"] is None

    published = api_client.post(f"{DESK_URL}{rule.pk}/publish/", {}, format="json")
    assert published.status_code == 200, published.content
    body = published.json()
    assert body["state"] == "authoritative"
    assert body["publisher_id"] == publisher.pk
    assert body["preparer_id"] == preparer.pk
    assert body["publisher_id"] != body["preparer_id"]

    again = api_client.get(DESK_URL, {"q": "desk-sample", "state": "authoritative"})
    match = next(item for item in again.json()["results"] if item["id"] == rule.pk)
    assert match["publisher_id"] != match["preparer_id"]
    assert list_versions(query="desk-sample")[0]["policy"] == "desk-sample"
