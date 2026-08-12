"""
SchemaAnalyzer — enriches the knowledge graph with implicit relationship
discovery, column semantic classification, and entity importance scoring.

Runs after migration (Stage 1) has populated ENTITY + ATTRIBUTE nodes.
Pure analysis — reads from the graph, writes enriched properties back.
No LLM calls — all logic is heuristic / structural.
"""
import json
import logging
import math
import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

logger = logging.getLogger("pulse.knowledge_graph.schema_analyzer")

# ── Abbreviation map: column prefix → likely table name ──────────────────────
_ABBREV_MAP: dict[str, list[str]] = {
    "cust": ["customer", "customers"],
    "prod": ["product", "products"],
    "org":  ["organization", "organizations", "organisation", "organisations"],
    "emp":  ["employee", "employees"],
    "dept": ["department", "departments"],
    "inv":  ["invoice", "invoices", "inventory"],
    "txn":  ["transaction", "transactions"],
    "trans": ["transaction", "transactions"],
    "acct": ["account", "accounts"],
    "cat":  ["category", "categories"],
    "usr":  ["user", "users"],
    "addr": ["address", "addresses"],
    "proj": ["project", "projects"],
    "grp":  ["group", "groups"],
    "loc":  ["location", "locations"],
    "doc":  ["document", "documents"],
    "msg":  ["message", "messages"],
    "notif": ["notification", "notifications"],
    "cfg":  ["config", "configuration", "configurations"],
    "perm": ["permission", "permissions"],
    "sess": ["session", "sessions"],
    "tok":  ["token", "tokens"],
    "evt":  ["event", "events"],
    "rec":  ["record", "records"],
    "ref":  ["reference", "references"],
}

# ── Column name suffix → semantic group ──────────────────────────────────────
_TEMPORAL_SUFFIXES = (
    "_at", "_date", "_time", "_datetime", "_ts", "_timestamp",
    "_on", "_created", "_updated", "_modified", "_deleted",
)
_MONETARY_SUFFIXES = (
    "_amount", "_total", "_price", "_cost", "_revenue",
    "_fee", "_rate", "_value", "_balance", "_sum",
)
_STATUS_SUFFIXES = (
    "_status", "_state", "_type", "_kind", "_mode",
    "_flag", "_phase", "_stage",
)
_QUANTITY_SUFFIXES = (
    "_count", "_qty", "_quantity", "_num", "_number",
    "_size", "_length", "_weight", "_volume",
)
_RATIO_SUFFIXES = (
    "_ratio", "_pct", "_percent", "_percentage", "_rate",
    "_score", "_accuracy", "_mape", "_rmse", "_mae",
)
_IDENTIFIER_SUFFIXES = ("_id", "_uuid", "_pk", "_fk")
_NATURAL_KEY_NAMES = frozenset({
    "code", "sku", "email", "slug", "username", "label",
    "ref", "reference", "barcode", "isbn", "serial",
})
_SOFT_DELETE_NAMES = frozenset({"deleted_at", "is_deleted", "active", "archived", "enabled"})
_AUDIT_NAMES = frozenset({"created_by", "updated_by", "modified_by", "deleted_by", "owner_id", "author_id"})
_BOOLEAN_PREFIXES = ("is_", "has_", "can_", "should_", "allow_", "enable_", "disable_")


def _col_lower(name: str) -> str:
    return name.lower()


def _semantic_group(col_name: str, data_type: str) -> str:
    n = _col_lower(col_name)
    dt = (data_type or "").lower()

    if any(n.endswith(s) for s in _IDENTIFIER_SUFFIXES) or n == "id":
        return "identifier"
    if any(n.endswith(s) for s in _TEMPORAL_SUFFIXES) or "date" in dt or "time" in dt or "timestamp" in dt:
        return "temporal"
    if any(n.endswith(s) for s in _MONETARY_SUFFIXES) and ("int" in dt or "float" in dt or "numeric" in dt or "decimal" in dt or "double" in dt):
        return "monetary"
    if any(n.endswith(s) for s in _RATIO_SUFFIXES) and ("float" in dt or "numeric" in dt or "double" in dt or "real" in dt or "int" in dt):
        return "ratio"
    if any(n.endswith(s) for s in _QUANTITY_SUFFIXES) and ("int" in dt or "numeric" in dt or "float" in dt):
        return "quantity"
    if any(n.endswith(s) for s in _STATUS_SUFFIXES) and ("char" in dt or "text" in dt or "varchar" in dt or "int" in dt):
        return "status"
    if dt in ("boolean", "bool") or any(n.startswith(p) for p in _BOOLEAN_PREFIXES) or n.startswith("is") or n.startswith("has"):
        return "boolean"
    if "blob" in dt or "binary" in dt or "bytea" in dt:
        return "binary"
    if "json" in dt or "jsonb" in dt or "xml" in dt:
        return "json"
    if "int" in dt or "numeric" in dt or "float" in dt or "double" in dt or "real" in dt or "decimal" in dt:
        return "numeric"
    if "char" in dt or "text" in dt or "varchar" in dt or "string" in dt:
        return "text"
    return "other"


def _business_role(col_name: str, data_type: str, is_pk: bool, is_fk: bool) -> str:
    n = _col_lower(col_name)
    dt = (data_type or "").lower()

    if is_pk or n == "id":
        return "primary_key"
    if is_fk or (n.endswith("_id") and n != "id"):
        return "foreign_key"
    if n in _NATURAL_KEY_NAMES:
        return "natural_key"
    if n in _SOFT_DELETE_NAMES:
        return "soft_delete"
    if n in _AUDIT_NAMES:
        return "audit"
    if n in ("created_at", "updated_at", "modified_at"):
        return "timestamp"
    if any(n.endswith(s) for s in _MONETARY_SUFFIXES) and ("int" in dt or "float" in dt or "numeric" in dt or "decimal" in dt):
        return "measure"
    if any(n.endswith(s) for s in _QUANTITY_SUFFIXES) and ("int" in dt or "numeric" in dt or "float" in dt):
        return "measure"
    if any(n.endswith(s) for s in _RATIO_SUFFIXES):
        return "measure"
    if any(n.endswith(s) for s in _STATUS_SUFFIXES):
        return "dimension"
    if "char" in dt or "text" in dt or "varchar" in dt:
        return "dimension"
    return "other"


def _aggregation_hint(col_name: str, data_type: str, business_role: str) -> Optional[str]:
    if business_role != "measure":
        return None
    n = _col_lower(col_name)
    if any(n.endswith(s) for s in ("_amount", "_total", "_revenue", "_cost", "_fee", "_balance", "_price", "_sum")):
        return "sum"
    if any(n.endswith(s) for s in ("_ratio", "_pct", "_percent", "_percentage", "_rate", "_mape", "_rmse", "_mae", "_accuracy", "_score")):
        return "avg"
    if any(n.endswith(s) for s in _QUANTITY_SUFFIXES):
        return "sum"
    return "sum"  # safe default for any numeric measure


def _display_hint(col_name: str, data_type: str, semantic_grp: str) -> Optional[str]:
    if semantic_grp == "monetary":
        return "currency"
    if semantic_grp == "ratio":
        return "percentage"
    if semantic_grp == "temporal":
        n = _col_lower(col_name)
        if any(n.endswith(s) for s in ("_at", "_time", "_datetime", "_timestamp", "_ts")):
            return "datetime"
        return "date"
    if semantic_grp == "boolean":
        return "boolean"
    if semantic_grp in ("text", "status"):
        return "text"
    return None


# ── Helpers to pluralise / singularise for name matching ─────────────────────

def _name_variants(name: str) -> set[str]:
    """Generate common singular/plural variants of a table name."""
    variants = {name}
    # plural: add s
    variants.add(name + "s")
    # plural: add es
    variants.add(name + "es")
    # singular from plural: strip trailing s
    if name.endswith("ies"):
        variants.add(name[:-3] + "y")
    elif name.endswith("es") and len(name) > 3:
        variants.add(name[:-2])
    elif name.endswith("s") and len(name) > 2:
        variants.add(name[:-1])
    return variants


class SchemaAnalyzer:
    """
    Heuristic-based schema intelligence enricher.

    All methods are idempotent — safe to call multiple times.
    Uses only in-memory graph traversal + async SQLite updates.
    No LLM calls, no external dependencies.
    """

    def __init__(
        self,
        store: "KnowledgeGraphStore",
        instance_id: str,
    ):
        self.store = store
        self.instance_id = instance_id

    # ── Part 1: Implicit relationship discovery ───────────────────────────────

    async def analyze_implicit_relationships(self) -> list[dict]:
        """
        Strategy 1: Naming convention matching.
        Scans ATTRIBUTE nodes for {table_name}_id patterns and matches
        them to existing ENTITY nodes (direct, plural/singular, and abbreviation).

        Returns a list of candidate dicts for apply_implicit_relationships().
        """
        entity_nodes = await self.store.get_nodes_by_type("ENTITY", self.instance_id)
        attribute_nodes = await self.store.get_nodes_by_type("ATTRIBUTE", self.instance_id)

        # Build a flat entity name → node_id lookup (lowercase) with all variants
        entity_lookup: dict[str, str] = {}  # lower_variant → entity_node_id
        entity_id_to_name: dict[str, str] = {}
        for en in entity_nodes:
            entity_id_to_name[en.id] = en.name
            for variant in _name_variants(en.name.lower()):
                entity_lookup[variant] = en.id

        # Add abbreviation aliases
        for abbrev, expansions in _ABBREV_MAP.items():
            for expansion in expansions:
                for variant in _name_variants(expansion.lower()):
                    entity_lookup[variant] = entity_lookup.get(variant) or entity_lookup.get(expansion.lower(), "")
            # Also map abbrev itself → first expansion that exists
            for expansion in expansions:
                if expansion.lower() in entity_lookup:
                    entity_lookup[abbrev] = entity_lookup[expansion.lower()]
                    for variant in _name_variants(expansion.lower()):
                        entity_lookup[abbrev] = entity_lookup.get(variant, "")
                    break

        # Build set of already-existing DEPENDS_ON edges to avoid duplicates
        existing_deps: set[tuple[str, str]] = set()
        for en in entity_nodes:
            edges_out = await self.store.get_edges_from(en.id, "DEPENDS_ON")
            for edge in edges_out:
                existing_deps.add((en.id, edge.target_node_id))
            edges_rt = await self.store.get_edges_from(en.id, "RELATED_TO")
            for edge in edges_rt:
                existing_deps.add((en.id, edge.target_node_id))  # also skip existing RELATED_TO

        # Build attribute parent lookup: attribute_node_id → parent_entity_node_id
        attr_to_entity: dict[str, str] = {}
        for en in entity_nodes:
            ha_edges = await self.store.get_edges_from(en.id, "HAS_ATTRIBUTE")
            for edge in ha_edges:
                attr_to_entity[edge.target_node_id] = en.id

        candidates: list[dict] = []

        for attr in attribute_nodes:
            # Attribute name is "table_name.column_name"
            if "." not in attr.name:
                continue
            table_part, col_part = attr.name.split(".", 1)
            col_lower = col_part.lower()

            # Only scan columns that look like FK references
            if not (col_lower.endswith("_id") or col_lower.endswith("id")):
                continue

            # Derive the referenced table candidate from the column name
            if col_lower.endswith("_id"):
                prefix = col_lower[:-3]  # strip _id
            elif col_lower.endswith("id") and len(col_lower) > 2:
                prefix = col_lower[:-2]  # strip id
            else:
                continue

            # Skip if the prefix is trivially short (e.g., "id", "uid")
            if len(prefix) < 2:
                continue

            # Resolve to an entity — try direct, then abbreviation expansion
            target_entity_id = entity_lookup.get(prefix, "")

            if not target_entity_id:
                # Try abbreviation map: prefix may be an abbreviation
                for abbrev, expansions in _ABBREV_MAP.items():
                    if prefix == abbrev or prefix.startswith(abbrev + "_"):
                        for expansion in expansions:
                            for variant in _name_variants(expansion):
                                if variant in entity_lookup:
                                    target_entity_id = entity_lookup[variant]
                                    break
                            if target_entity_id:
                                break
                    if target_entity_id:
                        break

            if not target_entity_id:
                continue  # couldn't resolve to a known entity

            # Find the source entity for this attribute
            source_entity_id = attr_to_entity.get(attr.id)
            if not source_entity_id:
                continue

            # Don't add self-loops
            if source_entity_id == target_entity_id:
                continue

            # Skip if a DEPENDS_ON or RELATED_TO already exists
            if (source_entity_id, target_entity_id) in existing_deps:
                continue

            source_entity_name = entity_id_to_name.get(source_entity_id, "?")
            target_entity_name = entity_id_to_name.get(target_entity_id, "?")

            # Check whether there's already a confirmed FK
            fk_exists = (source_entity_id, target_entity_id) in {
                (src, tgt) for (src, tgt) in existing_deps
            }

            # Load attribute properties to check is_foreign_key
            try:
                props_raw = attr.properties
                props = json.loads(props_raw) if props_raw else {}
            except Exception:
                props = {}
            already_has_fk = props.get("is_foreign_key", False)

            candidates.append({
                "source_entity": source_entity_name,
                "source_entity_id": source_entity_id,
                "target_entity": target_entity_name,
                "target_entity_id": target_entity_id,
                "via_column": col_part,
                "strategy": "naming_convention",
                "confidence": 0.7,
                "already_has_fk": already_has_fk,
            })
            # Mark this pair as seen to avoid duplicates across multiple columns
            existing_deps.add((source_entity_id, target_entity_id))

        logger.info(
            f"analyze_implicit_relationships: found {len(candidates)} candidates "
            f"for instance {self.instance_id}"
        )
        return candidates

    async def apply_implicit_relationships(
        self,
        candidates: list[dict],
        auto_apply_threshold: float = 0.7,
    ) -> dict:
        """
        Auto-apply candidates above threshold as RELATED_TO edges.
        Store below-threshold candidates as pending_relationships on the source entity.
        """
        auto_applied = 0
        pending_review = 0
        skipped_existing = 0

        # Group pending candidates by entity id
        pending_by_entity: dict[str, list[dict]] = {}

        for c in candidates:
            if c.get("already_has_fk"):
                skipped_existing += 1
                continue

            src_id = c["source_entity_id"]
            tgt_id = c["target_entity_id"]

            if c["confidence"] >= auto_apply_threshold:
                try:
                    await self.store.add_edge({
                        "instance_id": self.instance_id,
                        "source_node_id": src_id,
                        "target_node_id": tgt_id,
                        "relationship": "RELATED_TO",
                        "properties": {
                            "via_column": c["via_column"],
                            "strategy": c["strategy"],
                            "inferred": True,
                        },
                        "confidence": c["confidence"],
                        "source": "SCHEMA",
                        "weight": 1.1,
                    })
                    auto_applied += 1
                except ValueError as exc:
                    logger.debug(f"RELATED_TO edge skipped: {exc}")
                    skipped_existing += 1
            else:
                pending_review += 1
                pending_by_entity.setdefault(src_id, []).append({
                    "target_entity": c["target_entity"],
                    "via_column": c["via_column"],
                    "confidence": c["confidence"],
                    "strategy": c["strategy"],
                })

        # Store pending info on entity nodes
        for entity_id, pending_list in pending_by_entity.items():
            node = await self.store.get_node(entity_id)
            if node:
                try:
                    props = json.loads(node.properties)
                except Exception:
                    props = {}
                props["pending_relationships"] = pending_list
                await self.store.update_node(entity_id, {"properties": props})

        summary = {
            "auto_applied": auto_applied,
            "pending_review": pending_review,
            "skipped_existing": skipped_existing,
        }
        logger.info(
            f"apply_implicit_relationships for instance {self.instance_id}: {summary}"
        )
        return summary

    # ── Part 2: Column semantic enrichment ───────────────────────────────────

    async def enrich_column_semantics(self) -> dict:
        """
        For every ATTRIBUTE node, infer and write semantic metadata into properties.
        Adds: semantic_group, business_role, aggregation_hint, display_hint.
        """
        attribute_nodes = await self.store.get_nodes_by_type("ATTRIBUTE", self.instance_id)
        by_group: dict[str, int] = {}
        enriched = 0

        for attr in attribute_nodes:
            try:
                props = json.loads(attr.properties) if attr.properties else {}
            except Exception:
                props = {}

            col_name = props.get("column_name", attr.name.split(".")[-1])
            data_type = props.get("data_type", "")
            is_pk = props.get("is_primary_key", False)
            is_fk = props.get("is_foreign_key", False)

            sg = _semantic_group(col_name, data_type)
            br = _business_role(col_name, data_type, is_pk, is_fk)
            ah = _aggregation_hint(col_name, data_type, br)
            dh = _display_hint(col_name, data_type, sg)

            props["semantic_group"] = sg
            props["business_role"] = br
            props["aggregation_hint"] = ah
            props["display_hint"] = dh

            await self.store.update_node(attr.id, {"properties": props})
            by_group[sg] = by_group.get(sg, 0) + 1
            enriched += 1

        result = {"attributes_enriched": enriched, "by_semantic_group": by_group}
        logger.info(
            f"enrich_column_semantics for instance {self.instance_id}: "
            f"{enriched} attributes enriched — {by_group}"
        )
        return result

    # ── Part 3: Entity importance scoring ────────────────────────────────────

    async def score_entity_importance(self) -> dict:
        """
        Assign importance_score (0.0–1.0) to every ENTITY node.
        Factors: connectivity, attribute_count, reference_count, row_count, name_centrality.
        """
        entity_nodes = await self.store.get_nodes_by_type("ENTITY", self.instance_id)
        if not entity_nodes:
            return {"entities_scored": 0, "top_5": [], "bottom_5": []}

        entity_names = {n.id: n.name.lower() for n in entity_nodes}

        # ── Precompute raw factors ────────────────────────────────────────────

        connectivity: dict[str, int] = {}    # total edge count
        attribute_count: dict[str, int] = {}
        reference_count: dict[str, int] = {} # incoming DEPENDS_ON + RELATED_TO
        row_counts: dict[str, float] = {}

        for en in entity_nodes:
            nid = en.id

            # Connectivity: out + in edges from in-memory graph
            from ai.engine.knowledge_graph.store import _adjacency
            adj = _adjacency.get(nid, {"out": [], "in": []})
            connectivity[nid] = len(adj["out"]) + len(adj["in"])

            # Attribute count: count HAS_ATTRIBUTE edges
            ha_edges = await self.store.get_edges_from(nid, "HAS_ATTRIBUTE")
            attribute_count[nid] = len(ha_edges)

            # Reference count: incoming DEPENDS_ON + RELATED_TO
            dep_in = await self.store.get_edges_to(nid, "DEPENDS_ON")
            rel_in = await self.store.get_edges_to(nid, "RELATED_TO")
            reference_count[nid] = len(dep_in) + len(rel_in)

            # Row count from properties
            try:
                props = json.loads(en.properties) if en.properties else {}
                rc = props.get("row_count", 0) or 0
                row_counts[nid] = math.log1p(float(rc))   # log scale
            except Exception:
                row_counts[nid] = 0.0

        # ── Name centrality ───────────────────────────────────────────────────
        # Score = number of other entity names that contain this entity's name as prefix/suffix
        name_centrality: dict[str, int] = {}
        all_names_lower = list(entity_names.values())
        for nid, ename in entity_names.items():
            score = sum(
                1 for other in all_names_lower
                if other != ename and (other.startswith(ename) or other.endswith(ename))
            )
            name_centrality[nid] = score

        # ── Normalise each factor to [0, 1] ──────────────────────────────────
        def _normalise(d: dict) -> dict:
            max_val = max(d.values()) if d else 0
            if max_val == 0:
                return {k: 0.0 for k in d}
            return {k: v / max_val for k, v in d.items()}

        n_conn = _normalise(connectivity)
        n_attr = _normalise(attribute_count)
        n_ref  = _normalise(reference_count)
        n_rows = _normalise(row_counts)
        n_cent = _normalise(name_centrality)

        # ── Weighted sum → importance score ──────────────────────────────────
        W_CONN = 0.30
        W_ATTR = 0.15
        W_REF  = 0.25
        W_ROWS = 0.15
        W_CENT = 0.15

        scores: list[tuple[str, float, str]] = []  # (id, score, name)
        for en in entity_nodes:
            nid = en.id
            score = (
                W_CONN * n_conn.get(nid, 0)
                + W_ATTR * n_attr.get(nid, 0)
                + W_REF  * n_ref.get(nid, 0)
                + W_ROWS * n_rows.get(nid, 0)
                + W_CENT * n_cent.get(nid, 0)
            )
            factors = {
                "connectivity": round(n_conn.get(nid, 0), 3),
                "attribute_count": round(n_attr.get(nid, 0), 3),
                "reference_count": round(n_ref.get(nid, 0), 3),
                "row_count_log": round(n_rows.get(nid, 0), 3),
                "name_centrality": round(n_cent.get(nid, 0), 3),
            }

            # Write back to node properties
            try:
                props = json.loads(en.properties) if en.properties else {}
            except Exception:
                props = {}
            props["importance_score"] = round(score, 4)
            props["importance_factors"] = factors
            await self.store.update_node(nid, {"properties": props})

            scores.append((nid, score, en.name))

        scores.sort(key=lambda x: x[1], reverse=True)
        top_5 = [(name, round(s, 4)) for _, s, name in scores[:5]]
        bottom_5 = [(name, round(s, 4)) for _, s, name in scores[-5:]]

        result = {
            "entities_scored": len(entity_nodes),
            "top_5": top_5,
            "bottom_5": bottom_5,
        }
        logger.info(
            f"score_entity_importance for instance {self.instance_id}: "
            f"top_5={top_5}"
        )
        return result


# ── Standalone pipeline helper ────────────────────────────────────────────────

async def run_schema_analysis(
    instance_id: str,
    force: bool = False,
    session=None,
) -> dict:
    """
    Run the full analysis pipeline for one instance.

    If force=False (default), checks whether ENTITY nodes already have an
    importance_score — if they do, skips the entire analysis (idempotent).

    Pass an open AsyncSession as `session`, or leave None to open one.
    Returns combined summary dict from all three methods.
    """
    from ai.engine.knowledge_graph.store import KnowledgeGraphStore

    async def _run(db_session):
        store = KnowledgeGraphStore(db_session)

        # Idempotency check
        if not force:
            entities = await store.get_nodes_by_type("ENTITY", instance_id)
            if entities:
                try:
                    first_props = json.loads(entities[0].properties or "{}")
                    if "importance_score" in first_props:
                        logger.info(
                            f"Schema analysis already run for instance {instance_id}. "
                            f"Use force=True to re-run."
                        )
                        return {"skipped": True, "reason": "already_analysed"}
                except Exception:
                    pass

        analyzer = SchemaAnalyzer(store, instance_id)

        semantics_result = await analyzer.enrich_column_semantics()
        candidates = await analyzer.analyze_implicit_relationships()
        apply_result = await analyzer.apply_implicit_relationships(candidates)
        scoring_result = await analyzer.score_entity_importance()

        return {
            "column_semantics": semantics_result,
            "implicit_relationships": {
                "candidates_found": len(candidates),
                **apply_result,
            },
            "entity_importance": scoring_result,
        }

    if session is not None:
        return await _run(session)

    from ai.engine.core.database import get_session_factory
    session_factory = get_session_factory()
    async with session_factory() as db:
        return await _run(db)
