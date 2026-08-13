"""
Cache invalidator — Stage 9.

Evicts KgCacheEntry rows by:
  • table tag  — evict all entries whose table_tags JSON list contains the named table
  • global     — evict all entries for an instance (optionally scoped to one layer)
  • TTL expiry — periodic sweep of entries whose expires_at has passed

All public methods are idempotent and best-effort (exceptions are caught and logged).
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ai.models.knowledge_graph import KgCacheEntry

logger = logging.getLogger("pulse.knowledge_graph.cache_invalidator")


class CacheInvalidator:

    async def invalidate_table(
        self,
        table_name: str,
        instance_id: str,
        db,
    ) -> int:
        """
        Evict all cache entries that reference *table_name* in their table_tags.
        Returns the number of evicted entries.
        """
        try:
            entries = await db.select(KgCacheEntry, ("instance_id", instance_id))

            needle = table_name.lower()
            ids_to_delete: list[str] = []
            for entry in entries:
                try:
                    tags: list[str] = json.loads(entry.table_tags or "[]")
                    if needle in [t.lower() for t in tags]:
                        ids_to_delete.append(entry.id)
                except Exception:
                    pass

            for entry in entries:
                if entry.id in ids_to_delete:
                    await db.delete(entry)
            if ids_to_delete:
                await db.commit()

            logger.info(
                "cache_invalidator: evicted %d entries  table=%s  instance=%s",
                len(ids_to_delete), table_name, instance_id,
            )
            return len(ids_to_delete)
        except Exception as exc:
            logger.warning("cache_invalidator.invalidate_table error: %s", exc)
            return 0

    async def invalidate_all(
        self,
        instance_id: str,
        db,
        cache_layer: Optional[str] = None,
    ) -> int:
        """
        Evict all cache entries for *instance_id*.
        Pass *cache_layer* ("query"|"semantic"|"materialized") to flush only that layer.
        Returns the number of evicted entries.
        """
        try:
            filters: list = [("instance_id", instance_id)]
            if cache_layer:
                filters.append(("cache_layer", cache_layer))
            entries = await db.select(KgCacheEntry, *filters)
            ids = [e.id for e in entries]

            for entry in entries:
                await db.delete(entry)
            if ids:
                await db.commit()

            logger.info(
                "cache_invalidator: flushed %d entries  instance=%s  layer=%s",
                len(ids), instance_id, cache_layer or "all",
            )
            return len(ids)
        except Exception as exc:
            logger.warning("cache_invalidator.invalidate_all error: %s", exc)
            return 0

    async def evict_expired(self, db) -> int:
        """
        Delete all entries whose TTL has passed.
        Called periodically (e.g. from the cognition loop or on startup).
        Returns the number of evicted entries.
        """
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            entries = await db.select(KgCacheEntry, ("expires_at__lte", now))
            ids = [e.id for e in entries]

            for entry in entries:
                await db.delete(entry)
            if ids:
                await db.commit()
                logger.info("cache_invalidator: evicted %d expired entries", len(ids))

            return len(ids)
        except Exception as exc:
            logger.warning("cache_invalidator.evict_expired error: %s", exc)
            return 0
