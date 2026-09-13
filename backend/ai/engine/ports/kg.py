"""KnowledgeGraphStore port — structured graph data access.

Replaces the engine's direct ``ai.models.knowledge_graph.KnowledgeNode`` /
``KnowledgeEdge`` ORM access in
:class:`ai.engine.knowledge_graph.store.KnowledgeGraphStore` (P2-03).  The host
adapter persists nodes/edges behind ``scope_q()`` and owns the vector index and
per-instance adjacency; the engine requests structure + semantic lookup.
"""
from __future__ import annotations

from typing import Any, Protocol, TypedDict


class NodeRecord(TypedDict, total=False):
    """A knowledge-graph node projection."""

    id: str
    instance_id: str
    name: str
    node_type: str
    description: str | None
    metadata: dict[str, Any] | None


class EdgeRecord(TypedDict, total=False):
    """A knowledge-graph edge projection."""

    id: str
    instance_id: str
    source_id: str
    target_id: str
    relationship: str
    weight: float | None
    metadata: dict[str, Any] | None


class KnowledgeGraphStore(Protocol):
    """CRUD + semantic lookup over the knowledge graph, scoped by instance."""

    async def add_node(self, node_data: dict[str, Any]) -> NodeRecord:
        """Insert a node and return its record."""
        ...

    async def upsert_node(
        self, name: str, instance_id: str, node_type: str, **kwargs: Any
    ) -> NodeRecord:
        """Insert or update a node by name within an instance."""
        ...

    async def update_node(self, node_id: str, updates: dict[str, Any]) -> NodeRecord | None:
        """Update a node; return the updated record or ``None`` if not found."""
        ...

    async def get_node(self, node_id: str) -> NodeRecord | None:
        """Return a node by id."""
        ...

    async def get_nodes_by_type(self, instance_id: str, node_type: str) -> list[NodeRecord]:
        """Return nodes of a given type within an instance."""
        ...

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges; return whether a node was removed."""
        ...

    async def add_edge(self, edge_data: dict[str, Any]) -> EdgeRecord:
        """Insert an edge and return its record."""
        ...

    async def query_edges(
        self, instance_id: str, relationship: str | None = None, **filters: Any
    ) -> list[EdgeRecord]:
        """Return edges matching relationship/filters within an instance."""
        ...

    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge; return whether an edge was removed."""
        ...

    async def semantic_search(
        self, instance_id: str, query_text: str, limit: int = 10
    ) -> list[NodeRecord]:
        """Semantically search nodes within an instance."""
        ...

    async def get_neighbors(self, instance_id: str, node_id: str) -> list[NodeRecord]:
        """Return neighbours of a node within an instance."""
        ...
