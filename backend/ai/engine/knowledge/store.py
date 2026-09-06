"""
Knowledge storage — PostgreSQL (``ai.models.KnowledgeEntity``) + vector store
for schema entities.
"""
import json
import logging
import re
from typing import Optional

from ai.engine.core.config import get_settings
from ai.engine.core.models import KnowledgeEntity, generate_uuid
from ai.store import first

logger = logging.getLogger("pulse.knowledge.store")

# ── Backward-compat: ChromaDB client for code that hasn't migrated yet ────────
_chroma_client = None


def get_chroma_client():
    """Singleton ChromaDB client. Kept for backward compatibility with
    code that hasn't migrated to get_vector_store() yet.

    When VECTOR_BACKEND=pgvector, this returns None.
    When VECTOR_BACKEND=chromadb but the chromadb package is not installed,
    this raises ImportError with a helpful message.
    """
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        if settings.VECTOR_BACKEND == "chromadb":
            try:
                import chromadb
            except ImportError:
                raise ImportError(
                    "VECTOR_BACKEND=chromadb but chromadb is not installed. "
                    "Install with: pip install chromadb==0.5.18\n"
                    "Or switch to pgvector: set VECTOR_BACKEND=pgvector in .env"
                )
            # Silence ChromaDB telemetry noise
            logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
            _chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=chromadb.config.Settings(anonymized_telemetry=False),
            )
    return _chroma_client


class KnowledgeStore:
    def __init__(self, db_session, chroma_client=None):
        self.db_session = db_session
        from ai.engine.knowledge.vector_store import get_vector_store
        self.vector = get_vector_store(db_session)

    def _collection_name(self, instance_id: str) -> str:
        return f"knowledge_{instance_id[:8]}"

    async def store_entities(self, instance_id: str, entities: list[dict]):
        """Save entities to SQLite knowledge_entities + embed and store in vector backend."""
        collection = self._collection_name(instance_id)
        ids_list: list[str] = []
        docs_list: list[str] = []
        metas_list: list[dict] = []

        for entity_data in entities:
            entity_id = generate_uuid()

            # Store in SQLite
            entity = KnowledgeEntity(
                id=entity_id,
                instance_id=instance_id,
                entity_type=entity_data.get("entity_type", "table"),
                name=entity_data["name"],
                schema_json=entity_data.get("schema_json"),
                semantic_description=entity_data.get("semantic_description", ""),
                relationships=entity_data.get("relationships"),
            )
            self.db_session.add(entity)

            ids_list.append(entity_id)
            docs_list.append(
                f"{entity_data['name']}: {entity_data.get('semantic_description', '')}"
            )
            metas_list.append({"name": entity_data["name"], "instance_id": instance_id})

        await self.db_session.commit()

        # Batch upsert into vector store. The vector backend is an ENHANCEMENT —
        # the durable PostgreSQL rows above are the source of truth. When the
        # configured backend is unavailable (e.g. chromadb not installed), the
        # lexical fallback in ``search`` still returns these entities, so
        # seeding must never fail the whole command.
        if ids_list:
            try:
                await self.vector.upsert(
                    collection=collection,
                    ids=ids_list,
                    documents=docs_list,
                    metadatas=metas_list,
                    instance_id=instance_id,
                )
            except Exception as exc:  # noqa: BLE001 - vector is best-effort
                logger.warning(
                    "Vector upsert failed for instance=%s (%s); rows are "
                    "durable and will be served by lexical search",
                    instance_id, exc,
                )

        logger.info(f"Stored {len(entities)} knowledge entities for instance {instance_id}")

    async def search(
        self, instance_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Search knowledge entities for ``instance_id``.

        1. Vector semantic search (when the configured backend is usable).
        2. Lexical fallback (guaranteed floor) — direct PostgreSQL keyword
           match over ``name`` / ``semantic_description`` so grounding works
           even when chromadb is not installed or the collection is empty.
        """
        entities: list[dict] = []

        try:
            collection = self._collection_name(instance_id)
            results = await self.vector.query(
                collection=collection,
                query_texts=[query],
                n_results=top_k,
                where={"instance_id": instance_id},
                instance_id=instance_id,
            )

            if results and results.get("ids") and results["ids"][0]:
                entity_ids = results["ids"][0]
                for eid in entity_ids:
                    entity = first(
                        await self.db_session.select(
                            KnowledgeEntity,
                            {"id": eid, "instance_id": instance_id},
                        )
                    )
                    if entity:
                        entities.append(self._entity_to_dict(entity))
        except Exception as exc:  # noqa: BLE001 - vector is best-effort
            logger.warning(
                "Vector search failed for instance=%s query=%r (%s); "
                "falling back to lexical search",
                instance_id, query, exc,
            )

        if not entities:
            entities = await self._lexical_search(instance_id, query, top_k)

        return entities

    async def _lexical_search(
        self, instance_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Django keyword fallback — no vector backend required.

        The process-doc corpus for an instance is small (tens of rows), so we
        load it and score token overlap in Python. This is deterministic,
        natural-language tolerant (no exact-phrase dependency), and returns the
        same dict shape as ``search`` so callers are agnostic to the backend.
        """
        q = (query or "").strip()
        if not q:
            return []

        from asgiref.sync import sync_to_async
        from ai.models.core import KnowledgeEntity as DjangoKnowledgeEntity

        query_terms = {t for t in re.split(r"\W+", q.lower()) if len(t) > 1}
        if not query_terms:
            return []

        def _run():
            return list(
                DjangoKnowledgeEntity.objects.filter(instance_id=instance_id)
            )

        rows = await sync_to_async(_run, thread_sensitive=True)()

        scored: list[tuple[int, int, dict]] = []
        for r in rows:
            name = (r.name or "").lower()
            desc = (r.semantic_description or "").lower()
            haystack = f"{name} {desc}"
            haystack_terms = set(re.split(r"\W+", haystack))

            overlap = len(query_terms & haystack_terms)
            # Exact / phrase bonus for contiguous matches.
            phrase_bonus = 2 if q.lower() in haystack else 0
            # Name matches are more specific than description matches.
            name_bonus = 1 if any(t in name for t in query_terms) else 0
            score = overlap * 3 + phrase_bonus + name_bonus
            if score <= 0:
                continue
            scored.append((score, -len(name), self._entity_to_dict(r)))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item[2] for item in scored[:top_k]]

    @staticmethod
    def _entity_to_dict(entity) -> dict:
        """Normalize a knowledge entity (engine or Django model) to a dict.

        Both the SQLAlchemy engine model and the Django model expose the same
        attribute names, so a single helper serves vector + lexical paths.
        """
        return {
            "id": entity.id,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "semantic_description": entity.semantic_description,
            "schema_json": entity.schema_json,
            "relationships": entity.relationships,
        }

    async def get_entity(self, instance_id: str, name: str) -> Optional[dict]:
        """Exact match lookup by entity name."""
        entity = first(
            await self.db_session.select(
                KnowledgeEntity,
                {"instance_id": instance_id, "name": name},
            )
        )
        if not entity:
            return None
        return {
            "id": entity.id,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "semantic_description": entity.semantic_description,
            "schema_json": entity.schema_json,
            "relationships": entity.relationships,
        }

    async def update_entity_description(self, entity_id: str, new_description: str):
        """Admin updates semantic description → re-embed and update vector store."""
        entity = first(
            await self.db_session.select(KnowledgeEntity, {"id": entity_id})
        )
        if not entity:
            return

        entity.semantic_description = new_description
        await self.db_session.commit()

        # Re-index in vector store
        collection = self._collection_name(entity.instance_id)
        doc_text = f"{entity.name}: {new_description}"
        try:
            await self.vector.update(
                collection=collection,
                ids=[entity_id],
                documents=[doc_text],
                metadatas=[{"name": entity.name, "instance_id": entity.instance_id}],
                instance_id=entity.instance_id,
            )
        except Exception as e:
            logger.warning(f"Vector store update failed for {entity_id}: {e}")

        logger.info(f"Updated description for entity {entity.name}")
