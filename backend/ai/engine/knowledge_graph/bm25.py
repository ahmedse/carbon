"""
BM25 keyword/lexical search index for knowledge graph nodes.

Phase 2b-3b: the SQLite FTS5 table that backed this index is retired with the
SQLAlchemy persistence seam.  The class surface is kept so ``KnowledgeGraphStore``
call sites keep compiling, but every method is a graceful no-op — indexing and
rebuild do nothing, and ``search`` returns an empty list.  This is fail-visible
(degraded, never a fabricated hit), matching the Phase 2b-3b degradation rules.
"""
import logging

logger = logging.getLogger("pulse.knowledge_graph.bm25")


class BM25Index:
    """Lexical (keyword) search index — retired, kept as a no-op stub.

    The SQLite FTS5 backend is gone (Django Store → PostgreSQL).  Methods keep
    their original signatures so existing call sites compile and degrade
    gracefully.
    """

    async def _ensure_table(self, db) -> None:
        """No-op — the FTS5 virtual table no longer exists."""
        return None

    async def index_node(self, db, node) -> None:
        """No-op — BM25 indexing is retired."""
        return None

    async def delete_node(self, db, node_id: str) -> None:
        """No-op — BM25 indexing is retired."""
        return None

    async def search(
        self,
        db,
        query: str,
        instance_id: str,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Return (node_id, bm25_score) — always empty (BM25 retired)."""
        logger.debug(
            "BM25 search skipped for %r: index retired (no-op)", query[:60]
        )
        return []

    async def rebuild(self, db, instance_id: str) -> None:
        """No-op — BM25 rebuilding is retired."""
        logger.debug("BM25 rebuild skipped for %s: index retired (no-op)", instance_id)
        return None
