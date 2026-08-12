"""
One-time (idempotent) migration from KnowledgeEntity records into the knowledge graph.

Converts existing flat KnowledgeEntity records into a proper graph structure:
  - One ENTITY node per database table
  - One ATTRIBUTE node per column, linked by HAS_ATTRIBUTE edges
  - DEPENDS_ON edges for foreign-key relationships (ground truth, confidence=1.0)

Run this after every bootstrap / re-introspect so the graph stays in sync
with the latest KnowledgeEntity data. The function is idempotent: running it
twice produces the same result (existing nodes are skipped, not duplicated).
"""
import json
import logging
from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, or_, select

from ai.engine.knowledge_graph.models import KnowledgeEdge, KnowledgeNode
from ai.engine.knowledge_graph.store import (
    KnowledgeGraphStore,
    _adj_add_edge,
    _adj_remove_edge,
    _adjacency,
    _cache_node,
    _ensure_adj,
    _node_cache,
)

logger = logging.getLogger("pulse.knowledge_graph.migration")


async def _bulk_clear_instance(store: KnowledgeGraphStore, instance_id: str) -> None:
    """
    Drop ALL nodes and edges for an instance in two bulk SQL statements.
    Also cleans the in-memory adjacency/cache. Much faster than delete_node() per node.
    """
    # Collect node IDs so we can purge in-memory structures
    id_rows = await store.db.execute(
        select(KnowledgeNode.id).where(KnowledgeNode.instance_id == instance_id)
    )
    node_ids = [r[0] for r in id_rows.fetchall()]

    if not node_ids:
        return

    # Bulk delete edges (both directions) and nodes
    await store.db.execute(
        delete(KnowledgeEdge).where(
            or_(
                KnowledgeEdge.source_node_id.in_(node_ids),
                KnowledgeEdge.target_node_id.in_(node_ids),
            )
        )
    )
    await store.db.execute(
        delete(KnowledgeNode).where(KnowledgeNode.instance_id == instance_id)
    )
    await store.db.commit()

    # Purge vector store
    try:
        await store._vector.delete(
            collection="knowledge_nodes",
            ids=node_ids,
            instance_id=instance_id,
        )
    except Exception:
        pass

    # Purge in-memory structures
    for nid in node_ids:
        _node_cache.pop(nid, None)
        _adjacency.pop(nid, None)


async def migrate_knowledge_entities(
    store: KnowledgeGraphStore,
    existing_entities: list,          # list of KnowledgeEntity ORM objects
    instance_id: str,
    force: bool = False,
    schema_graph=None,                # optional knowledge.schema_graph.SchemaGraph
) -> dict:
    """
    Convert KnowledgeEntity records → KnowledgeNode + KnowledgeEdge graph.

    Parameters
    ----------
    store:
        KnowledgeGraphStore to write into.
    existing_entities:
        List of KnowledgeEntity ORM objects (all for this instance).
    instance_id:
        The Pulse instance ID these entities belong to.
    force:
        If True, wipe existing graph nodes for this instance and rebuild from scratch.
        If False (default), skip if ENTITY nodes already exist.
    schema_graph:
        Optional SchemaGraph dataclass from the introspector. When provided, FK
        edges are created with full column-level details and confidence=1.0.
        When absent, FK edges are inferred from entity.relationships (table names only).

    Returns
    -------
    dict with: nodes_created, edges_created, entities_migrated,
               attributes_created, fk_edges_created
    """
    counts = {
        "nodes_created": 0,
        "edges_created": 0,
        "entities_migrated": 0,
        "attributes_created": 0,
        "fk_edges_created": 0,
    }

    # ── Idempotency guard ─────────────────────────────────────────────────────
    existing_entity_nodes = await store.get_nodes_by_type("ENTITY", instance_id)

    if existing_entity_nodes and not force:
        logger.info(
            f"Knowledge graph already contains {len(existing_entity_nodes)} ENTITY nodes "
            f"for instance {instance_id}. Skipping migration (use force=True to rebuild)."
        )
        return counts

    if existing_entity_nodes and force:
        logger.info(
            f"force=True: clearing {len(existing_entity_nodes)} existing ENTITY nodes "
            f"and all their edges for instance {instance_id}."
        )
        await _bulk_clear_instance(store, instance_id)

    if not existing_entities:
        logger.warning(f"No KnowledgeEntity records found for instance {instance_id}. Nothing to migrate.")
        return counts

    logger.info(
        f"Migrating {len(existing_entities)} KnowledgeEntity records → knowledge graph "
        f"for instance {instance_id}"
    )

    # ── Build FK lookup from SchemaGraph (if available) ───────────────────────
    # Maps (source_table, source_column) → Relationship dataclass
    fk_lookup: dict[tuple[str, str], object] = {}
    if schema_graph is not None:
        for rel in schema_graph.relationships:
            fk_lookup[(rel.source_table, rel.source_column)] = rel

    # ── Step 1 & 2: ENTITY nodes + ATTRIBUTE nodes + HAS_ATTRIBUTE edges ──────
    # Build all ORM objects in memory first, then bulk-insert with a single commit.
    entity_node_map: dict[str, str] = {}  # table_name → KnowledgeNode.id
    all_new_nodes: list[KnowledgeNode] = []
    all_new_edges: list[KnowledgeEdge] = []

    for entity in existing_entities:
        schema_data = {}
        if entity.schema_json:
            try:
                schema_data = json.loads(entity.schema_json)
            except (json.JSONDecodeError, TypeError):
                schema_data = {}

        columns = schema_data.get("columns", [])
        row_count = schema_data.get("row_count", 0)
        primary_keys = schema_data.get("primary_keys", [])

        # Build ENTITY node (no DB write yet)
        entity_node_id = str(uuid4())
        entity_node = KnowledgeNode(
            id=entity_node_id,
            instance_id=instance_id,
            node_type="ENTITY",
            name=entity.name,
            description=entity.semantic_description or f"Database table: {entity.name}",
            properties=json.dumps({
                "table_name": entity.name,
                "row_count": row_count,
                "schema": "public",
            }),
            source="SCHEMA",
            confidence=0.8,
            verified=False,
        )
        entity_node_map[entity.name] = entity_node_id
        all_new_nodes.append(entity_node)
        counts["nodes_created"] += 1
        counts["entities_migrated"] += 1

        # Build ATTRIBUTE nodes + HAS_ATTRIBUTE edges
        for col in columns:
            col_name = col.get("name", "")
            col_type = col.get("type", "unknown")
            col_nullable = col.get("nullable", True)
            is_pk = col.get("is_primary_key", col_name in primary_keys)
            is_fk = col.get("is_foreign_key", False)
            fk_target_table = col.get("fk_target_table")
            fk_target_col = col.get("fk_target_column")
            col_default = col.get("default")

            desc_parts = [
                f"Column {col_name} in table {entity.name}.",
                f"Type: {col_type}.",
                "Nullable." if col_nullable else "Not null.",
            ]
            if is_pk:
                desc_parts.append("Primary key.")
            if is_fk and fk_target_table:
                desc_parts.append(f"Foreign key referencing {fk_target_table}.{fk_target_col or 'id'}.")

            attr_node_id = str(uuid4())
            attr_node = KnowledgeNode(
                id=attr_node_id,
                instance_id=instance_id,
                node_type="ATTRIBUTE",
                name=f"{entity.name}.{col_name}",
                description=" ".join(desc_parts),
                properties=json.dumps({
                    "column_name": col_name,
                    "data_type": col_type,
                    "nullable": col_nullable,
                    "is_primary_key": is_pk,
                    "is_foreign_key": is_fk,
                    "fk_target_table": fk_target_table,
                    "fk_target_column": fk_target_col,
                    "default": col_default,
                }),
                source="SCHEMA",
                confidence=0.8,
                verified=False,
            )
            all_new_nodes.append(attr_node)
            counts["nodes_created"] += 1
            counts["attributes_created"] += 1

            # HAS_ATTRIBUTE edge
            all_new_edges.append(KnowledgeEdge(
                id=str(uuid4()),
                instance_id=instance_id,
                source_node_id=entity_node_id,
                target_node_id=attr_node_id,
                relationship="HAS_ATTRIBUTE",
                properties=json.dumps({}),
                confidence=1.0,
                source="SCHEMA",
                weight=1.0,
            ))
            counts["edges_created"] += 1

    # ── Step 3: DEPENDS_ON edges for FK relationships ─────────────────────────
    if schema_graph is not None:
        for rel in schema_graph.relationships:
            src_id = entity_node_map.get(rel.source_table)
            tgt_id = entity_node_map.get(rel.target_table)
            if not (src_id and tgt_id):
                continue
            all_new_edges.append(KnowledgeEdge(
                id=str(uuid4()),
                instance_id=instance_id,
                source_node_id=src_id,
                target_node_id=tgt_id,
                relationship="DEPENDS_ON",
                properties=json.dumps({
                    "fk_column": rel.source_column,
                    "referenced_column": rel.target_column,
                    "constraint_name": getattr(rel, "constraint_name", None),
                }),
                confidence=1.0,
                source="SCHEMA",
                weight=1.5,
            ))
            counts["edges_created"] += 1
            counts["fk_edges_created"] += 1
    else:
        # Fallback: RELATED_TO edges from entity.relationships
        for entity in existing_entities:
            src_id = entity_node_map.get(entity.name)
            if not src_id:
                continue
            related_tables: list[str] = []
            if entity.relationships:
                try:
                    related_tables = json.loads(entity.relationships)
                except (json.JSONDecodeError, TypeError):
                    related_tables = []
            seen = set()
            for related_name in related_tables:
                tgt_id = entity_node_map.get(related_name)
                if not tgt_id or (src_id, tgt_id) in seen:
                    continue
                seen.add((src_id, tgt_id))
                all_new_edges.append(KnowledgeEdge(
                    id=str(uuid4()),
                    instance_id=instance_id,
                    source_node_id=src_id,
                    target_node_id=tgt_id,
                    relationship="RELATED_TO",
                    properties=json.dumps({}),
                    confidence=0.9,
                    source="SCHEMA",
                    weight=1.2,
                ))
                counts["edges_created"] += 1
                counts["fk_edges_created"] += 1

    # ── Bulk insert all nodes + edges in one commit ───────────────────────────
    store.db.add_all(all_new_nodes)
    store.db.add_all(all_new_edges)
    await store.db.commit()

    # ── Rebuild in-memory graph and vector store index ────────────────────────
    vector_ids, vector_docs, vector_metas = [], [], []
    for node in all_new_nodes:
        _cache_node(node)
        _ensure_adj(node.id)
        vector_ids.append(node.id)
        vector_docs.append(f"{node.node_type} {node.name}: {node.description}")
        vector_metas.append({
            "node_type": node.node_type,
            "name": node.name,
            "instance_id": node.instance_id,
        })

    for edge in all_new_edges:
        _adj_add_edge(edge)

    # Vector store batch upsert (up to 500 at a time)
    batch_size = 500
    for i in range(0, len(vector_ids), batch_size):
        try:
            await store._vector.upsert(
                collection="knowledge_nodes",
                ids=vector_ids[i:i + batch_size],
                documents=vector_docs[i:i + batch_size],
                metadatas=vector_metas[i:i + batch_size],
                instance_id=instance_id,
            )
        except Exception as exc:
            logger.warning(f"Vector store batch upsert failed (offset {i}): {exc}")

    logger.info(
        f"Migration complete for instance {instance_id}: "
        f"{counts['entities_migrated']} entities, "
        f"{counts['attributes_created']} attributes, "
        f"{counts['fk_edges_created']} FK edges, "
        f"{counts['nodes_created']} total nodes, "
        f"{counts['edges_created']} total edges."
    )
    return counts
