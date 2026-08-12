"""
BM25 keyword/lexical search index for knowledge graph nodes.

Uses SQLite FTS5 for zero-dependency BM25 scoring. Synchronized with
KnowledgeNode insert/update/delete via hooks in KnowledgeGraphStore.
"""
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.knowledge_graph.models import KnowledgeNode

logger = logging.getLogger("pulse.knowledge_graph.bm25")

# FTS5 table creation SQL — runs once per database
_CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS kg_fts USING fts5(
    node_id, instance_id, name, description,
    tokenize='porter unicode61'
)
"""


class BM25Index:
    """Lexical (keyword) search index for knowledge graph nodes.

    Uses SQLite FTS5 virtual table for zero-dependency BM25 scoring.
    Synchronized with KnowledgeNode inserts/updates/deletes via hooks.
    """

    async def _ensure_table(self, db: AsyncSession) -> None:
        """Create the FTS5 virtual table if it doesn't exist."""
        try:
            await db.execute(text(_CREATE_FTS_TABLE))
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.debug("FTS table may already exist: %s", exc)

    async def index_node(self, db: AsyncSession, node: KnowledgeNode) -> None:
        """Index a node's name + description for keyword search.

        Uses INSERT OR REPLACE so re-indexing an existing node is idempotent.
        """
        await self._ensure_table(db)
        try:
            await db.execute(
                text(
                    "INSERT OR REPLACE INTO kg_fts(node_id, instance_id, name, description) "
                    "VALUES (:node_id, :instance_id, :name, :description)"
                ),
                {
                    "node_id": node.id,
                    "instance_id": node.instance_id,
                    "name": node.name,
                    "description": node.description or "",
                },
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning("Failed to index node %s in FTS: %s", node.id, exc)

    async def delete_node(self, db: AsyncSession, node_id: str) -> None:
        """Remove a node from the FTS index."""
        await self._ensure_table(db)
        try:
            await db.execute(
                text("DELETE FROM kg_fts WHERE node_id = :node_id"),
                {"node_id": node_id},
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.warning("Failed to delete node %s from FTS: %s", node_id, exc)

    async def search(
        self,
        db: AsyncSession,
        query: str,
        instance_id: str,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Return (node_id, bm25_score) ranked by BM25 relevance.

        Filters by instance_id and returns top_k results.
        Uses the FTS5 'rank' column for BM25 scoring (negative = more relevant,
        so we negate for ascending sort).
        """
        await self._ensure_table(db)
        try:
            result = await db.execute(
                text(
                    "SELECT node_id, -rank AS bm25_score "
                    "FROM kg_fts "
                    "WHERE instance_id = :instance_id "
                    "AND kg_fts MATCH :query "
                    "ORDER BY rank "
                    "LIMIT :limit"
                ),
                {
                    "instance_id": instance_id,
                    "query": query,
                    "limit": top_k,
                },
            )
            rows = result.fetchall()
            return [(row[0], float(row[1])) for row in rows]
        except Exception as exc:
            await db.rollback()
            logger.warning("BM25 search failed for query=%r: %s", query[:60], exc)
            return []

    async def rebuild(self, db: AsyncSession, instance_id: str) -> None:
        """Full reindex: drop and rebuild FTS content from all KnowledgeNode rows."""
        await self._ensure_table(db)
        # Clear existing entries for this instance
        try:
            await db.execute(
                text("DELETE FROM kg_fts WHERE instance_id = :instance_id"),
                {"instance_id": instance_id},
            )
            await db.commit()
        except Exception:
            await db.rollback()

        # Re-index all nodes for this instance
        from sqlalchemy import select

        result = await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.instance_id == instance_id)
        )
        nodes = result.scalars().all()

        batch: list[dict] = []
        for node in nodes:
            batch.append({
                "node_id": node.id,
                "instance_id": node.instance_id,
                "name": node.name,
                "description": node.description or "",
            })

        if batch:
            try:
                await db.execute(
                    text(
                        "INSERT INTO kg_fts(node_id, instance_id, name, description) "
                        "VALUES (:node_id, :instance_id, :name, :description)"
                    ),
                    batch,
                )
                await db.commit()
            except Exception as exc:
                await db.rollback()
                logger.warning("BM25 rebuild batch insert failed: %s", exc)

        logger.info(
            "BM25 rebuild for instance=%s: %d nodes indexed",
            instance_id,
            len(batch),
        )
