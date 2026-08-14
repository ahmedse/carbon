"""Normalized knowledge-graph read API tests (TASK-AI-WORKSPACE-PHASE-E, Task A).

Covers the ``/carbon-api/ai/pulse/graph/`` endpoint:

  * auth-gated (401 without a JWT)
  * normalizes KnowledgeNode/KnowledgeEdge into the node/edge envelope
  * redacts secret-bearing ``properties`` via the shared ``_redact_secrets``
  * drops dangling edges (source/target must resolve to a returned node)
  * merges KgNode/KgEdge with a ``source_model`` discriminator
  * caps nodes/edges and reports ``stats.truncated``

Assertions are presence-based (look up seeded rows by their generated ids /
unique names) rather than exact-count, because the project test DB is reused
(``--reuse-db``) and may retain rows from prior sessions.
"""

import pytest

from ai.models.core import KgEdge, KgNode
from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode

BASE = "/carbon-api/ai/pulse/graph"


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="ai-graph", password="secret123")


@pytest.fixture
def auth_client(api_client, get_token_for_user, user):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return api_client


def _get_body(auth_client):
    resp = auth_client.get(f"{BASE}/")
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.django_db
def test_graph_requires_auth(api_client):
    assert api_client.get(f"{BASE}/").status_code == 401


@pytest.mark.django_db
def test_graph_normalizes_nodes_and_edges(auth_client):
    n1 = KnowledgeNode.objects.create(
        instance_id="inst-1", node_type="ENTITY", name="Plant A"
    )
    n2 = KnowledgeNode.objects.create(
        instance_id="inst-1", node_type="LOCATION", name="Cairo"
    )
    KnowledgeEdge.objects.create(
        instance_id="inst-1",
        source_node_id=n1.id,
        target_node_id=n2.id,
        relationship="located_in",
    )

    body = _get_body(auth_client)

    node_by_id = {n["id"]: n for n in body["nodes"]}
    assert n1.id in node_by_id and n2.id in node_by_id
    assert node_by_id[n1.id]["label"] == "Plant A"
    assert node_by_id[n1.id]["type"] == "ENTITY"
    assert node_by_id[n1.id]["confidence"] == 0.8
    assert node_by_id[n1.id]["verified"] is False
    assert node_by_id[n1.id]["instance_id"] == "inst-1"
    assert node_by_id[n1.id]["source_model"] == "KnowledgeNode"

    assert body["stats"]["node_count"] >= 2
    assert body["stats"]["node_types"].get("ENTITY", 0) >= 1
    assert body["stats"]["node_types"].get("LOCATION", 0) >= 1

    my_edge = next(
        e for e in body["edges"]
        if e["source"] == n1.id and e["target"] == n2.id
    )
    assert my_edge["relationship"] == "located_in"
    assert my_edge["weight"] == 1.0
    assert my_edge["confidence"] == 1.0
    assert body["stats"]["edge_count"] >= 1
    assert body["stats"]["relationship_counts"].get("located_in", 0) >= 1


@pytest.mark.django_db
def test_graph_redacts_secret_properties(auth_client):
    node = KnowledgeNode.objects.create(
        instance_id="inst-1",
        node_type="ENTITY",
        name="Secretive",
        properties={"api_token": "sk-abcdef1234567890", "note": "public"},
    )

    body = _get_body(auth_client)
    by_id = {n["id"]: n for n in body["nodes"]}
    assert by_id[node.id]["properties"]["api_token"] == "[REDACTED]"
    assert by_id[node.id]["properties"]["note"] == "public"


@pytest.mark.django_db
def test_graph_drops_dangling_edges(auth_client):
    n1 = KnowledgeNode.objects.create(
        instance_id="inst-1", node_type="ENTITY", name="Orphan Source"
    )
    dangling_target = "missing-target-id-unique"
    # Edge pointing at a node id that does not exist -> must be dropped.
    KnowledgeEdge.objects.create(
        instance_id="inst-1",
        source_node_id=n1.id,
        target_node_id=dangling_target,
        relationship="points_to",
    )

    body = _get_body(auth_client)
    assert not any(
        e["source"] == n1.id and e["target"] == dangling_target
        for e in body["edges"]
    )
    by_id = {n["id"] for n in body["nodes"]}
    assert n1.id in by_id


@pytest.mark.django_db
def test_graph_merges_kg_models_with_discriminator(auth_client):
    kn = KnowledgeNode.objects.create(
        instance_id="inst-1", node_type="ENTITY", name="KN"
    )
    kgn = KgNode.objects.create(
        instance_id="inst-1", type="FACT", name="KG fact", confidence=0.9
    )
    # Self-referential KgEdge resolves only against KgNode ids.
    KgEdge.objects.create(
        instance_id="inst-1",
        source_node_id=kgn.id,
        target_node_id=kgn.id,
        edge_type="self_ref",
    )

    body = _get_body(auth_client)
    by_id = {n["id"]: n for n in body["nodes"]}

    assert by_id[kn.id]["source_model"] == "KnowledgeNode"
    assert by_id[kgn.id]["source_model"] == "KgNode"
    assert by_id[kgn.id]["label"] == "KG fact"
    assert by_id[kgn.id]["type"] == "FACT"  # KgNode uses `type`, not node_type
    assert by_id[kgn.id]["verified"] is False  # KgNode has no verified field

    kg_edge = next(
        e for e in body["edges"]
        if e["source"] == kgn.id and e["target"] == kgn.id
    )
    assert kg_edge["source_model"] == "KgEdge"
    assert kg_edge["relationship"] == "self_ref"  # KgEdge uses edge_type
    assert kg_edge["weight"] == 1.0  # KgEdge has no weight field -> default


@pytest.mark.django_db
def test_graph_truncates_at_node_cap(auth_client):
    for i in range(501):
        KnowledgeNode.objects.create(
            instance_id="inst-cap", node_type="ENTITY", name=f"Node {i}"
        )

    body = _get_body(auth_client)
    # 501 freshly-seeded nodes (plus any reused rows) always exceed the cap.
    assert body["stats"]["truncated"] is True
    assert body["stats"]["node_count"] == 500
    assert len(body["nodes"]) == 500
