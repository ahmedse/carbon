"""P3-01 — ``Capability`` model + loader from ``api_catalog.yaml`` (host-side).

Covers the loader reading the domain pack through the DomainPack port, the
fail-closed host-action validation, and the NeutralDomainPack fallback.
"""
from __future__ import annotations

import pytest

from ai.engine.ports.domain import NeutralDomainPack
from ai.models.capability import (
    Capability,
    CapabilityValidationError,
    load_capabilities,
    sync_capabilities,
)

PILOT_CAPABILITY_IDS = {
    "dq.rule.validate",
    "dq.rule.review",
    "dq.rule.publish",
    "dq.rule.active_revision_matches_approved_revision",
}


def test_load_capabilities_registers_pilot_capabilities():
    capabilities = load_capabilities()
    ids = {cap.capability_id for cap in capabilities}
    assert ids == PILOT_CAPABILITY_IDS
    # Every loaded capability resolved a host action (validated, never skipped).
    assert all(cap.host_action for cap in capabilities)


def test_pilot_contracts_have_correct_kind_and_approval():
    by_id = {cap.capability_id: cap for cap in load_capabilities()}

    assert by_id["dq.rule.validate"].kind == "read_only"
    assert by_id["dq.rule.validate"].requires_confirmation is False

    assert by_id["dq.rule.review"].kind == "human_task"

    assert by_id["dq.rule.publish"].kind == "mutation"
    assert by_id["dq.rule.publish"].requires_confirmation is True
    assert by_id["dq.rule.publish"].approval_requirements.get("requires_grant") is True

    assert by_id["dq.rule.active_revision_matches_approved_revision"].kind == "assertion"


def test_unknown_host_action_raises_validation_error():
    spec = {
        "capability_id": "dq.rule.nonexistent",
        "business_name": "Nope",
        "kind": "read_only",
        "host_action": "dq.rule.nonexistent",
    }
    with pytest.raises(CapabilityValidationError):
        Capability.from_spec(spec)


def test_missing_host_action_raises_validation_error():
    spec = {"capability_id": "dq.rule.validate", "kind": "read_only"}
    with pytest.raises(CapabilityValidationError):
        Capability.from_spec(spec)


def test_neutral_domain_pack_yields_no_capabilities():
    assert load_capabilities(pack=NeutralDomainPack()) == []


@pytest.mark.django_db
def test_sync_capabilities_is_idempotent():
    first = sync_capabilities()
    second = sync_capabilities()

    assert len(first) == len(PILOT_CAPABILITY_IDS)
    assert Capability.objects.count() == len(PILOT_CAPABILITY_IDS)
    assert {c.capability_id for c in second} == PILOT_CAPABILITY_IDS
