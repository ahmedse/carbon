"""
KnowledgeGraphStore — data access layer for the knowledge graph.

Wraps three storage layers behind a single interface:
  - PostgreSQL via the Django Store (``ai.store.Session``) for structure
    and metadata (``ai.models.knowledge_graph``)
  - Vector store (pgvector/ChromaDB) for semantic search — optional, and
    degraded to ``None`` when unavailable
  - Module-level adjacency list (fast in-memory traversal)

No other module should directly query knowledge_nodes / knowledge_edges tables
or the 'knowledge_nodes' ChromaDB collection. Everything goes through this store.
"""
import json
import logging
from collections import deque
from datetime import datetime
from typing import Optional

from ai.engine.core.clock import utcnow
from uuid import uuid4

from django.db.models import Q

from ai.engine.knowledge_graph.models import (
    NODE_TYPES,
    RELATIONSHIP_TYPES,
    SOURCE_TYPES,
)
from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode
from ai.store import first

logger = logging.getLogger("pulse.knowledge_graph.store")

# ── Per-instance in-memory graph ─────────────────────────────────────────────
#
# INSTANCE ISOLATION: Each instance has its own independent adjacency list and
# node cache. Previously these were module-level globals shared across all
# instances — Carbon and Gigacast nodes were mixed in the same dicts.
#
# Structure per instance_id:
#   _adjacency[instance_id][node_id] → {
#       "out": [(edge_id, target_node_id, relationship, weight), ...],
#       "in":  [(edge_id, source_node_id, relationship, weight), ...]
#   }
#   _node_cache[instance_id][node_id] → {id, name, node_type, description, instance_id}
#
# Populated by load_graph() at startup and updated on every write.

_adjacency: dict[str, dict[str, dict]] = {}   # instance_id → node_id → {in/out}
_node_cache: dict[str, dict[str, dict]] = {}  # instance_id → node_id → node_data
_graph_loaded: dict[str, bool] = {}            # instance_id → bool


def _adj_for(instance_id: str) -> dict[str, dict]:
    """Get (or create) the adjacency dict for an instance."""
    if instance_id not in _adjacency:
        _adjacency[instance_id] = {}
    return _adjacency[instance_id]


def _cache_for(instance_id: str) -> dict[str, dict]:
    """Get (or create) the node cache dict for an instance."""
    if instance_id not in _node_cache:
        _node_cache[instance_id] = {}
    return _node_cache[instance_id]


def _is_loaded(instance_id: str) -> bool:
    return _graph_loaded.get(instance_id, False)


def _set_loaded(instance_id: str) -> None:
    _graph_loaded[instance_id] = True


# ── Adjacency helpers ─────────────────────────────────────────────────────────

def _ensure_adj(node_id: str, instance_id: str) -> None:
    adj = _adj_for(instance_id)
    if node_id not in adj:
        adj[node_id] = {"out": [], "in": []}


def _adj_add_edge(edge: KnowledgeEdge) -> None:
    inst = edge.instance_id
    adj = _adj_for(inst)
    _ensure_adj(edge.source_node_id, inst)
    _ensure_adj(edge.target_node_id, inst)
    out_entry = (edge.id, edge.target_node_id, edge.relationship, edge.weight)
    in_entry = (edge.id, edge.source_node_id, edge.relationship, edge.weight)
    if out_entry not in adj[edge.source_node_id]["out"]:
        adj[edge.source_node_id]["out"].append(out_entry)
    if in_entry not in adj[edge.target_node_id]["in"]:
        adj[edge.target_node_id]["in"].append(in_entry)


def _adj_remove_edge(edge_id: str, source_id: str, target_id: str, instance_id: str) -> None:
    adj = _adj_for(instance_id)
    if source_id in adj:
        adj[source_id]["out"] = [
            e for e in adj[source_id]["out"] if e[0] != edge_id
        ]
    if target_id in adj:
        adj[target_id]["in"] = [
            e for e in adj[target_id]["in"] if e[0] != edge_id
        ]


def _cache_node(node: KnowledgeNode) -> None:
    cache = _cache_for(node.instance_id)
    cache[node.id] = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "description": node.description,
        "instance_id": node.instance_id,
    }


def _get_chroma_collection(chroma_client):
    """Get (or create) the single shared 'knowledge_nodes' collection.
    Only used when VECTOR_BACKEND=chromadb; pgvector uses the SQL table instead."""
    return chroma_client.get_or_create_collection(
        name="knowledge_nodes",
        metadata={"description": "Pulse knowledge graph nodes — all instances"},
    )


# ── BM25 lazy singleton ──────────────────────────────────────────────────────

_bm25_instance = None


def _get_bm25():
    """Lazy-load the BM25 index singleton."""
    global _bm25_instance
    if _bm25_instance is None:
        from ai.engine.knowledge_graph.bm25 import BM25Index
        _bm25_instance = BM25Index()
    return _bm25_instance


# ── Store class ───────────────────────────────────────────────────────────────

class KnowledgeGraphStore:
    """
    Unified interface for the Pulse knowledge graph.

    One instance is created per request (receiving the request's Store session),
    but all instances share the module-level in-memory graph.
    """

    def __init__(
        self,
        db_session,
        chroma_client=None,
    ):
        self.db = db_session
        # Phase 2b-3b: the vector store is optional. If the configured backend
        # is unavailable (e.g. chromadb not installed), degrade to ``None`` and
        # let semantic search return [] — fail-visible, never a fabricated hit.
        self._vector = None
        try:
            from ai.engine.knowledge.vector_store import get_vector_store
            self._vector = get_vector_store(db_session)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Vector store unavailable; semantic search degraded: %s", exc
            )

    # ── Node operations ───────────────────────────────────────────────────────

    async def add_node(self, node_data: dict) -> KnowledgeNode:
        """
        Validate, insert into PostgreSQL, index in ChromaDB, update in-memory graph.
        Returns the created KnowledgeNode.
        """
        node_type = node_data.get("node_type", "ENTITY")
        if node_type not in NODE_TYPES:
            raise ValueError(f"Invalid node_type '{node_type}'. Must be one of {sorted(NODE_TYPES)}")

        source = node_data.get("source", "SCHEMA")
        if source not in SOURCE_TYPES:
            raise ValueError(f"Invalid source '{source}'. Must be one of {sorted(SOURCE_TYPES)}")

        node = KnowledgeNode(
            id=node_data.get("id") or str(uuid4()),
            instance_id=node_data["instance_id"],
            node_type=node_type,
            name=node_data["name"],
            description=node_data.get("description", ""),
            properties=json.dumps(node_data.get("properties", {})),
            source=source,
            confidence=node_data.get("confidence", 0.8),
            verified=node_data.get("verified", False),
            verification_date=node_data.get("verification_date"),
            module_id=node_data.get("module_id"),
        )
        self.db.add(node)
        await self.db.commit()

        # Index in vector store
        doc_text = f"{node.node_type} {node.name}: {node.description}"
        try:
            await self._vector.upsert(
                collection="knowledge_nodes",
                ids=[node.id],
                documents=[doc_text],
                metadatas=[{
                    "node_type": node.node_type,
                    "name": node.name,
                    "instance_id": node.instance_id,
                    "host_user_id": node_data.get("host_user_id") or "",
                }],
                instance_id=node.instance_id,
            )
        except Exception as exc:
            logger.warning(f"Vector store upsert failed for node {node.id}: {exc}")

        _cache_node(node)
        _ensure_adj(node.id, node.instance_id)

        # BE-02-2: Sync BM25 index
        try:
            bm25 = _get_bm25()
            await bm25.index_node(self.db, node)
        except Exception as exc:
            logger.warning(f"BM25 index_node failed for {node.id}: {exc}")

        return node

    async def upsert_node(self, name: str, instance_id: str, node_type: str,
                          description: str = "", properties: dict | None = None,
                          labels: list[str] | None = None,
                          ) -> KnowledgeNode:
        """Insert or update a KnowledgeNode by exact name match.

        BE-02-2: Dedup strategy —
        1. Exact name match in same instance → update existing node
        2. Near-match (vector cosine > 0.90) → log for review, treat as new
        3. No match → create new node

        Returns the existing (updated) or new node.
        """
        # ── Step 1: Exact name match ────────────────────────────────────────
        existing = first(
            await self.db.select(
                KnowledgeNode, ("name", name), ("instance_id", instance_id)
            )
        )
        if existing is not None:
            logger.debug("upsert_node: exact match %s, updating", name)
            updates = {}
            if description:
                updates["description"] = description
            if properties:
                existing_props = existing.properties
                if isinstance(existing_props, str):
                    existing_props = json.loads(existing_props) if existing_props else {}
                merged = dict(existing_props)
                merged.update(properties)
                updates["properties"] = json.dumps(merged)
            if labels:
                # No dedicated ``labels`` column on the Django model — store
                # merged labels inside the properties JSON blob instead.
                existing_props = existing.properties
                if isinstance(existing_props, str):
                    existing_props = json.loads(existing_props) if existing_props else {}
                merged = dict(existing_props)
                existing_labels = merged.get("labels") or []
                if isinstance(existing_labels, str):
                    existing_labels = json.loads(existing_labels) if existing_labels else []
                merged["labels"] = json.dumps(list(set(existing_labels) | set(labels)))
                updates["properties"] = json.dumps(merged)
            if updates:
                for key, value in updates.items():
                    setattr(existing, key, value)
                existing.updated_at = utcnow()
                await self.db.commit()

                # Sync BM25
                try:
                    bm25 = _get_bm25()
                    await bm25.index_node(self.db, existing)
                except Exception as exc:
                    logger.warning(f"BM25 re-index in upsert failed for {existing.id}: {exc}")

                _cache_node(existing)
            return existing

        # ── Step 2: Near-match via vector ───────────────────────────────────
        if self._vector is not None:
            try:
                results = await self._vector.query(
                    collection="knowledge_nodes",
                    query_texts=[description or name],
                    n_results=3,
                    instance_id=instance_id,
                )
                if results.get("ids") and results["ids"][0]:
                    for i, nid in enumerate(results["ids"][0]):
                        distance = results.get("distances", [[1.0]])[0][i]
                        similarity = 1.0 - distance
                        if similarity > 0.90:
                            near = first(
                                await self.db.select(KnowledgeNode, ("id", nid))
                            )
                            if near:
                                logger.info(
                                    "upsert_node: near-match '%s' (sim=%.3f) with "
                                    "existing '%s'. Creating new node; review advised.",
                                    name, similarity, near.name,
                                )
                            break
            except Exception as exc:
                logger.debug("upsert_node near-match check skipped: %s", exc)

        # ── Step 3: Create new ──────────────────────────────────────────────
        logger.debug("upsert_node: no match for %s, creating new", name)
        return await self.add_node({
            "name": name,
            "instance_id": instance_id,
            "node_type": node_type,
            "description": description,
            "properties": properties or {},
            "labels": labels or [],
        })

    async def update_node(self, node_id: str, updates: dict) -> Optional[KnowledgeNode]:
        """
        Update specified fields in PostgreSQL. Re-indexes in ChromaDB if description changed.
        Returns the updated node, or None if not found.
        """
        result = await self.db.select(KnowledgeNode, ("id", node_id))
        node = first(result)
        if node is None:
            return None

        description_changed = False
        for key, value in updates.items():
            if key == "properties" and isinstance(value, dict):
                value = json.dumps(value)
            if key == "description" and value != node.description:
                description_changed = True
            setattr(node, key, value)

        node.updated_at = utcnow()
        await self.db.commit()

        if description_changed:
            doc_text = f"{node.node_type} {node.name}: {node.description}"
            try:
                await self._vector.upsert(
                    collection="knowledge_nodes",
                    ids=[node_id],
                    documents=[doc_text],
                    metadatas=[{
                        "node_type": node.node_type,
                        "name": node.name,
                        "instance_id": node.instance_id,
                        "host_user_id": "",
                    }],
                    instance_id=node.instance_id,
                )
            except Exception as exc:
                logger.warning(f"Vector store re-index failed for node {node_id}: {exc}")

        _cache_node(node)

        # BE-02-2: Sync BM25 index
        try:
            bm25 = _get_bm25()
            await bm25.index_node(self.db, node)
        except Exception as exc:
            logger.warning(f"BM25 re-index failed for {node_id}: {exc}")

        return node

    async def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """
        Retrieve by ID from PostgreSQL. Updates access stats. Returns None if not found.
        """
        node = first(await self.db.select(KnowledgeNode, ("id", node_id)))
        if node:
            node.last_accessed = utcnow()
            node.access_count = (node.access_count or 0) + 1
            await self.db.commit()
        return node

    async def get_nodes_by_type(
        self, node_type: str, instance_id: str = None
    ) -> list[KnowledgeNode]:
        """Return all nodes of a given type, optionally filtered to one instance."""
        filters: list = [("node_type", node_type)]
        if instance_id:
            filters.append(("instance_id", instance_id))
        return await self.db.select(KnowledgeNode, *filters)

    async def get_nodes_by_module(self, module_id: str) -> list[KnowledgeNode]:
        """Return all nodes belonging to a specific module."""
        return await self.db.select(KnowledgeNode, ("module_id", module_id))

    async def delete_node(self, node_id: str) -> bool:
        """
        Remove node from all three layers, including all connected edges.
        Returns True if the node existed (and was deleted).
        """
        node = first(await self.db.select(KnowledgeNode, ("id", node_id)))
        if node is None:
            return False

        # Remove all edges touching this node
        edges = await self.db.select(
            KnowledgeEdge,
            Q(source_node_id=node_id) | Q(target_node_id=node_id),
        )
        for edge in edges:
            _adj_remove_edge(edge.id, edge.source_node_id, edge.target_node_id, edge.instance_id)
            await self.db.delete(edge)

        await self.db.delete(node)
        await self.db.commit()

        if self._vector is not None:
            try:
                await self._vector.delete(
                    collection="knowledge_nodes",
                    ids=[node_id],
                    instance_id=node.instance_id,
                )
            except Exception:
                pass

        _cache_for(node.instance_id).pop(node_id, None)
        _adj_for(node.instance_id).pop(node_id, None)

        # BE-02-2: Remove from BM25 index
        try:
            bm25 = _get_bm25()
            await bm25.delete_node(self.db, node_id)
        except Exception as exc:
            logger.warning(f"BM25 delete_node failed for {node_id}: {exc}")

        return True

    # ── Edge operations ───────────────────────────────────────────────────────

    async def add_edge(self, edge_data: dict) -> KnowledgeEdge:
        """
        Validate, insert into PostgreSQL, update in-memory graph.
        Raises ValueError if either node doesn't exist or type is invalid.
        """
        relationship = edge_data.get("relationship", "RELATED_TO")
        if relationship not in RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship '{relationship}'")

        source = edge_data.get("source", "SCHEMA")
        if source not in SOURCE_TYPES:
            raise ValueError(f"Invalid source '{source}'")

        # Verify both endpoint nodes exist
        inst = edge_data.get("instance_id", "")
        cache = _cache_for(inst)
        for key in ("source_node_id", "target_node_id"):
            nid = edge_data.get(key)
            if not nid:
                raise ValueError(f"Missing {key}")
            if nid not in cache:
                check = first(await self.db.select(KnowledgeNode, ("id", nid)))
                if check is None:
                    raise ValueError(f"Node '{nid}' not found — cannot create edge")

        edge = KnowledgeEdge(
            id=edge_data.get("id") or str(uuid4()),
            instance_id=edge_data["instance_id"],
            source_node_id=edge_data["source_node_id"],
            target_node_id=edge_data["target_node_id"],
            relationship=relationship,
            properties=json.dumps(edge_data.get("properties", {})),
            confidence=edge_data.get("confidence", 1.0),
            source=source,
            weight=edge_data.get("weight", 1.0),
            valid_from=edge_data.get("valid_from"),
            valid_to=edge_data.get("valid_to"),
        )
        self.db.add(edge)
        await self.db.commit()
        _adj_add_edge(edge)
        return edge

    async def query_edges(
        self,
        instance_id: str,
        source_node_id: str = None,
        target_node_id: str = None,
        relationship: str = None,
        as_of: datetime | None = None,
    ) -> list[dict]:
        """Query edges with optional bi-temporal as_of filtering.

        When as_of is set, returns edges that were valid at that point in time:
        valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of).

        When as_of is None, only returns currently-valid (non-expired) edges:
        valid_to IS NULL.
        """
        filters: list = [("instance_id", instance_id)]
        if source_node_id:
            filters.append(("source_node_id", source_node_id))
        if target_node_id:
            filters.append(("target_node_id", target_node_id))
        if relationship:
            filters.append(("relationship", relationship))

        if as_of is not None:
            filters.append(
                Q(valid_from__lte=as_of)
                & (Q(valid_to__isnull=True) | Q(valid_to__gt=as_of))
            )
        else:
            filters.append(("valid_to__isnull", True))

        return await self.db.select(KnowledgeEdge, *filters)

    async def update_edge(self, edge_id: str, updates: dict) -> Optional[KnowledgeEdge]:
        """
        Bi-temporal edge update: expires the existing edge (sets valid_to = now())
        and inserts a new edge row with the updated values and valid_from = now().

        This preserves the full version history of every fact.
        For simple in-place updates (e.g., confidence tweaks), use the
        `source_node_id`, `target_node_id`, `relationship` keys to identify
        the subject+predicate pair for the new version.
        """
        now = utcnow()
        edge = first(await self.db.select(KnowledgeEdge, ("id", edge_id)))
        if edge is None:
            return None

        # Expire the existing edge
        if edge.valid_to is None:
            edge.valid_to = now
            edge.updated_at = now

        # Create a new edge row with updated values
        new_edge = KnowledgeEdge(
            id=str(uuid4()),
            instance_id=updates.get("instance_id", edge.instance_id),
            source_node_id=updates.get("source_node_id", edge.source_node_id),
            target_node_id=updates.get("target_node_id", edge.target_node_id),
            relationship=updates.get("relationship", edge.relationship),
            properties=updates.get("properties", edge.properties)
            if isinstance(updates.get("properties"), str)
            else json.dumps(updates.get("properties", {})),
            confidence=updates.get("confidence", edge.confidence),
            source=updates.get("source", edge.source),
            weight=updates.get("weight", edge.weight),
            valid_from=now,
            valid_to=None,
        )
        self.db.add(new_edge)
        await self.db.commit()
        _adj_add_edge(new_edge)
        return new_edge

    async def get_fact_history(
        self, instance_id: str, source_node_id: str, relationship: str
    ) -> list[KnowledgeEdge]:
        """Return all versions of a fact (subject+predicate), ordered by valid_from."""
        rows = await self.db.select(
            KnowledgeEdge,
            ("instance_id", instance_id),
            ("source_node_id", source_node_id),
            ("relationship", relationship),
        )
        rows.sort(key=lambda e: e.valid_from or datetime.min)
        return rows

    async def delete_edge(self, edge_id: str) -> bool:
        """Remove edge from PostgreSQL and in-memory graph. Returns True if it existed."""
        edge = first(await self.db.select(KnowledgeEdge, ("id", edge_id)))
        if edge is None:
            return False

        _adj_remove_edge(edge.id, edge.source_node_id, edge.target_node_id, edge.instance_id)
        await self.db.delete(edge)
        await self.db.commit()
        return True

    async def get_edges_from(
        self, node_id: str, relationship: str = None
    ) -> list[KnowledgeEdge]:
        """Get all outgoing edges from a node, optionally filtered by relationship type."""
        filters: list = [("source_node_id", node_id)]
        if relationship:
            filters.append(("relationship", relationship))
        return await self.db.select(KnowledgeEdge, *filters)

    async def get_edges_to(
        self, node_id: str, relationship: str = None
    ) -> list[KnowledgeEdge]:
        """Get all incoming edges to a node, optionally filtered by relationship type."""
        filters: list = [("target_node_id", node_id)]
        if relationship:
            filters.append(("relationship", relationship))
        return await self.db.select(KnowledgeEdge, *filters)

    # ── Graph traversal ───────────────────────────────────────────────────────

    def get_neighbors(
        self,
        node_id: str,
        instance_id: str,
        depth: int = 1,
        relationship_types: list[str] = None,
    ) -> dict:
        """
        BFS on the in-memory adjacency list. Returns a subgraph dict:
            {"nodes": [cache_dicts], "edges": [edge_dicts]}

        Does NOT query PostgreSQL — uses the in-memory adjacency list and node cache.
        Call load_graph() at startup to populate them.
        """
        adj = _adj_for(instance_id)
        cache = _cache_for(instance_id)
        if node_id not in adj:
            return {"nodes": [], "edges": []}

        visited_nodes: set[str] = {node_id}
        visited_edges: set[str] = set()
        queue: deque = deque([(node_id, 0)])
        result_nodes: list[dict] = []
        result_edges: list[dict] = []

        while queue:
            current_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            for edge_id, neighbor_id, rel, weight in adj.get(current_id, {}).get("out", []):
                if relationship_types and rel not in relationship_types:
                    continue
                if edge_id not in visited_edges:
                    visited_edges.add(edge_id)
                    result_edges.append({
                        "id": edge_id,
                        "source": current_id,
                        "target": neighbor_id,
                        "relationship": rel,
                        "weight": weight,
                    })
                if neighbor_id not in visited_nodes:
                    visited_nodes.add(neighbor_id)
                    if neighbor_id in cache:
                        result_nodes.append(cache[neighbor_id])
                    queue.append((neighbor_id, current_depth + 1))

        return {"nodes": result_nodes, "edges": result_edges}

    # ── Semantic search ───────────────────────────────────────────────────────

    async def semantic_search(
        self,
        query: str,
        instance_id: str,
        top_k: int = 10,
        node_types: list[str] = None,
    ) -> list[KnowledgeNode]:
        """
        Vector similarity search → fetch full nodes from PostgreSQL.
        Routes through self._vector (pgvector or ChromaDB) — NOT self._collection.
        If node_types is provided, filters results to those types.
        """
        where_clause: dict = {"instance_id": instance_id}
        post_filter_types: list[str] | None = None
        if node_types:
            if len(node_types) == 1:
                where_clause["node_type"] = node_types[0]
            else:
                # $in filter — not expressible by pgvector; fetch superset, filter in Python
                post_filter_types = [t.lower() for t in node_types]

        # Fetch more results when we need to post-filter (compensate for pruning)
        fetch_k = top_k * 3 if post_filter_types else top_k

        if self._vector is None:
            # Vector backend unavailable — fail-visible, never a fabricated hit.
            logger.debug(
                "semantic_search skipped for %s: vector store unavailable",
                instance_id,
            )
            return []

        try:
            results = await self._vector.query(
                collection="knowledge_nodes",
                query_texts=[query],
                n_results=fetch_k,
                where=where_clause,
                instance_id=instance_id,
            )
        except Exception as exc:
            logger.error(
                f"Vector semantic_search failed (instance={instance_id}, query={query[:60]!r}): {exc}",
                exc_info=True,
            )
            return []

        if not results.get("ids") or not results["ids"][0]:
            return []

        nodes: list[KnowledgeNode] = []
        for nid in results["ids"][0]:
            node = first(await self.db.select(KnowledgeNode, ("id", nid)))
            if node:
                # Apply $in post-filter when backend cannot express it
                if post_filter_types and node.node_type.lower() not in post_filter_types:
                    continue
                nodes.append(node)
                if len(nodes) >= top_k:
                    break

        return nodes

    async def get_subgraph_for_nodes(
        self,
        node_ids: list[str],
        include_edges: bool = True,
    ) -> dict:
        """
        Fetch the given nodes and all edges between them.
        Useful for serializing context after semantic search identifies seed nodes.
        """
        nodes: list[KnowledgeNode] = []
        for nid in node_ids:
            node = first(await self.db.select(KnowledgeNode, ("id", nid)))
            if node:
                nodes.append(node)

        edges: list[KnowledgeEdge] = []
        if include_edges and len(node_ids) > 1:
            edges = await self.db.select(
                KnowledgeEdge,
                Q(source_node_id__in=node_ids) & Q(target_node_id__in=node_ids),
            )

        return {"nodes": nodes, "edges": edges}

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_stats(self, instance_id: str = None) -> dict:
        """
        Returns counts: nodes by type, edges by relationship, unverified, low-confidence.
        Used by Studio dashboard and health checks.
        """
        filters: list = [("instance_id", instance_id)] if instance_id else []

        nodes = await self.db.select(KnowledgeNode, *filters)
        nodes_by_type: dict[str, int] = {}
        unverified = 0
        low_confidence = 0
        for node in nodes:
            nodes_by_type[node.node_type] = nodes_by_type.get(node.node_type, 0) + 1
            if not node.verified:
                unverified += 1
            if (node.confidence or 0) < 0.5:
                low_confidence += 1

        edges = await self.db.select(KnowledgeEdge, *filters)
        edges_by_rel: dict[str, int] = {}
        for edge in edges:
            edges_by_rel[edge.relationship] = edges_by_rel.get(edge.relationship, 0) + 1

        return {
            "nodes_by_type": nodes_by_type,
            "edges_by_relationship": edges_by_rel,
            "total_nodes": sum(nodes_by_type.values()),
            "total_edges": sum(edges_by_rel.values()),
            "unverified": unverified,
            "low_confidence": low_confidence,
            "in_memory_nodes": len(_cache_for(instance_id or "")),
            "in_memory_edges": sum(
                len(v["out"]) for v in _adj_for(instance_id or "").values()
            ),
        }

    # ── Graph loading ─────────────────────────────────────────────────────────

    async def load_graph(self, instance_id: str = None) -> None:
        """
        Read all nodes and edges from PostgreSQL and populate the per-instance
        in-memory graph. Must be called once at startup (in main.py lifespan).
        """
        filters: list = [("instance_id", instance_id)] if instance_id else []
        nodes = await self.db.select(KnowledgeNode, *filters)
        for node in nodes:
            _cache_node(node)
            _ensure_adj(node.id, node.instance_id)

        edges = await self.db.select(KnowledgeEdge, *filters)
        for edge in edges:
            _adj_add_edge(edge)

        if instance_id:
            _set_loaded(instance_id)
        logger.info(
            f"Knowledge graph loaded into memory: {len(nodes)} nodes, {len(edges)} edges"
        )

    async def rebuild_embeddings(self, instance_id: str = None) -> None:
        """
        Regenerate all vector embeddings from node descriptions.
        Routes through self._vector — NOT self._collection.
        Used as a repair / maintenance operation from Studio.
        """
        if self._vector is None:
            logger.warning("rebuild_embeddings skipped: vector store unavailable")
            return

        filters: list = [("instance_id", instance_id)] if instance_id else []
        nodes = await self.db.select(KnowledgeNode, *filters)

        for node in nodes:
            doc_text = f"{node.node_type} {node.name}: {node.description}"
            try:
                await self._vector.upsert(
                    collection="knowledge_nodes",
                    ids=[node.id],
                    documents=[doc_text],
                    metadatas=[{
                        "node_type": node.node_type,
                        "name": node.name,
                        "instance_id": node.instance_id,
                        "host_user_id": "",
                    }],
                    instance_id=node.instance_id,
                )
            except Exception as exc:
                logger.error(
                    f"rebuild_embeddings: failed for node {node.id}: {exc}",
                    exc_info=True,
                )

        logger.info(f"Rebuilt embeddings for {len(nodes)} knowledge nodes")

    # ── Data profiling ────────────────────────────────────────────────────────

    async def store_table_profile(self, node_id: str, table_profile) -> None:
        """
        Merge a TableProfile into the node's properties JSON blob.

        Stores per-table stats under the following keys (all added/replaced):
          profiled_at, row_count_actual, column_profiles

        The ``table_profile`` argument is a ``TableProfile`` dataclass from
        knowledge_graph.data_profiler.
        """
        node = await self.get_node(node_id)
        if node is None:
            logger.warning(f"store_table_profile: node {node_id} not found")
            return

        existing: dict = {}
        if node.properties:
            try:
                existing = json.loads(node.properties)
            except json.JSONDecodeError:
                existing = {}

        # Serialize column profiles to plain dicts
        col_profiles_serialized = []
        for cp in table_profile.columns:
            col_profiles_serialized.append({
                "column_name": cp.column_name,
                "data_type": cp.data_type,
                "row_count": cp.row_count,
                "null_count": cp.null_count,
                "null_rate": cp.null_rate,
                "distinct_count": cp.distinct_count,
                "min_value": cp.min_value,
                "max_value": cp.max_value,
                "value_list": cp.value_list,
                "is_pii": cp.is_pii,
            })

        existing["profiled_at"] = table_profile.profiled_at
        existing["row_count_actual"] = table_profile.row_count
        existing["column_profiles"] = col_profiles_serialized

        await self.update_node(node_id, {"properties": existing})

    async def get_entity_profile(self, entity_name: str, instance_id: str) -> dict | None:
        """
        Return the profile section of an ENTITY node's properties, or None if
        the node doesn't exist or hasn't been profiled yet.

        Returns a dict with keys: row_count_actual, profiled_at, column_profiles.
        """
        node = first(
            await self.db.select(
                KnowledgeNode,
                ("instance_id", instance_id),
                ("node_type", "ENTITY"),
                ("name", entity_name),
            )
        )
        if node is None or not node.properties:
            return None

        try:
            props = json.loads(node.properties)
        except json.JSONDecodeError:
            return None

        if "profiled_at" not in props:
            return None

        return {
            "row_count_actual": props.get("row_count_actual", 0),
            "profiled_at": props.get("profiled_at"),
            "column_profiles": props.get("column_profiles", []),
        }

    async def get_column_values(
        self, entity_name: str, column_name: str, instance_id: str
    ) -> dict | None:
        """
        Return profile statistics for a specific column of an entity, or None
        if no profile exists or the column was not found in the profile.

        Returns a dict with keys: value_list, min_value, max_value,
        null_rate, distinct_count, is_pii.
        """
        profile = await self.get_entity_profile(entity_name, instance_id)
        if profile is None:
            return None

        col_lower = column_name.lower()
        for cp in profile.get("column_profiles", []):
            if cp.get("column_name", "").lower() == col_lower:
                return {
                    "value_list": cp.get("value_list", []),
                    "min_value": cp.get("min_value"),
                    "max_value": cp.get("max_value"),
                    "null_rate": cp.get("null_rate", 0.0),
                    "distinct_count": cp.get("distinct_count"),
                    "is_pii": cp.get("is_pii", False),
                }
        return None

    # ── Compatibility with KnowledgeStore interface ───────────────────────────
    # These two methods match the KnowledgeStore.search() / get_entity() signatures
    # so existing agent/tools.py callers keep working without modification.

    async def search(
        self, instance_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """
        Drop-in replacement for KnowledgeStore.search().
        Returns dicts in the same format so tools.py keeps working.
        """
        nodes = await self.semantic_search(query, instance_id, top_k=top_k)
        return [
            {
                "id": n.id,
                "name": n.name,
                "entity_type": n.node_type,
                "semantic_description": n.description,
                "schema_json": n.properties,
                "relationships": None,
            }
            for n in nodes
        ]

    async def get_entity(self, instance_id: str, name: str) -> Optional[dict]:
        """Drop-in replacement for KnowledgeStore.get_entity()."""
        node = first(
            await self.db.select(
                KnowledgeNode, ("instance_id", instance_id), ("name", name)
            )
        )
        if node is None:
            return None
        return {
            "id": node.id,
            "name": node.name,
            "entity_type": node.node_type,
            "semantic_description": node.description,
            "schema_json": node.properties,
            "relationships": None,
        }


# ── Standalone startup helper ─────────────────────────────────────────────────

async def load_knowledge_graph() -> None:
    """
    Called from main.py lifespan. Opens its own session and populates
    the module-level in-memory graph from PostgreSQL.
    """
    from ai.engine.core.database import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        store = KnowledgeGraphStore(session)
        await store.load_graph()
