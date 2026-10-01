# A second policy type uses the existing lifecycle. The service is not edited
# to name this type, and this is not a Finance or Inventory app.

import inspect

import pytest

import catalog.policy_lifecycle as policy_lifecycle
from people import policy_service
from people.policy_service import create_draft, publish, submit
from people.tests.ref_helpers import ensure_ref


@pytest.mark.django_db
def test_probe_plane_publishes_without_a_service_edit(create_user):
    source = inspect.getsource(policy_service)
    assert "probe_plane" not in source
    assert "policy_lifecycle" in source
    assert "probe_plane" not in inspect.getsource(policy_lifecycle)
    ensure_ref("compliance_category", "probe_plane")
    ensure_ref("jurisdiction", "KW")
    drafter = create_user("probe_drafter")
    publisher = create_user("probe_publisher")
    rule = create_draft({
        "rule_id": "probe-plane",
        "version": "2026.9",
        "name": "Probe plane",
        "category": "probe_plane",
        "jurisdiction": "KW",
        "effective_date": "2026-08-01",
        "source_citation": "contract",
        "inputs_schema": {
            "formula": {"type": "multiply", "params": {"a": "a", "b": "b"}},
        },
        "test_cases": [{"inputs": {"a": "2", "b": "3"}, "expected": "6.000"}],
    }, drafter)
    submit(rule, drafter)
    published = publish(rule, publisher)
    assert published.lifecycle == "authoritative"
    assert published.category.code == "probe_plane"
