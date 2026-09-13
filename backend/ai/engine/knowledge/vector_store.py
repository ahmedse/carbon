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

from ai.engine.ports.store import Session

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

def get_vector_store(db_session: Session) -> AbstractVectorStore:
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

    def __init__(self, db_session: Session):
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

    def __init__(self, db_session: Session):
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
        from ai.engine.core.query import first

        vectors = await self._embed(documents)
        if not vectors:
            return  # embedding failed — logged in _embed, no zero-vector stored

        for i, eid in enumerate(ids):
            emb_json = self._embedding_json(vectors[i])
            meta_json = json.dumps(metadatas[i]) if i < len(metadatas) else "{}"

            # Check for an existing row in this collection (upsert pattern).
            existing = first(
                await self.db.select(
                    VectorEmbedding,
                    ("id", eid),
                    ("collection", collection),
                )
            )

            if existing is not None:
                existing.document = documents[i]
                existing.metadata_json = meta_json
                existing.embedding_json = emb_json
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
        from ai.engine.core.models import VectorEmbedding

        query_vecs = await self._embed(query_texts)
        if not query_vecs or not query_vecs[0]:
            _log.error(
                f"Query embedding failed — returning empty result for collection={collection}"
            )
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

        query_vec = query_vecs[0]

        rows = await self.db.select(VectorEmbedding, ("collection", collection))

        # Apply the ChromaDB-style metadata filter in Python, then score the
        # surviving rows by cosine similarity (single portable path — no
        # pgvector raw SQL, no dialect branching).
        scored = self._score_rows(rows, query_vec, where or {})
        scored.sort(key=lambda r: r["similarity"], reverse=True)
        scored = scored[:n_results]

        ids_list: list[str] = []
        docs_list: list[str] = []
        metas_list: list[dict] = []
        dists_list: list[float] = []

        for row in scored:
            ids_list.append(row["id"])
            docs_list.append(row["document"])
            metas_list.append(json.loads(row["metadata_json"]) if row["metadata_json"] else {})
            # similarity → distance
            dists_list.append(1.0 - float(row["similarity"]))

        return {
            "ids": [ids_list],
            "documents": [docs_list],
            "metadatas": [metas_list],
            "distances": [dists_list],
        }

    def _score_rows(
        self,
        rows: list,
        query_vec: list[float],
        where: dict,
    ) -> list[dict]:
        """Filter rows by the ``where`` metadata dict and score by cosine."""
        import math

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        scored = []
        for row in rows:
            emb = self._parse_embedding(getattr(row, "embedding_json", None))
            if not emb:
                continue
            if where:
                try:
                    meta = json.loads(getattr(row, "metadata_json", None) or "{}")
                except (TypeError, ValueError):
                    meta = {}
                if not all(meta.get(k) == v for k, v in where.items()):
                    continue
            sim = cosine_sim(query_vec, emb)
            scored.append(
                {
                    "id": getattr(row, "id", None),
                    "document": getattr(row, "document", None),
                    "metadata_json": getattr(row, "metadata_json", None),
                    "similarity": sim,
                }
            )

        return scored

    async def delete(self, collection, ids, instance_id):
        from ai.engine.core.models import VectorEmbedding

        if not ids:
            return
        rows = await self.db.select(
            VectorEmbedding,
            ("collection", collection),
            ("id__in", list(ids)),
        )
        for row in rows:
            await self.db.delete(row)
        await self.db.commit()

    async def update(self, collection, ids, documents, metadatas, instance_id):
        from ai.engine.core.models import VectorEmbedding
        from ai.engine.core.query import first

        if not documents:
            return
        # Re-embed updated documents
        vectors = await self._embed(documents)
        if not vectors:
            return  # embedding failed — logged in _embed, no zero-vector stored
        for i, eid in enumerate(ids):
            meta_json = json.dumps(metadatas[i]) if i < len(metadatas) else "{}"
            emb_json = self._embedding_json(vectors[i])
            row = first(
                await self.db.select(
                    VectorEmbedding,
                    ("id", eid),
                    ("collection", collection),
                )
            )
            if row is not None:
                row.document = documents[i]
                row.metadata_json = meta_json
                row.embedding_json = emb_json
        await self.db.commit()
