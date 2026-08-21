"""
Phase 24 — Data Products domain registration (remaining domains segment) tests.

Covers:
  - domain registration + lookup via ai.domain_protocol
  - DomainContext shape (knowledge + config with capability gates)
  - manifest surface (task types → conversation registry, entry points,
    starter prompts, system prompt extension)
  - build_workspace_context entity resolution (dataset)
  - validate_task_payload fail-fast rules
  - manifest API endpoints (GET /carbon-api/ai/pulse/apps/ + .../apps/data_product/)
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from ai.domain.data_product import DataProductDomainAI
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
    return User.objects.create_user(username="dp-worker", password="secret123")


@pytest.fixture
def authed_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def dataset(db):
    from catalog.models import DataDomain, Dataset, DatasetVersion
    from core.models import Module
    from dataschema.models import DataTable
    from mdm.models import OrgUnit

    org_unit = OrgUnit.objects.create(name="Engineering", org_type="college")
    module = Module.objects.create(name="Campus Ops", org_unit=org_unit)
    domain = DataDomain.objects.create(name="Energy", slug="energy")
    table = DataTable.objects.create(title="Energy", name="energy", module=module)

    ds = Dataset.objects.create(
        name="Energy Consumption", slug="energy-consumption",
        module=module, domain=domain, status="active",
    )
    version = DatasetVersion.objects.create(
        dataset=ds, version_number=1, data_table=table,
        row_count=1200, health_score=0.94,
        health_detail={"completeness": 0.98, "validity": 0.95, "freshness": 1.0},
        status="approved",
    )
    ds.current_version = version
    ds.save()
    return ds


# ── Registration & lookup ─────────────────────────────────────────────────


def test_data_product_domain_registered():
    assert has_domain("data_product") is True


def test_get_domain_returns_data_product_class():
    assert get_domain("data_product") is DataProductDomainAI


def test_get_domain_unknown_raises_keyerror():
    with pytest.raises(KeyError):
        get_domain("nope")


def test_list_domains_includes_data_product():
    assert "data_product" in list_domains()


def test_duplicate_registration_raises():
    with pytest.raises(ValueError):
        register_domain("data_product", DataProductDomainAI)


# ── DomainContext content ─────────────────────────────────────────────────


def test_app_identifier_and_display_name():
    assert DataProductDomainAI.app_identifier == "data_product"
    assert DataProductDomainAI.app_display_name == "Data Products"


def test_domain_context_knowledge_shape():
    ctx = DataProductDomainAI().get_domain_context()
    knowledge = ctx.domain_knowledge
    assert knowledge["model"].startswith("Dataset")
    assert set(knowledge["version_statuses"]) == {"pending", "approved", "rejected"}
    assert knowledge["versioning_rule"] == "versions freeze on approval; new data = new version"
    assert set(knowledge["health_dimensions"]) == {"completeness", "validity", "freshness"}
    assert knowledge["mutation_rule"] == "assistants propose, humans confirm"


def test_domain_context_config_shape():
    ctx = DataProductDomainAI().get_domain_context()
    config = ctx.domain_config
    assert config["capability_gate_view"] == "catalog:view"
    assert config["capability_gate_manage"] == "catalog:manage_products"
    assert config["read_only"] is True
    assert config["confirmation_required"] is True


# ── Manifest surface ──────────────────────────────────────────────────────


def test_manifest_task_types_declared():
    types = DataProductDomainAI.supported_task_types
    for task_type in ("product_explain", "product_health", "product_draft"):
        assert task_type in types


def test_data_product_task_types_flow_into_conversation_registry():
    allowed = supported_conversation_types()
    for task_type in ("product_explain", "product_health", "product_draft"):
        assert task_type in allowed


def test_entry_points_shape():
    for ep in DataProductDomainAI.entry_points:
        assert ep["label"]
        assert ep["task_type"] in DataProductDomainAI.supported_task_types
        assert ep["icon"]
        assert ep["on_entity"]


def test_starter_prompts_cover_data_product_surfaces():
    prompts = DataProductDomainAI.starter_prompts
    for key in ("dataset", "default"):
        assert key in prompts
    for chip in prompts["dataset"]:
        assert chip["label"] and chip["prompt"] and chip["task_type"]


def test_system_prompt_extension_grounds_no_mutation():
    ext = DataProductDomainAI.system_prompt_extension
    assert ext
    assert "never" in ext and "confirm" in ext


# ── Workspace context enrichment ──────────────────────────────────────────


def test_build_workspace_context_dataset(dataset):
    ctx = DataProductDomainAI().build_workspace_context(None, "dataset", dataset.id)
    assert ctx["dataset_name"] == "Energy Consumption"
    assert ctx["dataset_status"] == "active"
    assert ctx["dataset_classification"] == "internal"
    assert ctx["domain_name"] == "Energy"
    assert ctx["current_version_number"] == 1
    assert ctx["current_version_health"] == 0.94


def test_build_workspace_context_unknown_entity_returns_empty(dataset):
    ctx = DataProductDomainAI().build_workspace_context(None, "dataset", "00000000-0000-0000-0000-000000000000")
    assert ctx == {}
    ctx = DataProductDomainAI().build_workspace_context(None, None, None)
    assert ctx == {}


# ── Payload validation ────────────────────────────────────────────────────


def test_validate_task_payload_product_requires_dataset_id():
    for task_type in ("product_explain", "product_health", "product_draft"):
        ok, _ = DataProductDomainAI().validate_task_payload(task_type, {"dataset_id": 1})
        assert ok is True
        ok, reason = DataProductDomainAI().validate_task_payload(task_type, {})
        assert ok is False and "dataset_id" in reason


def test_validate_task_payload_chat_always_passes():
    ok, reason = DataProductDomainAI().validate_task_payload("chat", {})
    assert ok is True and reason == ""


# ── Manifest API endpoints ────────────────────────────────────────────────


def test_manifest_list_includes_data_product(authed_client):
    resp = authed_client.get("/carbon-api/ai/pulse/apps/")
    assert resp.status_code == 200
    ids = [m["app_identifier"] for m in resp.data["apps"]]
    assert "data_product" in ids


def test_manifest_detail_returns_data_product(authed_client):
    resp = authed_client.get("/carbon-api/ai/pulse/apps/data_product/")
    assert resp.status_code == 200
    assert resp.data["app_identifier"] == "data_product"
    assert resp.data["display_name"] == "Data Products"
    assert "product_health" in resp.data["supported_task_types"]
