"""DjangoKGAdapter — host implementation of the KnowledgeGraphStore port.

Persists :class:`ai.models.knowledge_graph.KnowledgeNode` / ``KnowledgeEdge``
rows behind ``scope_q()`` and projects them onto the ``NodeRecord`` /
``EdgeRecord`` dicts the engine port expects.  The vector index is out of scope
for this adapter contract, so :meth:`semantic_search` degrades to a
deterministic substring match (name/description) over instance-scoped nodes —
fail-visible, never a fabricated hit.

Tenancy model
-------------
The adapter holds no user context (``__init__(self, db)``), so every
instance-scoped read uses ``scope_q(model, instance_id, None)`` (``global |
shared`` visibility).  Id-addressed reads (``get_node`` / ``update_node`` /
``delete_node`` / ``delete_edge``) apply the equivalent visibility filter
without an instance predicate, because the port signatures carry no
``instance_id``.  Writes default to ``visibility="shared"`` (instance-level
knowledge-graph data) unless the caller supplies an explicit ``visibility`` /
``host_user_id`` in ``node_data`` / ``edge_data``.

RULE_20: imports only ``ai.*``, Django, and the stdlib.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Q

from ai.engine.ports.kg import EdgeRecord, NodeRecord
from ai.models.base import generate_uuid
from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode
from ai.store import first, scope_q

# Visibility triplet applied to id-only reads (no instance_id available in the
# port signature).  Mirrors scope_q(..., None) — the adapter has no user.
_VISIBLE = Q(visibility="global") | Q(visibility="shared")


def _node_to_record(node: KnowledgeNode) -> NodeRecord:
    return {
        "id": node.id,
        "instance_id": node.instance_id,
        "name": node.name,
        "node_type": node.node_type,
        "description": node.description or None,
        "metadata": node.properties or {},
    }


def _edge_to_record(edge: KnowledgeEdge) -> EdgeRecord:
    return {
        "id": edge.id,
        "instance_id": edge.instance_id,
        "source_id": edge.source_node_id,
        "target_id": edge.target_node_id,
        "relationship": edge.relationship,
        "weight": edge.weight,
        "metadata": edge.properties or {},
    }


class DjangoKGAdapter:
    """Knowledge-graph adapter implementing ``ai.engine.ports.kg.KnowledgeGraphStore``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    # ── Node operations ──────────────────────────────────────────────────

    async def add_node(self, node_data: dict[str, Any]) -> NodeRecord:
        node = KnowledgeNode(
            id=node_data.get("id") or generate_uuid(),
            instance_id=node_data["instance_id"],
            node_type=node_data.get("node_type", "ENTITY"),
            name=node_data["name"],
            description=node_data.get("description", ""),
            properties=node_data.get("metadata") or node_data.get("properties") or {},
            source=node_data.get("source", "SCHEMA"),
            confidence=node_data.get("confidence", 0.8),
            verified=node_data.get("verified", False),
            visibility=node_data.get("visibility", "shared"),
            host_user_id=node_data.get("host_user_id"),
        )
        self.db.add(node)
        await self.db.commit()
        return _node_to_record(node)

    async def upsert_node(
        self, name: str, instance_id: str, node_type: str, **kwargs: Any
    ) -> NodeRecord:
        existing = first(
            await self.db.select(
                KnowledgeNode,
                scope_q(KnowledgeNode, instance_id, None),
                ("name", name),
            )
        )
        if existing is not None:
            updates = dict(kwargs)
            updates.pop("instance_id", None)
            updates.pop("name", None)
            updates.pop("node_type", None)
            updated = await self.update_node(existing.id, updates)
            return updated if updated is not None else _node_to_record(existing)

        return await self.add_node(
            {
                "name": name,
                "instance_id": instance_id,
                "node_type": node_type,
                **kwargs,
            }
        )

    async def update_node(
        self, node_id: str, updates: dict[str, Any]
    ) -> NodeRecord | None:
        node = first(
            await self.db.select(KnowledgeNode, ("id", node_id), _VISIBLE)
        )
        if node is None:
            return None
        for key, value in updates.items():
            if key == "metadata":
                key = "properties"
            if key in ("id", "instance_id"):
                continue  # immutable identity columns
            setattr(node, key, value)
        await self.db.commit()
        return _node_to_record(node)

    async def get_node(self, node_id: str) -> NodeRecord | None:
        node = first(
            await self.db.select(KnowledgeNode, ("id", node_id), _VISIBLE)
        )
        return _node_to_record(node) if node is not None else None

    async def get_nodes_by_type(
        self, instance_id: str, node_type: str
    ) -> list[NodeRecord]:
        rows = await self.db.select(
            KnowledgeNode,
            scope_q(KnowledgeNode, instance_id, None),
            ("node_type", node_type),
        )
        return [_node_to_record(n) for n in rows]

    async def delete_node(self, node_id: str) -> bool:
        node = first(
            await self.db.select(KnowledgeNode, ("id", node_id), _VISIBLE)
        )
        if node is None:
            return False
        edges = await self.db.select(
            KnowledgeEdge,
            Q(source_node_id=node_id) | Q(target_node_id=node_id),
        )
        for edge in edges:
            await self.db.delete(edge)
        await self.db.delete(node)
        await self.db.commit()
        return True

    # ── Edge operations ──────────────────────────────────────────────────

    async def add_edge(self, edge_data: dict[str, Any]) -> EdgeRecord:
        edge = KnowledgeEdge(
            id=edge_data.get("id") or generate_uuid(),
            instance_id=edge_data["instance_id"],
            source_node_id=edge_data["source_id"],
            target_node_id=edge_data["target_id"],
            relationship=edge_data["relationship"],
            weight=edge_data.get("weight", 1.0),
            properties=edge_data.get("metadata") or edge_data.get("properties") or {},
            confidence=edge_data.get("confidence", 1.0),
            source=edge_data.get("source", "SCHEMA"),
            visibility=edge_data.get("visibility", "shared"),
            host_user_id=edge_data.get("host_user_id"),
        )
        self.db.add(edge)
        await self.db.commit()
        return _edge_to_record(edge)

    async def query_edges(
        self, instance_id: str, relationship: str | None = None, **filters: Any
    ) -> list[EdgeRecord]:
        q = scope_q(KnowledgeEdge, instance_id, None)
        if relationship is not None:
            q &= Q(relationship=relationship)
        for key, value in filters.items():
            if key == "source_id":
                key = "source_node_id"
            elif key == "target_id":
                key = "target_node_id"
            q &= Q(**{key: value})
        rows = await self.db.select(KnowledgeEdge, q)
        return [_edge_to_record(e) for e in rows]

    async def delete_edge(self, edge_id: str) -> bool:
        edge = first(
            await self.db.select(KnowledgeEdge, ("id", edge_id), _VISIBLE)
        )
        if edge is None:
            return False
        await self.db.delete(edge)
        await self.db.commit()
        return True

    # ── Search / traversal ───────────────────────────────────────────────

    async def semantic_search(
        self, instance_id: str, query_text: str, limit: int = 10
    ) -> list[NodeRecord]:
        # The vector store is out of scope for the adapter contract; degrade to
        # a deterministic substring match so callers get a fail-visible,
        # non-fabricated result set.
        q = scope_q(KnowledgeNode, instance_id, None)
        q &= Q(name__icontains=query_text) | Q(description__icontains=query_text)
        rows = await self.db.select(KnowledgeNode, q)
        return [_node_to_record(n) for n in rows[:limit]]

    async def get_neighbors(
        self, instance_id: str, node_id: str
    ) -> list[NodeRecord]:
        edges = await self.db.select(
            KnowledgeEdge,
            scope_q(KnowledgeEdge, instance_id, None),
            Q(source_node_id=node_id) | Q(target_node_id=node_id),
        )
        neighbor_ids: set[str] = set()
        for edge in edges:
            if edge.source_node_id == node_id:
                neighbor_ids.add(edge.target_node_id)
            else:
                neighbor_ids.add(edge.source_node_id)
        if not neighbor_ids:
            return []
        rows = await self.db.select(
            KnowledgeNode,
            scope_q(KnowledgeNode, instance_id, None),
            ("id__in", list(neighbor_ids)),
        )
        return [_node_to_record(n) for n in rows]
