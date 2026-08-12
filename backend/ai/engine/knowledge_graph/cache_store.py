"""
Multi-layer query result cache — Stage 9.

Three layers, all backed by the kg_cache_entries SQLite table:

  Layer 1 — query       : SHA-256(normalized SQL + instance + role) → SynthesizedAnswer
  Layer 2 — semantic    : SHA-256(normalized utterance + instance + role) → SynthesizedAnswer
  Layer 3 — materialized: SHA-256(pre-computed rollup SQL + "__materialized__") → SynthesizedAnswer

TTL is resolved per entry using KG_CACHE_TABLE_TTLS (JSON map of table name → seconds).
The smallest TTL across all tables touched by the SQL is applied, so a join involving
a real-time table correctly gets the real-time TTL even when paired with a batch table.

All public methods are best-effort: exceptions are caught and logged so that a cache
failure never blocks the main query path.
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.knowledge_graph.models import KgCacheEntry

logger = logging.getLogger("pulse.knowledge_graph.cache_store")


# ── SQL table-name extractor ──────────────────────────────────────────────────

_FROM_PATTERN = re.compile(
    r'\b(?:FROM|JOIN)\s+(?:"?(\w+)"?\.)?"?(\w+)"?',
    re.IGNORECASE,
)

_STOP_WORDS = frozenset({
    "select", "where", "on", "and", "or", "not", "in", "as", "is",
    "null", "true", "false", "by", "having", "with", "only",
})


def extract_table_tags(sql: str) -> list[str]:
    """Extract table (relation) names referenced in a SQL query."""
    tables: list[str] = []
    for m in _FROM_PATTERN.finditer(sql):
        table = m.group(2).lower()
        if table and table not in _STOP_WORDS and table not in tables:
            tables.append(table)
    return tables


# ── Cache key helpers ─────────────────────────────────────────────────────────

def sql_cache_key(sql: str, instance_id: str, user_role: str = "", host_user_id: str = "") -> str:
    """SHA-256 of normalized SQL + instance + role + host_user_id → hexdigest."""
    normalized = re.sub(r"\s+", " ", sql.strip().lower())
    payload = f"{instance_id}|{user_role}|{host_user_id}|{normalized}"
    return hashlib.sha256(payload.encode()).hexdigest()


def semantic_cache_key(utterance: str, instance_id: str, user_role: str = "", host_user_id: str = "") -> str:
    """SHA-256 of lowercased, whitespace-normalized utterance + instance + role + host_user_id."""
    normalized = re.sub(r"\s+", " ", utterance.strip().lower())
    payload = f"{instance_id}|{user_role}|{host_user_id}|{normalized}"
    return hashlib.sha256(payload.encode()).hexdigest()


# ── TTL resolution ────────────────────────────────────────────────────────────

def _resolve_ttl(table_tags: list[str], default_ttl: int) -> int:
    """
    Return smallest TTL across *table_tags* using KG_CACHE_TABLE_TTLS.
    Falls back to *default_ttl* when no per-table override is configured.
    """
    from ai.engine.core.config import get_settings
    settings = get_settings()
    try:
        per_table: dict[str, int] = json.loads(settings.KG_CACHE_TABLE_TTLS)
    except Exception:
        per_table = {}

    if not per_table or not table_tags:
        return default_ttl

    matched = [per_table[t] for t in table_tags if t in per_table]
    return min(matched) if matched else default_ttl


# ── Serialization helpers ─────────────────────────────────────────────────────

def _serialize(synthesis) -> str:
    """Convert SynthesizedAnswer to a JSON string."""
    d: dict[str, Any] = {
        "answer_text": synthesis.answer_text,
        "shape": synthesis.shape,
        "row_count": synthesis.row_count,
        "columns": synthesis.columns,
        "rows": synthesis.rows,
        "sql_executed": synthesis.sql_executed,
        "truncated": synthesis.truncated,
        "retry_count": synthesis.retry_count,
        "provenance": synthesis.provenance,
        "cached": True,
    }
    if synthesis.viz_hint:
        d["viz_hint"] = {
            "viz_type": synthesis.viz_hint.viz_type,
            "x_axis": synthesis.viz_hint.x_axis,
            "y_axis": synthesis.viz_hint.y_axis,
            "series_column": synthesis.viz_hint.series_column,
            "title": synthesis.viz_hint.title,
        }
    return json.dumps(d, default=str)


def _deserialize(raw: str):
    """Reconstruct SynthesizedAnswer from a JSON string."""
    from ai.engine.knowledge_graph.synthesis import SynthesizedAnswer, VisualizationHint

    d = json.loads(raw)
    viz = None
    if d.get("viz_hint"):
        vh = d["viz_hint"]
        viz = VisualizationHint(
            viz_type=vh.get("viz_type", "none"),
            x_axis=vh.get("x_axis"),
            y_axis=vh.get("y_axis"),
            series_column=vh.get("series_column"),
            title=vh.get("title", ""),
        )
    return SynthesizedAnswer(
        answer_text=d.get("answer_text", ""),
        shape=d.get("shape", "empty"),
        row_count=d.get("row_count", 0),
        columns=d.get("columns", []),
        rows=d.get("rows", []),
        viz_hint=viz,
        sql_executed=d.get("sql_executed", ""),
        truncated=d.get("truncated", False),
        retry_count=d.get("retry_count", 0),
        provenance=d.get("provenance", []),
        cached=True,
    )


# ── QueryCacheStore ───────────────────────────────────────────────────────────

class QueryCacheStore:
    """
    Multi-layer result cache.  All methods are best-effort — never raises.
    """

    # ── Layer 1: SQL result cache ─────────────────────────────────────────────

    async def get_query(
        self,
        sql: str,
        instance_id: str,
        db: AsyncSession,
        user_role: str = "",
        host_user_id: str = "",
    ) -> Optional[Any]:
        """Return a cached SynthesizedAnswer for *sql*, or None on miss."""
        from ai.engine.core.config import get_settings
        if not get_settings().KG_CACHE_ENABLED:
            return None
        return await self._get(
            cache_key=sql_cache_key(sql, instance_id, user_role, host_user_id),
            instance_id=instance_id,
            db=db,
        )

    async def set_query(
        self,
        sql: str,
        instance_id: str,
        synthesis,
        db: AsyncSession,
        user_role: str = "",
        utterance: str = "",
        host_user_id: str = "",
    ) -> None:
        """Store *synthesis* under the SQL result cache."""
        from ai.engine.core.config import get_settings
        settings = get_settings()
        if not settings.KG_CACHE_ENABLED:
            return
        table_tags = extract_table_tags(sql)
        ttl = _resolve_ttl(table_tags, settings.KG_CACHE_QUERY_TTL)
        await self._set(
            cache_key=sql_cache_key(sql, instance_id, user_role, host_user_id),
            cache_layer="query",
            instance_id=instance_id,
            utterance=utterance,
            sql_executed=sql,
            synthesis=synthesis,
            table_tags=table_tags,
            ttl=ttl,
            db=db,
        )

    # ── Layer 2: Semantic cache ───────────────────────────────────────────────

    async def get_semantic(
        self,
        utterance: str,
        instance_id: str,
        db: AsyncSession,
        user_role: str = "",
        host_user_id: str = "",
    ) -> Optional[Any]:
        """Return a cached SynthesizedAnswer for *utterance*, or None on miss."""
        from ai.engine.core.config import get_settings
        if not get_settings().KG_CACHE_ENABLED:
            return None
        return await self._get(
            cache_key=semantic_cache_key(utterance, instance_id, user_role, host_user_id),
            instance_id=instance_id,
            db=db,
        )

    async def set_semantic(
        self,
        utterance: str,
        instance_id: str,
        synthesis,
        db: AsyncSession,
        user_role: str = "",
        sql_executed: str = "",
        host_user_id: str = "",
    ) -> None:
        """Store *synthesis* under the semantic (utterance) cache."""
        from ai.engine.core.config import get_settings
        settings = get_settings()
        if not settings.KG_CACHE_ENABLED:
            return
        table_tags = extract_table_tags(sql_executed) if sql_executed else []
        ttl = _resolve_ttl(table_tags, settings.KG_CACHE_SEMANTIC_TTL)
        await self._set(
            cache_key=semantic_cache_key(utterance, instance_id, user_role, host_user_id),
            cache_layer="semantic",
            instance_id=instance_id,
            utterance=utterance,
            sql_executed=sql_executed,
            synthesis=synthesis,
            table_tags=table_tags,
            ttl=ttl,
            db=db,
        )

    # ── Layer 3: Materialized aggregation cache ───────────────────────────────

    async def get_materialized(
        self,
        sql: str,
        instance_id: str,
        db: AsyncSession,
    ) -> Optional[Any]:
        """Return a cached materialized aggregation result, or None on miss."""
        from ai.engine.core.config import get_settings
        if not get_settings().KG_CACHE_ENABLED:
            return None
        return await self._get(
            cache_key=sql_cache_key(sql, instance_id, user_role="__materialized__"),
            instance_id=instance_id,
            db=db,
        )

    async def set_materialized(
        self,
        sql: str,
        instance_id: str,
        synthesis,
        db: AsyncSession,
        utterance: str = "",
    ) -> None:
        """Store a pre-computed rollup result in the materialized cache."""
        from ai.engine.core.config import get_settings
        settings = get_settings()
        if not settings.KG_CACHE_ENABLED:
            return
        table_tags = extract_table_tags(sql)
        ttl = _resolve_ttl(table_tags, settings.KG_CACHE_MATERIALIZED_TTL)
        await self._set(
            cache_key=sql_cache_key(sql, instance_id, user_role="__materialized__"),
            cache_layer="materialized",
            instance_id=instance_id,
            utterance=utterance,
            sql_executed=sql,
            synthesis=synthesis,
            table_tags=table_tags,
            ttl=ttl,
            db=db,
        )

    # ── Statistics ────────────────────────────────────────────────────────────

    async def get_stats(self, instance_id: str, db: AsyncSession) -> dict:
        """Return hit/count statistics per cache layer for *instance_id*."""
        try:
            from sqlalchemy import func as sqlfunc
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            result = await db.execute(
                select(
                    KgCacheEntry.cache_layer,
                    sqlfunc.count(KgCacheEntry.id).label("cnt"),
                    sqlfunc.sum(KgCacheEntry.hit_count).label("hits"),
                ).where(
                    KgCacheEntry.instance_id == instance_id,
                    KgCacheEntry.expires_at > now,
                ).group_by(KgCacheEntry.cache_layer)
            )
            rows = result.all()
            by_layer = {
                r.cache_layer: {"count": r.cnt, "hits": r.hits or 0}
                for r in rows
            }
            total_count = sum(v["count"] for v in by_layer.values())
            total_hits = sum(v["hits"] for v in by_layer.values())
            return {
                "instance_id": instance_id,
                "total_live_entries": total_count,
                "total_hits": total_hits,
                "by_layer": by_layer,
            }
        except Exception as exc:
            logger.warning("cache_store.get_stats error: %s", exc)
            return {"instance_id": instance_id, "error": str(exc)}

    # ── Shared internals ──────────────────────────────────────────────────────

    async def _get(
        self,
        cache_key: str,
        instance_id: str,
        db: AsyncSession,
    ) -> Optional[Any]:
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            result = await db.execute(
                select(KgCacheEntry).where(
                    KgCacheEntry.cache_key == cache_key,
                    KgCacheEntry.instance_id == instance_id,
                    KgCacheEntry.expires_at > now,
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return None

            # Increment hit counter (best-effort; ignore failure)
            try:
                await db.execute(
                    update(KgCacheEntry)
                    .where(KgCacheEntry.id == entry.id)
                    .values(hit_count=KgCacheEntry.hit_count + 1)
                )
                await db.commit()
            except Exception:
                pass

            synthesis = _deserialize(entry.result_json)
            logger.debug(
                "cache HIT  layer=%s  key=%.8s  instance=%s",
                entry.cache_layer, cache_key, instance_id,
            )
            return synthesis
        except Exception as exc:
            logger.debug("cache_store._get error: %s", exc)
            return None

    async def _set(
        self,
        cache_key: str,
        cache_layer: str,
        instance_id: str,
        utterance: str,
        sql_executed: str,
        synthesis,
        table_tags: list[str],
        ttl: int,
        db: AsyncSession,
    ) -> None:
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            expires = now + timedelta(seconds=ttl)
            serialized = _serialize(synthesis)
            tags_json = json.dumps(table_tags)

            result = await db.execute(
                select(KgCacheEntry).where(
                    KgCacheEntry.cache_key == cache_key,
                    KgCacheEntry.instance_id == instance_id,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.result_json = serialized
                existing.expires_at = expires
                existing.utterance = utterance or existing.utterance
                existing.sql_executed = sql_executed or existing.sql_executed
                existing.table_tags = tags_json
                existing.ttl_seconds = ttl
            else:
                db.add(KgCacheEntry(
                    instance_id=instance_id,
                    cache_layer=cache_layer,
                    cache_key=cache_key,
                    utterance=utterance,
                    sql_executed=sql_executed,
                    result_json=serialized,
                    table_tags=tags_json,
                    ttl_seconds=ttl,
                    expires_at=expires,
                ))
            await db.commit()
            logger.debug(
                "cache SET  layer=%s  key=%.8s  instance=%s  ttl=%ds",
                cache_layer, cache_key, instance_id, ttl,
            )
        except Exception as exc:
            logger.warning("cache_store._set error: %s", exc)
            try:
                await db.rollback()
            except Exception:
                pass
