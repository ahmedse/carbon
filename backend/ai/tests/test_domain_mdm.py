"""
Phase 24 — MDM domain registration (remaining domains segment) tests.

Covers:
  - domain registration + lookup via ai.domain_protocol
  - DomainContext shape (knowledge + config with capability gates)
  - manifest surface (task types → conversation registry, entry points,
    starter prompts, system prompt extension)
  - build_workspace_context entity resolution (entity / reference_set)
  - validate_task_payload fail-fast rules
  - manifest API endpoints (GET /carbon-api/ai/pulse/apps/ + .../apps/mdm/)
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from ai.domain.mdm import MdmDomainAI
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
    return User.objects.create_user(username="mdm-worker", password="secret123")


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def reference_set(db):
    from mdm.models import ReferenceSet, ReferenceValue

    rs = ReferenceSet.objects.create(
        name="emission_factors", lifecycle_state=ReferenceSet.LIFECYCLE_ACTIVE,
    )
    value = ReferenceValue.objects.create(
        reference_set=rs, code="CO2", label="Carbon Dioxide",
        metadata={"formula": "44.01"},
    )
    return rs, value


# ── Registration & lookup ─────────────────────────────────────────────────


def test_mdm_domain_registered():
    assert has_domain("mdm") is True


def test_get_domain_returns_mdm_class():
    assert get_domain("mdm") is MdmDomainAI


def test_get_domain_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        get_domain("nope")


def test_list_domains_includes_mdm():
    assert "mdm" in list_domains()


def test_duplicate_registration_raises():
    with pytest.raises(ValueError):
        register_domain("mdm", MdmDomainAI)


# ── DomainContext content ─────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    assert MdmDomainAI.app_identifier == "mdm"
    assert MdmDomainAI.app_display_name == "Master Data"


def test_domain_context_knowledge_shape():
    ctx = MdmDomainAI().get_domain_context()
    knowledge = ctx.domain_knowledge
    assert knowledge["model"] == "reference sets of reference values"
    assert set(knowledge["lifecycle"]) == {"draft", "active", "deprecated", "archived"}
    assert knowledge["transition_rules"]["active"] == ["deprecated"]
    assert knowledge["mutation_rule"] == "assistants propose, humans confirm"
    assert "gold_record_confidence" in knowledge
    assert "dedup_basis" in knowledge


def test_domain_context_config_shape():
    ctx = MdmDomainAI().get_domain_context()
    config = ctx.domain_config
    assert config["capability_gate_view"] == "mdm:view"
    assert config["capability_gate_manage"] == "mdm:manage"
    assert config["read_only"] is True
    assert config["confirmation_required"] is True


# ── Manifest surface ──────────────────────────────────────────────────────


def test_manifest_task_types_declared():
    types = MdmDomainAI.supported_task_types
    for task_type in ("mdm_explain", "mdm_dedup", "mdm_merge_draft"):
        assert task_type in types


def test_mdm_task_types_flow_into_conversation_registry():
    allowed = supported_conversation_types()
    for task_type in ("mdm_explain", "mdm_dedup", "mdm_merge_draft"):
        assert task_type in allowed


def test_entry_points_shape():
    for ep in MdmDomainAI.entry_points:
        assert ep["label"]
        assert ep["task_type"] in MdmDomainAI.supported_task_types
        assert ep["icon"]
        assert ep["on_entity"]


def test_starter_prompts_cover_mdm_surfaces():
    prompts = MdmDomainAI.starter_prompts
    for key in ("entity", "reference_set", "default"):
        assert key in prompts
    for chip in prompts["entity"]:
        assert chip["label"] and chip["prompt"] and chip["task_type"]


def test_system_prompt_extension_grounds_no_mutation():
    ext = MdmDomainAI.system_prompt_extension
    assert ext
    assert "never" in ext and "confirm" in ext


# ── Workspace context enrichment ──────────────────────────────────────────


def test_build_workspace_context_entity(reference_set):
    rs, value = reference_set
    ctx = MdmDomainAI().build_workspace_context(None, "entity", value.id)
    assert ctx["value_code"] == "CO2"
    assert ctx["value_label"] == "Carbon Dioxide"
    assert ctx["value_active"] is True
    assert ctx["reference_set_name"] == "emission_factors"
    assert ctx["reference_set_lifecycle"] == "active"


def test_build_workspace_context_reference_set(reference_set):
    rs, value = reference_set
    ctx = MdmDomainAI().build_workspace_context(None, "reference_set", rs.id)
    assert ctx["reference_set_name"] == "emission_factors"
    assert ctx["reference_set_lifecycle"] == "active"
    assert ctx["active_value_count"] == 1


def test_build_workspace_context_unknown_entity_returns_empty(reference_set):
    ctx = MdmDomainAI().build_workspace_context(None, "entity", 999999)
    assert ctx == {}
    ctx = MdmDomainAI().build_workspace_context(None, None, None)
    assert ctx == {}


# ── Payload validation ────────────────────────────────────────────────────


def test_validate_task_payload_mdm_requires_entity_ref():
    ok, _ = MdmDomainAI().validate_task_payload("mdm_explain", {"entity_type": "entity", "entity_id": 1})
    assert ok is True
    ok, _ = MdmDomainAI().validate_task_payload("mdm_dedup", {"reference_set_id": 1, "code": "X"})
    assert ok is True
    ok, reason = MdmDomainAI().validate_task_payload("mdm_explain", {})
    assert ok is False and "entity_type" in reason


def test_validate_task_payload_merge_requires_all_ids():
    ok, _ = MdmDomainAI().validate_task_payload(
        "mdm_merge_draft", {"set_id": 1, "duplicate_value_id": 2, "gold_value_id": 3}
    )
    assert ok is True
    ok, reason = MdmDomainAI().validate_task_payload("mdm_merge_draft", {"set_id": 1})
    assert ok is False and "duplicate_value_id" in reason


def test_validate_task_payload_chat_always_passes():
    ok, reason = MdmDomainAI().validate_task_payload("chat", {})
    assert ok is True and reason == ""


# ── Manifest API endpoints ────────────────────────────────────────────────


def test_manifest_list_includes_mdm(authed_client):
    resp = authed_client.get("/carbon-api/ai/pulse/apps/")
    assert resp.status_code == 200
    ids = [m["app_identifier"] for m in resp.data["apps"]]
    assert "mdm" in ids


def test_manifest_detail_returns_mdm(authed_client):
    resp = authed_client.get("/carbon-api/ai/pulse/apps/mdm/")
    assert resp.status_code == 200
    assert resp.data["app_identifier"] == "mdm"
    assert resp.data["display_name"] == "Master Data"
    assert "mdm_dedup" in resp.data["supported_task_types"]
