"""
Vector store abstraction — pluggable backend for semantic search.

Supports two backends controlled by ``VECTOR_BACKEND`` in settings:
  * ``chromadb`` — embedded ChromaDB (legacy, requires chromadb package)
  * ``pgvector``  — PostgreSQL + pgvector extension (postgres only)

All existing consumers (KnowledgeStore, KnowledgeGraphStore, LongTermMemory,
EpisodicMemory) go through ``get_vector_store()`` and call the same
upsert/query/delete interface regardless of backend.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_log = logging.getLogger("pulse.vector_store")


# ── Abstract interface ───────────────────────────────────────────────────────

class AbstractVectorStore(ABC):
    """Minimal interface that mirrors the ChromaDB collection API enough for
    all existing Pulse consumers."""

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        instance_id: str,
    ) -> None:
        """Insert or update vector documents."""

    @abstractmethod
    async def query(
        self,
        collection: str,
        query_texts: list[str],
        n_results: int,
        where: dict | None,
        instance_id: str,
    ) -> dict:
        """Semantic search. Returns ChromaDB-shaped result dict."""

    @abstractmethod
    async def delete(self, collection: str, ids: list[str], instance_id: str) -> None:
        """Remove documents by ID."""

    @abstractmethod
    async def update(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        instance_id: str,
    ) -> None:
        """Update documents (re-embed and replace)."""


# ── Factory ───────────────────────────────────────────────────────────────────

def get_vector_store(db_session: AsyncSession) -> AbstractVectorStore:
    """Return the configured vector store backend.

    The backend is chosen once per process based on ``VECTOR_BACKEND``.
    """
    from ai.engine.core.config import get_settings

    settings = get_settings()
    backend = settings.VECTOR_BACKEND.strip().lower()

    if backend == "pgvector":
        return PgVectorStore(db_session)
    else:
        return ChromaDbVectorStore(db_session)


# ── ChromaDB implementation (DEPRECATED — prefer pgvector) ──────────────────

class ChromaDbVectorStore(AbstractVectorStore):
    """ChromaDB-backed store. Kept for backward compatibility.
    Prefer PgVectorStore for new deployments. Requires ``pip install chromadb``."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._client = None

    def _get_client(self):
        if self._client is None:
            from ai.engine.knowledge.store import get_chroma_client
            self._client = get_chroma_client()
        return self._client

    def _get_collection(self, collection: str):
        chroma = self._get_client()
        return chroma.get_or_create_collection(
            name=collection,
            metadata={},
        )

    async def upsert(self, collection, ids, documents, metadatas, instance_id):
        coll = self._get_collection(collection)
        coll.upsert(ids=ids, documents=documents, metadatas=metadatas)

    async def query(self, collection, query_texts, n_results, where, instance_id):
        coll = self._get_collection(collection)
        try:
            return coll.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
            )
        except Exception:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    async def delete(self, collection, ids, instance_id):
        coll = self._get_collection(collection)
        try:
            coll.delete(ids=ids)
        except Exception:
            pass

    async def update(self, collection, ids, documents, metadatas, instance_id):
        # ChromaDB's update doesn't accept documents, so we do upsert (which re-embeds)
        coll = self._get_collection(collection)
        try:
            coll.update(ids=ids, metadatas=metadatas)
        except Exception:
            pass


# ── PostgreSQL + pgvector implementation ──────────────────────────────────────

class PgVectorStore(AbstractVectorStore):
    """
    Vector embeddings stored in the ``vector_embeddings`` SQL table.

    Embedding is done via ``llm.embeddings.embed_text`` (OpenAI-compatible).
    The vector is serialised as JSON and stored in ``embedding_json``.
    Similarity search uses PostgreSQL's ``<=>`` (cosine distance) operator
    via ``embedding_json::vector`` casts.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ── helpers ───────────────────────────────────────────────────────────

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via the LLM embeddings provider.
        Returns empty list on failure (callers must detect and skip).
        """
        from ai.engine.llm.embeddings import embed_texts

        result = await embed_texts(texts)
        if not result:
            _log.error(
                f"Embedding failed for {len(texts)} text(s) — "
                "vector operation will be skipped (no zero-vector stored)"
            )
            return []
        return result

    def _embedding_json(self, vec: list[float]) -> str:
        return json.dumps(vec)

    def _parse_embedding(self, raw: str | None) -> list[float]:
        if not raw:
            return []
        return json.loads(raw)

    # ── public API ────────────────────────────────────────────────────────

    async def upsert(self, collection, ids, documents, metadatas, instance_id):
        from ai.engine.core.models import VectorEmbedding

        vectors = await self._embed(documents)
        if not vectors:
            return  # embedding failed — logged in _embed, no zero-vector stored
        now = None  # let server_default handle it

        for i, eid in enumerate(ids):
            emb_json = self._embedding_json(vectors[i])
            meta_json = json.dumps(metadatas[i]) if i < len(metadatas) else "{}"

            # Check for existing row (upsert pattern)
            result = await self.db.execute(
                text(
                    "SELECT id FROM vector_embeddings WHERE id = :id AND collection = :coll"
                ),
                {"id": eid, "coll": collection},
            )
            existing = result.scalar_one_or_none()

            if existing:
                await self.db.execute(
                    text(
                        "UPDATE vector_embeddings SET document = :doc, metadata_json = :meta, "
                        "embedding_json = :emb WHERE id = :id"
                    ),
                    {"id": eid, "doc": documents[i], "meta": meta_json, "emb": emb_json},
                )
            else:
                row = VectorEmbedding(
                    id=eid,
                    collection=collection,
                    instance_id=instance_id,
                    document=documents[i],
                    metadata_json=meta_json,
                    embedding_json=emb_json,
                )
                self.db.add(row)

        await self.db.commit()

    async def query(self, collection, query_texts, n_results, where, instance_id):
        query_vecs = await self._embed(query_texts)
        if not query_vecs or not query_vecs[0]:
            _log.error(
                f"Query embedding failed — returning empty result for collection={collection}"
            )
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        query_vec = query_vecs[0]
        query_json = self._embedding_json(query_vec)

        # Build WHERE clause from ChromaDB-style `where` dict
        where_clauses = ["collection = :coll"]
        params: dict = {"coll": collection, "limit": n_results}

        # Determine dialect for metadata JSON filter
        try:
            bind = self.db.get_bind()
            is_pg = bind.dialect.name == "postgresql"
        except Exception:
            is_pg = False

        if where:
            for key, val in where.items():
                param_key = f"w_{key}"
                if is_pg:
                    where_clauses.append(f"metadata_json::jsonb->>'{key}' = :{param_key}")
                else:
                    where_clauses.append(f"json_extract(metadata_json, '$.{key}') = :{param_key}")
                params[param_key] = val

        where_sql = " AND ".join(where_clauses)

        # Try pgvector native cosine similarity first
        pgvector_sql = (
            "SELECT id, document, metadata_json, embedding_json, "
            "  1 - (embedding_json::vector <=> :query_vec::vector) AS similarity "
            f"FROM vector_embeddings WHERE {where_sql} "
            "AND embedding_json IS NOT NULL "
            "ORDER BY similarity DESC LIMIT :limit"
        )

        try:
            params["query_vec"] = query_json
            result = await self.db.execute(text(pgvector_sql), params)
            rows = result.mappings().all()
            del params["query_vec"]
        except Exception:
            # pgvector extension not available → rollback & fall back to Python cosine similarity
            await self.db.rollback()
            params.pop("query_vec", None)
            rows = await self._query_python_fallback(
                where_sql, params, query_vec, n_results
            )

        ids_list: list[str] = []
        docs_list: list[str] = []
        metas_list: list[dict] = []
        dists_list: list[float] = []

        for row in rows:
            ids_list.append(row["id"])
            docs_list.append(row["document"])
            metas_list.append(json.loads(row["metadata_json"]) if row["metadata_json"] else {})
            # similarity → distance
            sim = row.get("similarity", 0.0)
            dists_list.append(1.0 - float(sim))

        return {
            "ids": [ids_list],
            "documents": [docs_list],
            "metadatas": [metas_list],
            "distances": [dists_list],
        }

    async def _query_python_fallback(
        self,
        where_sql: str,
        params: dict,
        query_vec: list[float],
        n_results: int,
    ) -> list[dict]:
        """Fallback: load all matching rows and compute cosine similarity in Python."""
        import math

        sql = (
            "SELECT id, document, metadata_json, embedding_json "
            f"FROM vector_embeddings WHERE {where_sql} "
            "AND embedding_json IS NOT NULL"
        )
        result = await self.db.execute(text(sql), params)
        rows = result.mappings().all()

        # Compute cosine similarity in Python
        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for row in rows:
            emb = json.loads(row["embedding_json"]) if row["embedding_json"] else []
            if emb:
                sim = cosine_sim(query_vec, emb)
                scored.append({**row, "similarity": sim})

        scored.sort(key=lambda r: r["similarity"], reverse=True)
        return scored[:n_results]

    async def delete(self, collection, ids, instance_id):
        if not ids:
            return
        placeholders = ",".join([f":id_{i}" for i in range(len(ids))])
        params = {f"id_{i}": eid for i, eid in enumerate(ids)}
        params["coll"] = collection
        await self.db.execute(
            text(f"DELETE FROM vector_embeddings WHERE collection = :coll AND id IN ({placeholders})"),
            params,
        )
        await self.db.commit()

    async def update(self, collection, ids, documents, metadatas, instance_id):
        if not documents:
            return
        # Re-embed updated documents
        vectors = await self._embed(documents)
        if not vectors:
            return  # embedding failed — logged in _embed, no zero-vector stored
        for i, eid in enumerate(ids):
            meta_json = json.dumps(metadatas[i]) if i < len(metadatas) else "{}"
            emb_json = self._embedding_json(vectors[i])
            await self.db.execute(
                text(
                    "UPDATE vector_embeddings SET document = :doc, metadata_json = :meta, "
                    "embedding_json = :emb WHERE id = :id AND collection = :coll"
                ),
                {"id": eid, "coll": collection, "doc": documents[i], "meta": meta_json, "emb": emb_json},
            )
        await self.db.commit()
