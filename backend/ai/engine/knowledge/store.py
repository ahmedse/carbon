"""
Knowledge storage — SQLite + vector store for schema entities.
"""
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.config import get_settings
from ai.engine.core.models import KnowledgeEntity, generate_uuid

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
    def __init__(self, db_session: AsyncSession, chroma_client=None):
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

        # Batch upsert into vector store
        if ids_list:
            await self.vector.upsert(
                collection=collection,
                ids=ids_list,
                documents=docs_list,
                metadatas=metas_list,
                instance_id=instance_id,
            )

        logger.info(f"Stored {len(entities)} knowledge entities for instance {instance_id}")

    async def search(
        self, instance_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Semantic search: embed query → vector similarity search → return entities."""
        collection = self._collection_name(instance_id)

        results = await self.vector.query(
            collection=collection,
            query_texts=[query],
            n_results=top_k,
            where={"instance_id": instance_id},
            instance_id=instance_id,
        )

        if not results.get("ids") or not results["ids"][0]:
            return []

        entity_ids = results["ids"][0]
        entities = []
        for eid in entity_ids:
            stmt = select(KnowledgeEntity).where(
                KnowledgeEntity.id == eid,
                KnowledgeEntity.instance_id == instance_id,
            )
            result = await self.db_session.execute(stmt)
            entity = result.scalar_one_or_none()
            if entity:
                entities.append(
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "semantic_description": entity.semantic_description,
                        "schema_json": entity.schema_json,
                        "relationships": entity.relationships,
                    }
                )

        return entities

    async def get_entity(self, instance_id: str, name: str) -> Optional[dict]:
        """Exact match lookup by entity name."""
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.instance_id == instance_id,
            KnowledgeEntity.name == name,
        )
        result = await self.db_session.execute(stmt)
        entity = result.scalar_one_or_none()
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
        stmt = select(KnowledgeEntity).where(
            KnowledgeEntity.id == entity_id,
        )
        result = await self.db_session.execute(stmt)
        entity = result.scalar_one_or_none()
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
