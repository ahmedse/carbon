"""
JoinPathFinder — computes shortest join paths between ENTITY nodes.

Traverses DEPENDS_ON (FK relationships) and RELATED_TO (inferred relationships)
edges using BFS on the module-level in-memory adjacency list. Edge properties
(join columns) are resolved from PostgreSQL on demand.

Key design decisions:
- BFS on _adjacency (sync, fast) to find the path structure.
- One batched async DB call after BFS to resolve edge properties for the
  steps in the chosen path. This keeps BFS cheap while giving rich metadata.
- Both directions are traversed: A→B means "A has FK to B", B→A means
  "B is referenced by A". direction field tells the SQL generator which side
  owns the join column.
"""
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ai.models.knowledge_graph import KnowledgeEdge, KnowledgeNode
from ai.store import first

if TYPE_CHECKING:
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

logger = logging.getLogger("pulse.knowledge_graph.path_finder")


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class JoinStep:
    from_entity: str
    from_column: str
    to_entity: str
    to_column: str
    join_type: str      # "fk" | "inferred"
    confidence: float   # 1.0 for FK, edge confidence for inferred
    direction: str      # "outgoing" | "incoming" — which side owns the FK


@dataclass
class JoinPath:
    steps: list[JoinStep] = field(default_factory=list)
    total_confidence: float = 1.0
    hop_count: int = 0


@dataclass
class MultiEntityPlan:
    paths: list[JoinPath] = field(default_factory=list)
    anchor_entity: str = ""
    unreachable: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _node_name_from_cache(node_id: str) -> Optional[str]:
    """Look up a node's name from the module-level cache without DB access."""
    from ai.engine.knowledge_graph.store import _node_cache
    cached = _node_cache.get(node_id)
    return cached["name"] if cached else None


def _entity_id_by_name(name: str, instance_id: str) -> Optional[str]:
    """Find an ENTITY node id by exact name (case-insensitive) from the in-memory cache."""
    from ai.engine.knowledge_graph.store import _node_cache
    for nid, cached in _node_cache.items():
        if (
            cached["node_type"] == "ENTITY"
            and cached["instance_id"] == instance_id
            and cached["name"].lower() == name.lower()
        ):
            return nid
    return None


def _entity_node_ids(instance_id: str) -> set[str]:
    """Return all ENTITY node ids for this instance from the in-memory cache."""
    from ai.engine.knowledge_graph.store import _node_cache
    return {
        nid for nid, cached in _node_cache.items()
        if cached["node_type"] == "ENTITY" and cached["instance_id"] == instance_id
    }


# ── JoinPathFinder ────────────────────────────────────────────────────────────

class JoinPathFinder:
    """
    Computes join paths between ENTITY nodes using the knowledge graph.

    The BFS itself is sync (in-memory adjacency). Edge property resolution
    (join columns) is async (SQLite).
    """

    def __init__(self, store: "KnowledgeGraphStore"):
        self.store = store

    # ── Public API ────────────────────────────────────────────────────────────

    async def find_join_path(
        self,
        source_entity: str,
        target_entity: str,
        instance_id: str,
    ) -> Optional[JoinPath]:
        """
        Find the shortest join path between two entities.
        Returns None if no path exists or either entity is not in the graph.
        """
        from ai.engine.knowledge_graph.store import _adjacency, _node_cache

        src_id = _entity_id_by_name(source_entity, instance_id)
        tgt_id = _entity_id_by_name(target_entity, instance_id)

        if not src_id or not tgt_id:
            logger.debug(
                f"find_join_path: entity not found  src={source_entity!r}  tgt={target_entity!r}"
            )
            return None

        if src_id == tgt_id:
            return JoinPath(steps=[], total_confidence=1.0, hop_count=0)

        entity_ids = _entity_node_ids(instance_id)

        # BFS — each state: (current_node_id, path_so_far)
        # path_so_far is a list of (edge_id, from_node_id, to_node_id, relationship, direction)
        visited: set[str] = {src_id}
        queue: deque = deque([(src_id, [])])

        raw_path: list[tuple] = []  # filled when target is found

        while queue:
            current_id, path = queue.popleft()

            adj = _adjacency.get(current_id, {})

            # Outgoing edges (current → neighbor)
            for edge_id, neighbor_id, rel, weight in adj.get("out", []):
                if rel not in ("DEPENDS_ON", "RELATED_TO"):
                    continue
                # Only traverse through ENTITY nodes (not ATTRIBUTE etc.)
                if neighbor_id not in entity_ids and neighbor_id != tgt_id:
                    continue
                if neighbor_id == tgt_id:
                    raw_path = path + [(edge_id, current_id, neighbor_id, rel, "outgoing")]
                    break
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((
                        neighbor_id,
                        path + [(edge_id, current_id, neighbor_id, rel, "outgoing")],
                    ))

            if raw_path:
                break

            # Incoming edges (neighbor → current) — traverse in reverse
            for edge_id, neighbor_id, rel, weight in adj.get("in", []):
                if rel not in ("DEPENDS_ON", "RELATED_TO"):
                    continue
                if neighbor_id not in entity_ids and neighbor_id != tgt_id:
                    continue
                if neighbor_id == tgt_id:
                    raw_path = path + [(edge_id, current_id, neighbor_id, rel, "incoming")]
                    break
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((
                        neighbor_id,
                        path + [(edge_id, current_id, neighbor_id, rel, "incoming")],
                    ))

            if raw_path:
                break

        if not raw_path:
            logger.debug(
                f"find_join_path: no path  {source_entity!r} → {target_entity!r}"
            )
            return None

        return await self._build_join_path(raw_path, instance_id)

    async def find_multi_entity_path(
        self,
        entities: list[str],
        instance_id: str,
    ) -> MultiEntityPlan:
        """
        Given N entities, find the minimum set of join paths to connect them all.
        Uses the highest-importance entity as anchor. Falls back to the first entity
        if no importance scores are set.
        """
        if not entities:
            return MultiEntityPlan()

        if len(entities) == 1:
            return MultiEntityPlan(anchor_entity=entities[0], paths=[])

        # Pick anchor: entity with highest importance_score
        anchor = await self._pick_anchor(entities, instance_id)
        remaining = [e for e in entities if e != anchor]

        plan = MultiEntityPlan(anchor_entity=anchor)
        connected: list[str] = [anchor]  # entities already reachable from anchor

        for target in remaining:
            # Try from anchor first
            path = await self.find_join_path(anchor, target, instance_id)
            if path is None:
                # Try via any already-connected entity
                for bridge in connected[1:]:
                    path = await self.find_join_path(bridge, target, instance_id)
                    if path is not None:
                        break

            if path is None:
                plan.unreachable.append(target)
                logger.debug(
                    f"find_multi_entity_path: {target!r} unreachable from {anchor!r}"
                )
            else:
                # Deduplicate: merge paths sharing intermediate entities
                if not self._is_redundant(path, plan.paths):
                    plan.paths.append(path)
                connected.append(target)

        return plan

    def get_join_sql_fragment(
        self,
        path: JoinPath,
        base_entity: Optional[str] = None,
        dialect: str = "sqlite",
    ) -> str:
        """
        Convert a JoinPath into a SQL JOIN clause fragment.
        Uses INNER JOIN for FK relationships and LEFT JOIN for inferred ones.
        """
        if not path.steps:
            return ""

        lines: list[str] = []

        # The first FROM table is whichever entity is named by the caller (or first step's from_entity)
        anchor = base_entity or path.steps[0].from_entity

        for step in path.steps:
            join_kw = "INNER JOIN" if step.join_type == "fk" else "LEFT JOIN"

            if step.direction == "outgoing":
                # anchor.from_column = step.to_entity.to_column
                lhs = f"{step.from_entity}.{step.from_column}"
                rhs = f"{step.to_entity}.{step.to_column}"
                lines.append(f"{join_kw} {step.to_entity} ON {lhs} = {rhs}")
            else:
                # "incoming" means the edge was traversed in reverse:
                # we joined from to_entity side, FK lives on from_entity side
                lhs = f"{step.to_entity}.{step.from_column}"
                rhs = f"{step.from_entity}.{step.to_column}"
                lines.append(f"{join_kw} {step.to_entity} ON {lhs} = {rhs}")

        return "\n".join(lines)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _build_join_path(
        self, raw_path: list[tuple], instance_id: str
    ) -> JoinPath:
        """
        Resolve edge properties for a raw BFS path and build a JoinPath.
        raw_path entries: (edge_id, from_node_id, to_node_id, relationship, direction)
        """
        steps: list[JoinStep] = []
        total_conf = 1.0

        # Batch-fetch all edges by id
        edge_ids = [entry[0] for entry in raw_path]
        edge_map: dict[str, KnowledgeEdge] = {}
        if edge_ids:
            edges = await self.store.db.select(KnowledgeEdge, ("id__in", edge_ids))
            for edge in edges:
                edge_map[edge.id] = edge

        for edge_id, from_node_id, to_node_id, rel, direction in raw_path:
            from_name = _node_name_from_cache(from_node_id) or from_node_id
            to_name = _node_name_from_cache(to_node_id) or to_node_id

            edge = edge_map.get(edge_id)
            props: dict = {}
            if edge and edge.properties:
                try:
                    props = json.loads(edge.properties)
                except Exception:
                    pass

            # Resolve join columns
            if direction == "outgoing":
                from_col, to_col = await self._resolve_columns(
                    from_node_id, from_name, to_node_id, to_name, props, direction, instance_id
                )
            else:
                # Edge is reversed: "from" in our traversal is actually the target side
                from_col, to_col = await self._resolve_columns(
                    to_node_id, to_name, from_node_id, from_name, props, "outgoing", instance_id
                )

            confidence = props.get("confidence", 1.0 if rel == "DEPENDS_ON" else 0.7)
            join_type = "fk" if rel == "DEPENDS_ON" else "inferred"

            steps.append(JoinStep(
                from_entity=from_name,
                from_column=from_col,
                to_entity=to_name,
                to_column=to_col,
                join_type=join_type,
                confidence=confidence,
                direction=direction,
            ))
            total_conf *= confidence

        return JoinPath(
            steps=steps,
            total_confidence=round(total_conf, 4),
            hop_count=len(steps),
        )

    async def _resolve_columns(
        self,
        src_node_id: str,
        src_name: str,
        tgt_node_id: str,
        tgt_name: str,
        edge_props: dict,
        direction: str,
        instance_id: str,
    ) -> tuple[str, str]:
        """
        Determine (from_column, to_column) for a join step.

        Priority:
        1. Use via_column from edge properties if present.
        2. Scan ATTRIBUTE nodes on the source entity for a FK column pointing at target.
        3. Fall back to "{target}_id" → "id".
        """
        via_col = edge_props.get("via_column")
        if via_col:
            # Edge knows the FK column; assume target joins on its PK ("id" or "{target}_id")
            tgt_pk = await self._get_primary_key(tgt_node_id, tgt_name, instance_id)
            return (via_col, tgt_pk)

        # Scan source ATTRIBUTE nodes for a FK column pointing at this target
        fk_col = await self._find_fk_column(src_node_id, tgt_name, instance_id)
        if fk_col:
            tgt_pk = await self._get_primary_key(tgt_node_id, tgt_name, instance_id)
            return (fk_col, tgt_pk)

        # Last resort fallback
        guessed_fk = f"{tgt_name}_id"
        tgt_pk = await self._get_primary_key(tgt_node_id, tgt_name, instance_id)
        return (guessed_fk, tgt_pk)

    async def _get_primary_key(
        self, node_id: str, entity_name: str, instance_id: str
    ) -> str:
        """Return the primary key column name for an entity, or 'id' as fallback."""
        # Look for an ATTRIBUTE node whose business_role == "primary_key"
        pk_col = await self._find_pk_column(node_id, instance_id)
        return pk_col or "id"

    async def _find_pk_column(self, entity_node_id: str, instance_id: str) -> Optional[str]:
        """Find the primary_key attribute column name for an entity node."""
        from ai.engine.knowledge_graph.store import _adjacency, _node_cache

        adj = _adjacency.get(entity_node_id, {})
        attr_ids = [
            neighbor_id
            for edge_id, neighbor_id, rel, weight in adj.get("out", [])
            if rel == "HAS_ATTRIBUTE"
        ]
        if not attr_ids:
            return None

        attrs = await self.store.db.select(KnowledgeNode, ("id__in", attr_ids))
        for attr in attrs:
            if not attr.properties:
                continue
            try:
                props = json.loads(attr.properties)
            except Exception:
                continue
            if props.get("business_role") == "primary_key":
                return props.get("column_name", attr.name.split(".")[-1])
        return None

    async def _find_fk_column(
        self, src_node_id: str, target_name: str, instance_id: str
    ) -> Optional[str]:
        """
        Find an ATTRIBUTE on src_node_id whose business_role is 'foreign_key'
        and whose fk_target_table matches target_name.
        """
        from ai.engine.knowledge_graph.store import _adjacency

        adj = _adjacency.get(src_node_id, {})
        attr_ids = [
            neighbor_id
            for edge_id, neighbor_id, rel, weight in adj.get("out", [])
            if rel == "HAS_ATTRIBUTE"
        ]
        if not attr_ids:
            return None

        attrs = await self.store.db.select(KnowledgeNode, ("id__in", attr_ids))
        for attr in attrs:
            if not attr.properties:
                continue
            try:
                props = json.loads(attr.properties)
            except Exception:
                continue
            if props.get("business_role") == "foreign_key":
                fk_target = props.get("fk_target_table", "")
                if fk_target.lower() == target_name.lower():
                    return props.get("column_name", attr.name.split(".")[-1])
        return None

    async def _pick_anchor(self, entities: list[str], instance_id: str) -> str:
        """Select the entity with the highest importance_score as the join anchor."""
        best_name = entities[0]
        best_score = -1.0

        for name in entities:
            eid = _entity_id_by_name(name, instance_id)
            if not eid:
                continue
            node = first(await self.store.db.select(KnowledgeNode, ("id", eid)))
            if not node or not node.properties:
                continue
            try:
                props = json.loads(node.properties)
                score = props.get("importance_score", 0.0)
                if score > best_score:
                    best_score = score
                    best_name = name
            except Exception:
                pass

        return best_name

    @staticmethod
    def _is_redundant(new_path: JoinPath, existing: list[JoinPath]) -> bool:
        """
        Return True if every step in new_path is already covered by an existing path.
        (Simple dedup: same set of from/to entity pairs.)
        """
        new_pairs = {(s.from_entity, s.to_entity) for s in new_path.steps}
        for ep in existing:
            existing_pairs = {(s.from_entity, s.to_entity) for s in ep.steps}
            if new_pairs.issubset(existing_pairs):
                return True
        return False
