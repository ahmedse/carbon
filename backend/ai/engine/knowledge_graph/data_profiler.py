"""
DataProfiler — Stage 4 data profiling & value intelligence.

Connects to the host PostgreSQL database (READ-ONLY, same pattern as tools.py)
and collects per-table statistics: row counts, null rates, distinct counts,
min/max values, and low-cardinality value lists.

Results are stored as additional keys inside each ENTITY node's `properties`
JSON blob via KnowledgeGraphStore.store_table_profile().

Also validates inferred FK edges via FK-value-overlap analysis and prunes
edges whose overlap falls below KG_RELATIONSHIP_MATCH_THRESHOLD.
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("pulse.knowledge_graph.data_profiler")

# ── Default PII column-name patterns ─────────────────────────────────────────
_DEFAULT_PII_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bemail\b", re.I),
    re.compile(r"\bpassword\b", re.I),
    re.compile(r"\bphone\b", re.I),
    re.compile(r"\bssn\b", re.I),
    re.compile(r"\b(first|last)_?name\b", re.I),
    re.compile(r"\baddress\b", re.I),
    re.compile(r"\bip_?addr", re.I),
    re.compile(r"\bcredit_?card\b", re.I),
    re.compile(r"\bdob\b", re.I),
    re.compile(r"\bbirthdate\b", re.I),
]


def _build_pii_patterns(extra: str) -> list[re.Pattern]:
    """Combine default patterns with any user-supplied extras (comma-separated)."""
    patterns = list(_DEFAULT_PII_PATTERNS)
    if extra:
        for pat in extra.split(","):
            pat = pat.strip()
            if pat:
                try:
                    patterns.append(re.compile(pat, re.I))
                except re.error:
                    logger.warning(f"Invalid PII pattern ignored: {pat!r}")
    return patterns


def _is_pii(col_name: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(col_name) for p in patterns)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ColumnProfile:
    column_name: str
    data_type: str
    row_count: int = 0
    null_count: int = 0
    null_rate: float = 0.0
    distinct_count: Optional[int] = None
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    value_list: list[str] = field(default_factory=list)  # only if cardinality ≤ max_cardinality
    is_pii: bool = False
    profiled_at: str = ""


@dataclass
class TableProfile:
    table_name: str
    row_count: int = 0
    columns: list[ColumnProfile] = field(default_factory=list)
    profiled_at: str = ""
    sample_size: int = 0


@dataclass
class RelationshipValidation:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    overlap_ratio: float = 0.0
    edge_id: str = ""
    should_prune: bool = False


# ── DataProfiler ──────────────────────────────────────────────────────────────

class DataProfiler:
    """
    Profiles the host database tables using READ-ONLY psycopg2 connections.

    All SQL execution uses asyncio.to_thread() with psycopg2 (matching
    the pattern in agent/tools.py) to avoid blocking the event loop.
    """

    def __init__(self, host_db_url: str, schema: str = "public"):
        self.host_db_url = host_db_url
        self.schema = schema

    # ── Public API ────────────────────────────────────────────────────────────

    async def profile_table(
        self,
        table_name: str,
        columns: list[dict],
        sample_size: int = 10000,
        max_cardinality: int = 50,
        pii_patterns: list[re.Pattern] | None = None,
    ) -> TableProfile:
        """
        Profile a single table.

        ``columns`` is a list of dicts with at least ``name`` and ``type`` keys,
        sourced from the knowledge graph's stored schema JSON.
        """
        if pii_patterns is None:
            pii_patterns = _DEFAULT_PII_PATTERNS

        profiled_at = datetime.now(timezone.utc).isoformat()

        # Step 1: exact row count (FAST — uses pg stats if available, falls back to COUNT)
        row_count = await self._get_row_count(table_name, sample_size)

        col_profiles: list[ColumnProfile] = []
        for col_info in columns:
            col_name = col_info.get("name") or col_info.get("column_name", "")
            col_type = col_info.get("type") or col_info.get("data_type", "text")
            if not col_name:
                continue

            cp = await self._profile_column(
                table_name=table_name,
                col_name=col_name,
                col_type=col_type,
                row_count=row_count,
                sample_size=sample_size,
                max_cardinality=max_cardinality,
                pii_patterns=pii_patterns,
            )
            col_profiles.append(cp)

        return TableProfile(
            table_name=table_name,
            row_count=row_count,
            columns=col_profiles,
            profiled_at=profiled_at,
            sample_size=min(sample_size, row_count) if row_count else 0,
        )

    async def validate_graph_relationships(
        self,
        relationships: list[dict],
        threshold: float = 0.7,
    ) -> list[RelationshipValidation]:
        """
        For each inferred (non-FK) relationship, sample values on both sides
        and compute overlap ratio.  Returns a list of RelationshipValidation
        objects; those with overlap_ratio < threshold have should_prune=True.

        ``relationships`` is a list of dicts with keys:
            edge_id, source_table, source_column, target_table, target_column, source
        Only edges with source == "INFERRED" are tested.
        """
        results: list[RelationshipValidation] = []
        for rel in relationships:
            if rel.get("source", "").upper() != "INFERRED":
                continue
            rv = await self._validate_relationship(
                edge_id=rel.get("edge_id", ""),
                source_table=rel["source_table"],
                source_column=rel["source_column"],
                target_table=rel["target_table"],
                target_column=rel["target_column"],
                threshold=threshold,
            )
            results.append(rv)
        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _run_query(self, sql: str, params=None) -> list[dict]:
        """
        Execute a read-only SQL query on the host DB and return rows as dicts.
        Mirrors the connection pattern in agent/tools.py exactly.
        """
        host_db_url = self.host_db_url

        def _sync():
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(host_db_url)
            try:
                conn.set_session(readonly=True, autocommit=True)
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("SET statement_timeout = '30s'")
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                rows = cursor.fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

        return await asyncio.to_thread(_sync)

    async def _get_row_count(self, table_name: str, sample_size: int) -> int:
        """
        Try pg_stat_user_tables for a fast estimate first, then fall back to COUNT(*).
        Uses a capped scan if the table appears huge.
        """
        try:
            rows = await self._run_query(
                "SELECT n_live_tup FROM pg_stat_user_tables WHERE relname = %s",
                (table_name,),
            )
            if rows and rows[0]["n_live_tup"] is not None:
                estimate = int(rows[0]["n_live_tup"])
                if estimate > 0:
                    return estimate
        except Exception:
            pass

        try:
            quoted = self._quote(table_name)
            rows = await self._run_query(f"SELECT COUNT(*) AS cnt FROM {quoted}")
            return int(rows[0]["cnt"]) if rows else 0
        except Exception as exc:
            logger.warning(f"Row count failed for {table_name}: {exc}")
            return 0

    async def _profile_column(
        self,
        table_name: str,
        col_name: str,
        col_type: str,
        row_count: int,
        sample_size: int,
        max_cardinality: int,
        pii_patterns: list[re.Pattern],
    ) -> ColumnProfile:
        """Profile a single column: null rate, distinct count, min/max, value list."""
        cp = ColumnProfile(
            column_name=col_name,
            data_type=col_type,
            row_count=row_count,
            profiled_at=datetime.now(timezone.utc).isoformat(),
            is_pii=_is_pii(col_name, pii_patterns),
        )

        quoted_table = self._quote(table_name)
        quoted_col = self._quote(col_name)

        # Use a tablesample for large tables to keep queries fast
        sample_clause = ""
        if row_count > sample_size * 2:
            pct = min(100.0, max(1.0, sample_size / row_count * 100))
            sample_clause = f" TABLESAMPLE SYSTEM({pct:.2f})"

        # Null count + distinct count in one query
        try:
            rows = await self._run_query(
                f"SELECT COUNT(*) FILTER (WHERE {quoted_col} IS NULL) AS null_cnt, "
                f"COUNT(DISTINCT {quoted_col}) AS distinct_cnt "
                f"FROM {quoted_table}{sample_clause}"
            )
            if rows:
                cp.null_count = int(rows[0]["null_cnt"] or 0)
                cp.null_rate = round(cp.null_count / max(row_count, 1), 4)
                cp.distinct_count = int(rows[0]["distinct_cnt"] or 0)
        except Exception as exc:
            logger.debug(f"Null/distinct query failed for {table_name}.{col_name}: {exc}")

        # Min/max for orderable types (skip PII, skip binary/json/array types)
        orderable_type_prefixes = (
            "int", "float", "numeric", "decimal", "real", "double",
            "smallint", "bigint", "serial", "money",
            "date", "time", "timestamp", "interval",
            "char", "varchar", "text",
        )
        col_type_lower = col_type.lower()
        is_orderable = any(col_type_lower.startswith(p) for p in orderable_type_prefixes)
        is_json_like = any(t in col_type_lower for t in ("json", "array", "bytea", "bit"))

        if is_orderable and not cp.is_pii and not is_json_like:
            try:
                rows = await self._run_query(
                    f"SELECT MIN({quoted_col}::text) AS mn, MAX({quoted_col}::text) AS mx "
                    f"FROM {quoted_table}{sample_clause}"
                )
                if rows:
                    cp.min_value = rows[0]["mn"]
                    cp.max_value = rows[0]["mx"]
            except Exception as exc:
                logger.debug(f"Min/max query failed for {table_name}.{col_name}: {exc}")

        # Value list for low-cardinality non-PII columns
        if (
            cp.distinct_count is not None
            and cp.distinct_count <= max_cardinality
            and cp.distinct_count > 0
            and not cp.is_pii
        ):
            try:
                rows = await self._run_query(
                    f"SELECT DISTINCT {quoted_col}::text AS v "
                    f"FROM {quoted_table}{sample_clause} "
                    f"WHERE {quoted_col} IS NOT NULL "
                    f"ORDER BY 1 "
                    f"LIMIT {max_cardinality}"
                )
                cp.value_list = [r["v"] for r in rows if r["v"] is not None]
            except Exception as exc:
                logger.debug(f"Value list query failed for {table_name}.{col_name}: {exc}")

        return cp

    async def _validate_relationship(
        self,
        edge_id: str,
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
        threshold: float,
    ) -> RelationshipValidation:
        """
        Compute FK overlap ratio: what fraction of non-null source values
        appear in target column?
        """
        rv = RelationshipValidation(
            source_table=source_table,
            source_column=source_column,
            target_table=target_table,
            target_column=target_column,
            edge_id=edge_id,
        )
        try:
            sq = self._quote(source_table)
            sc = self._quote(source_column)
            tq = self._quote(target_table)
            tc = self._quote(target_column)

            rows = await self._run_query(
                f"SELECT "
                f"  COUNT(*) FILTER (WHERE {sq}.{sc} IN "
                f"      (SELECT {tc} FROM {tq} WHERE {tc} IS NOT NULL)"
                f"  ) AS matched, "
                f"  COUNT({sq}.{sc}) AS total "
                f"FROM {sq} WHERE {sq}.{sc} IS NOT NULL "
                f"LIMIT 5000"
            )
            if rows and rows[0]["total"]:
                total = int(rows[0]["total"])
                matched = int(rows[0]["matched"])
                rv.overlap_ratio = round(matched / total, 4) if total else 0.0
            else:
                rv.overlap_ratio = 0.0
        except Exception as exc:
            logger.warning(
                f"Relationship validation failed {source_table}.{source_column} → "
                f"{target_table}.{target_column}: {exc}"
            )
            rv.overlap_ratio = 0.0

        rv.should_prune = rv.overlap_ratio < threshold
        return rv

    @staticmethod
    def _quote(name: str) -> str:
        """Double-quote an identifier to handle reserved words and mixed case."""
        safe = name.replace('"', '""')
        return f'"{safe}"'


# ── Convenience run function ──────────────────────────────────────────────────

async def run_data_profiling(
    instance_id: str,
    kg_store,           # KnowledgeGraphStore
    host_db_url: str,
    schema: str = "public",
    force: bool = False,
) -> dict:
    """
    Top-level entry point called from admin.py.

    For each ENTITY node:
      1. Check profile freshness (skip if recent & not forced)
      2. Extract column list from node.properties["columns"]
      3. Profile the table
      4. Store profile back via store.store_table_profile()

    Then validate inferred FK edges and prune stale ones.

    Returns a summary dict.
    """
    from ai.engine.core.config import get_settings
    from ai.engine.knowledge_graph.models import KnowledgeEdge, KnowledgeNode
    from sqlalchemy import select

    settings = get_settings()
    if not settings.KG_DATA_PROFILING_ENABLED and not force:
        return {"skipped": True, "reason": "KG_DATA_PROFILING_ENABLED=False"}

    profiler = DataProfiler(host_db_url=host_db_url, schema=schema)
    pii_patterns = _build_pii_patterns(settings.KG_PROFILE_PII_PATTERNS)

    ttl_hours = settings.KG_PROFILE_TTL_HOURS
    sample_size = settings.KG_PROFILE_SAMPLE_SIZE
    max_cardinality = settings.KG_PROFILE_MAX_CARDINALITY
    threshold = settings.KG_RELATIONSHIP_MATCH_THRESHOLD

    entity_nodes = await kg_store.get_nodes_by_type("ENTITY", instance_id)
    logger.info(f"run_data_profiling: {len(entity_nodes)} entities to profile for {instance_id}")

    profiled_count = 0
    skipped_count = 0
    error_count = 0

    for node in entity_nodes:
        try:
            props = json.loads(node.properties) if node.properties else {}

            # Freshness check
            if not force and props.get("profiled_at"):
                try:
                    profiled_dt = datetime.fromisoformat(props["profiled_at"])
                    if profiled_dt.tzinfo is None:
                        profiled_dt = profiled_dt.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - profiled_dt).total_seconds() / 3600
                    if age_hours < ttl_hours:
                        skipped_count += 1
                        continue
                except ValueError:
                    pass

            # Extract column list from stored schema
            columns: list[dict] = []
            schema_json = props.get("columns") or props.get("schema_json")
            if isinstance(schema_json, str):
                try:
                    schema_json = json.loads(schema_json)
                except json.JSONDecodeError:
                    schema_json = None
            if isinstance(schema_json, list):
                columns = schema_json
            elif isinstance(schema_json, dict) and "columns" in schema_json:
                columns = schema_json["columns"]

            if not columns:
                logger.debug(f"No column info for {node.name} — skipping profile")
                skipped_count += 1
                continue

            table_profile = await profiler.profile_table(
                table_name=node.name,
                columns=columns,
                sample_size=sample_size,
                max_cardinality=max_cardinality,
                pii_patterns=pii_patterns if settings.KG_PROFILE_PII_ENABLED else [],
            )
            await kg_store.store_table_profile(node.id, table_profile)
            profiled_count += 1
            logger.debug(f"Profiled {node.name}: {table_profile.row_count} rows, {len(table_profile.columns)} columns")

        except Exception as exc:
            error_count += 1
            logger.warning(f"Profiling failed for {node.name}: {exc}")

    # ── Validate inferred edges ───────────────────────────────────────────────
    pruned_count = 0
    try:
        from ai.engine.knowledge_graph.models import KnowledgeEdge
        edge_stmt = select(KnowledgeEdge).where(
            KnowledgeEdge.instance_id == instance_id,
            KnowledgeEdge.source == "INFERRED",
        )
        edge_result = await kg_store.db.execute(edge_stmt)
        inferred_edges = list(edge_result.scalars().all())

        if inferred_edges:
            # Build relationship list for validation
            rel_list: list[dict] = []
            for edge in inferred_edges:
                try:
                    ep = json.loads(edge.properties) if edge.properties else {}
                    src_table = ep.get("source_table", "")
                    src_col = ep.get("source_column", "")
                    tgt_table = ep.get("target_table", "")
                    tgt_col = ep.get("target_column", "")
                    if src_table and src_col and tgt_table and tgt_col:
                        rel_list.append({
                            "edge_id": edge.id,
                            "source_table": src_table,
                            "source_column": src_col,
                            "target_table": tgt_table,
                            "target_column": tgt_col,
                            "source": "INFERRED",
                        })
                except Exception:
                    pass

            validations = await profiler.validate_graph_relationships(rel_list, threshold=threshold)
            for rv in validations:
                if rv.should_prune and rv.edge_id:
                    deleted = await kg_store.delete_edge(rv.edge_id)
                    if deleted:
                        pruned_count += 1
                        logger.info(
                            f"Pruned inferred edge {rv.source_table}.{rv.source_column} → "
                            f"{rv.target_table}.{rv.target_column} "
                            f"(overlap={rv.overlap_ratio:.2f} < {threshold})"
                        )
    except Exception as exc:
        logger.warning(f"Relationship validation failed (non-fatal): {exc}")

    return {
        "profiled": profiled_count,
        "skipped": skipped_count,
        "errors": error_count,
        "inferred_edges_pruned": pruned_count,
    }
