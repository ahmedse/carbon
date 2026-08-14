"""Normalized knowledge-graph read API for the Pulse "Knowledge Graph" panel.

Task A of TASK-AI-WORKSPACE-PHASE-E. A read-only, read-layer endpoint that
normalizes the durable knowledge-graph tables into a single node/edge envelope
suitable for a force-directed graph visualization.

Design notes (mirror :mod:`ai.observability_api`):

* Read layer only — uses the Django ORM directly (correct at this layer),
  never the engine ``Store`` seam.
* ``KnowledgeNode`` / ``KnowledgeEdge`` are the primary graph. ``KgNode`` /
  ``KgEdge`` (the Phase-2 vendored engine tables) are merged in **only when
  they carry structure** and are tagged with a ``source_model`` discriminator.
* Caps (500 nodes / 1000 edges) with dangling-edge safety: an edge is emitted
  only if both endpoints resolve to a node in the capped node set.
* ``properties`` are recursively redacted with the shared ``_redact_secrets``
  helper imported from :mod:`ai.observability_api` (single source of truth).
"""

import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.permissions import AdminOrSuperuserOnly
from ai.models.core import KgEdge, KgNode
from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode
from ai.observability_api import _redact_secrets

log = logging.getLogger(__name__)

MAX_NODES = 500
MAX_EDGES = 1000


def _knowledge_node_to_dict(node: KnowledgeNode) -> dict:
    """Normalize a ``KnowledgeNode`` into the graph node envelope."""
    return {
        "id": node.id,
        "label": node.name,
        "type": node.node_type,
        "confidence": node.confidence,
        "verified": node.verified,
        "properties": _redact_secrets(node.properties or {}),
        "instance_id": node.instance_id,
        "source_model": "KnowledgeNode",
    }


def _kg_node_to_dict(node: KgNode) -> dict:
    """Normalize a ``KgNode`` into the graph node envelope.

    ``KgNode`` lacks ``verified`` (always ``False``) and uses ``type`` rather
    than ``node_type`` — mapped accordingly.
    """
    return {
        "id": node.id,
        "label": node.name,
        "type": node.type,
        "confidence": node.confidence,
        "verified": False,
        "properties": _redact_secrets(node.properties or {}),
        "instance_id": node.instance_id,
        "source_model": "KgNode",
    }


def _knowledge_edge_to_dict(edge: KnowledgeEdge) -> dict:
    """Normalize a ``KnowledgeEdge`` into the graph edge envelope."""
    return {
        "source": edge.source_node_id,
        "target": edge.target_node_id,
        "relationship": edge.relationship,
        "weight": edge.weight,
        "confidence": edge.confidence,
        "source_model": "KnowledgeEdge",
    }


def _kg_edge_to_dict(edge: KgEdge) -> dict:
    """Normalize a ``KgEdge`` into the graph edge envelope.

    ``KgEdge`` uses ``edge_type`` (not ``relationship``) and has no ``weight``
    (defaults to 1.0) — mapped accordingly.
    """
    return {
        "source": edge.source_node_id,
        "target": edge.target_node_id,
        "relationship": edge.edge_type,
        "weight": 1.0,
        "confidence": edge.confidence,
        "source_model": "KgEdge",
    }


# Which node namespace an edge's source/target ids belong to.
_EDGE_TO_NODE_MODEL = {
    "KnowledgeEdge": "KnowledgeNode",
    "KgEdge": "KgNode",
}


class GraphDataView(APIView):
    """GET /carbon-api/ai/pulse/graph/ — normalized, capped node/edge graph."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        # ── Nodes: primary (KnowledgeNode) first, then KgNode, capped ────────
        knowledge_nodes = scope_ai_queryset(KnowledgeNode.objects, request.user)
        kg_nodes = scope_ai_queryset(KgNode.objects, request.user)

        raw_node_count = knowledge_nodes.count() + kg_nodes.count()

        nodes = [_knowledge_node_to_dict(n) for n in knowledge_nodes[:MAX_NODES]]
        remaining = MAX_NODES - len(nodes)
        if remaining > 0:
            nodes.extend(_kg_node_to_dict(n) for n in kg_nodes[:remaining])

        node_truncated = raw_node_count > len(nodes)

        # Resolve edges against the capped node set, namespaced by source model
        # so KnowledgeNode/KgNode id collisions can never cross-link.
        node_keys = {(n["source_model"], n["id"]) for n in nodes}

        def _resolves(edge: dict) -> bool:
            model = _EDGE_TO_NODE_MODEL[edge["source_model"]]
            return (
                (model, edge["source"]) in node_keys
                and (model, edge["target"]) in node_keys
            )

        edges = [
            e
            for e in (
                _knowledge_edge_to_dict(e)
                for e in scope_ai_queryset(KnowledgeEdge.objects, request.user)
            )
            if _resolves(e)
        ]
        edges.extend(
            e
            for e in (
                _kg_edge_to_dict(e)
                for e in scope_ai_queryset(KgEdge.objects, request.user)
            )
            if _resolves(e)
        )

        edge_truncated = len(edges) > MAX_EDGES
        edges = edges[:MAX_EDGES]

        # ── Stats ────────────────────────────────────────────────────────────
        node_types: dict = {}
        for n in nodes:
            node_types[n["type"]] = node_types.get(n["type"], 0) + 1

        relationship_counts: dict = {}
        for e in edges:
            relationship_counts[e["relationship"]] = (
                relationship_counts.get(e["relationship"], 0) + 1
            )

        stats = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "truncated": node_truncated or edge_truncated,
            "node_types": node_types,
            "relationship_counts": relationship_counts,
        }

        return Response({"nodes": nodes, "edges": edges, "stats": stats})
