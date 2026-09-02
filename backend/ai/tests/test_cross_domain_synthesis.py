"""Phase E3 — cross-domain synthesis (``cross_synthesize``) tests.

Deterministic (no live LLM): seeds ENTITY nodes + edges in the knowledge graph
through the Django Store backend, then asserts the tool's structured output —
shared-node detection, per-domain provenance, temporal/causal alignment, and
read-only behavior.

Seed rows are committed (``transaction=True``) so the plugin's ``sync_to_async``
session — a separate connection — can see them, and a unique ``instance_id`` per
test keeps assertions isolated from the reused test DB.  A ``finally`` cleanup
removes the rows so nothing lingers across runs.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.agent.plugins import ToolContext
from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode
from ai.store import reset_store


@pytest.fixture
def django_store():
    """Run the plugin against the Django (PostgreSQL) Store backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


def _instance_id() -> str:
    return f"xsynth_{uuid4().hex[:10]}"


def _entity(instance_id: str, name: str) -> KnowledgeNode:
    return KnowledgeNode.objects.create(
        instance_id=instance_id,
        node_type="ENTITY",
        name=name,
        description="",
        properties={},
    )


def _cleanup(instance_id: str) -> None:
    KnowledgeEdge.objects.filter(instance_id=instance_id).delete()
    KnowledgeNode.objects.filter(instance_id=instance_id).delete()


async def _execute(results, question, instance_id) -> dict:
    from ai.plugins.cross_synthesize import CrossDomainSynthesisTool

    tool = CrossDomainSynthesisTool()
    ctx = ToolContext(instance_id=instance_id)
    return await tool.execute({"results": results, "question": question}, ctx=ctx)


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_shared_entity_across_domains_is_joined(django_store):
    instance_id = _instance_id()
    node = _entity(instance_id, "org_south_valley")
    try:
        results = [
            {
                "domain": "emissions",
                "data": {"co2e_kg": 1200, "week": "2026-05-18"},
                "entity_ids": [node.id],
            },
            {
                # Reference the same node by *name* to exercise name resolution.
                "domain": "dq",
                "data": {"failed_checks": 40, "week": "2026-05-18"},
                "entity_ids": ["org_south_valley"],
            },
        ]
        out = asyncio.run(
            _execute(results, "Why did emissions spike this week?", instance_id)
        )

        assert out["requires_confirmation"] is False
        assert {s["domain"] for s in out["sources"]} == {"emissions", "dq"}
        assert all(s["evidence"] for s in out["sources"])
        assert out["shared_nodes"] == [
            {"id": node.id, "name": "org_south_valley", "node_type": "ENTITY"}
        ]
        assert "same entity" in out["synthesis"]
        assert "org_south_valley" in out["synthesis"]
    finally:
        _cleanup(instance_id)


@pytest.mark.django_db(transaction=True)
def test_no_shared_node_does_not_fabricate_connection(django_store):
    instance_id = _instance_id()
    emissions_node = _entity(instance_id, "emissions_calc")
    dq_node = _entity(instance_id, "dq_run")
    try:
        results = [
            {
                "domain": "emissions",
                "data": {"co2e_kg": 10},
                "entity_ids": [emissions_node.id],
            },
            {"domain": "dq", "data": {"failed_checks": 2}, "entity_ids": [dq_node.id]},
        ]
        out = asyncio.run(_execute(results, "Is there any link?", instance_id))

        assert out["shared_nodes"] == []
        assert len(out["sources"]) == 2
        assert {s["domain"] for s in out["sources"]} == {"emissions", "dq"}
        # The synthesis must stay honest: no shared entity, no fabricated link.
        assert "separate entities" in out["synthesis"]
        assert "same entity" not in out["synthesis"]
        assert "same entities" not in out["synthesis"]
    finally:
        _cleanup(instance_id)


@pytest.mark.django_db(transaction=True)
def test_execute_is_read_only_and_side_effect_free(django_store):
    instance_id = _instance_id()
    node = _entity(instance_id, "emissions_calc")
    try:
        results = [
            {"domain": "emissions", "data": {"co2e_kg": 10}, "entity_ids": [node.id]},
        ]
        before_nodes = KnowledgeNode.objects.filter(instance_id=instance_id).count()
        before_edges = KnowledgeEdge.objects.filter(instance_id=instance_id).count()

        out = asyncio.run(_execute(results, "q", instance_id))

        assert out["requires_confirmation"] is False
        assert (
            KnowledgeNode.objects.filter(instance_id=instance_id).count()
            == before_nodes
        )
        assert (
            KnowledgeEdge.objects.filter(instance_id=instance_id).count()
            == before_edges
        )
    finally:
        _cleanup(instance_id)


@pytest.mark.django_db(transaction=True)
def test_temporal_alignment_surfaces_causal_edges(django_store):
    instance_id = _instance_id()
    dq_node = _entity(instance_id, "dq_failure_batch")
    emissions_node = _entity(instance_id, "emissions_facility")
    KnowledgeEdge.objects.create(
        instance_id=instance_id,
        source_node_id=dq_node.id,
        target_node_id=emissions_node.id,
        relationship="TRIGGERS",
        valid_from="2026-05-18T00:00:00Z",
        valid_to=None,
    )
    try:
        results = [
            {"domain": "dq", "data": {"failed_checks": 40}, "entity_ids": [dq_node.id]},
            {
                "domain": "emissions",
                "data": {"co2e_kg": 1200},
                "entity_ids": [emissions_node.id],
            },
        ]
        out = asyncio.run(_execute(results, "What triggered the spike?", instance_id))

        assert len(out["temporal_alignment"]) == 1
        link = out["temporal_alignment"][0]
        assert link["relationship"] == "TRIGGERS"
        assert link["source"]["name"] == "dq_failure_batch"
        assert link["target"]["name"] == "emissions_facility"
        assert "triggers" in out["synthesis"].lower()
    finally:
        _cleanup(instance_id)
