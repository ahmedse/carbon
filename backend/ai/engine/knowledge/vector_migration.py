"""
ChromaDB → pgvector data migration.

Reads every document + embedding + metadata from every ChromaDB collection
and writes them into the ``vector_embeddings`` PostgreSQL table.

Usage (after switching VECTOR_BACKEND=pgvector + PULSE_DB_URL):
    python -m knowledge.vector_migration

Or programmatically:
    from ai.engine.knowledge.vector_migration import migrate_chromadb_to_pgvector
    await migrate_chromadb_to_pgvector(db_session)
"""

import json
import logging

logger = logging.getLogger("pulse.knowledge.vector_migration")
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("pulse.knowledge.vector_migration")

# ChromaDB's default get batch limit
CHROMA_BATCH_SIZE = 1000


@dataclass
class MigrationStats:
    collections_found: int = 0
    collections_processed: int = 0
    documents_migrated: int = 0
    documents_skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def total_documents(self) -> int:
        return self.documents_migrated + self.documents_skipped


async def migrate_chromadb_to_pgvector(
    db_session,
    chroma_client=None,
    instance_id: Optional[str] = None,
    dry_run: bool = False,
) -> MigrationStats:
    """
    Copy all vectors from every ChromaDB collection into the ``vector_embeddings``
    PostgreSQL table.

    Args:
        db_session: Async SQLAlchemy session (must be connected to the *target*
                    PostgreSQL database).
        chroma_client: Optional pre-built ``chromadb.PersistentClient``.
                       If None, one is created from settings.
        instance_id:   If set, only migrate collections matching this instance's
                       collection naming pattern. If None, migrate everything.
        dry_run:       If True, read from ChromaDB but do not write to the DB.
                       Reports what *would* be migrated.

    Returns:
        MigrationStats with counts and any errors encountered.
    """
    import chromadb
    from ai.engine.core.config import get_settings

    settings = get_settings()
    stats = MigrationStats()

    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

    # ── Discover all ChromaDB collections ─────────────────────────────────
    try:
        collection_names = chroma_client.list_collections()
    except Exception as exc:
        stats.errors.append(f"Failed to list ChromaDB collections: {exc}")
        return stats

    stats.collections_found = len(collection_names)

    if not collection_names:
        logger.info("No ChromaDB collections found — nothing to migrate.")
        return stats

    # ── Check which rows already exist in the target table ────────────────
    existing_ids: set[str] = set()
    try:
        from ai.engine.core.models import VectorEmbedding
        rows = await db_session.select(VectorEmbedding)
        existing_ids = {row.id for row in rows}
    except Exception:
        # Table might not exist yet — treat as empty
        pass

    # ── Migrate collection by collection ──────────────────────────────────
    for coll_obj in collection_names:
        # ChromaDB 0.5.x returns Collection objects, not strings
        coll_name = coll_obj.name if hasattr(coll_obj, 'name') else coll_obj
        # Apply instance filter if given
        if instance_id and not coll_name.startswith(instance_id[:8]):
            continue

        try:
            coll = chroma_client.get_collection(coll_name)
            coll_stats = await _migrate_collection(
                db_session, coll, coll_name, existing_ids, dry_run
            )
            stats.documents_migrated += coll_stats.documents_migrated
            stats.documents_skipped += coll_stats.documents_skipped
            stats.collections_processed += 1
        except Exception as exc:
            msg = f"Collection '{coll_name}' migration failed: {exc}"
            logger.warning(msg)
            stats.errors.append(msg)

    logger.info(
        "Migration complete: %d collections processed, "
        "%d documents migrated, %d skipped, %d errors.",
        stats.collections_processed,
        stats.documents_migrated,
        stats.documents_skipped,
        len(stats.errors),
    )
    return stats


async def _migrate_collection(
    db_session,
    collection,
    coll_name: str,
    existing_ids: set[str],
    dry_run: bool,
) -> MigrationStats:
    """Migrate a single ChromaDB collection."""
    stats = MigrationStats(collections_found=1)

    # Read all items from ChromaDB in batches
    offset = 0
    while True:
        try:
            batch = collection.get(
                include=["embeddings", "metadatas", "documents"],
                limit=CHROMA_BATCH_SIZE,
                offset=offset,
            )
        except Exception as exc:
            stats.errors.append(
                f"Collection '{coll_name}' get(offset={offset}) failed: {exc}"
            )
            break

        ids = batch.get("ids", [])
        if not ids:
            break

        documents = batch.get("documents")
        metadatas = batch.get("metadatas")
        embeddings = batch.get("embeddings")
        # ChromaDB may return numpy arrays — convert safely
        if documents is None:
            documents = [""] * len(ids)
        if metadatas is None:
            metadatas = [{}] * len(ids)
        if embeddings is None:
            embeddings = []

        for i, eid in enumerate(ids):
            if eid in existing_ids:
                stats.documents_skipped += 1
                continue

            meta = metadatas[i] if i < len(metadatas) else {}
            instance_id = meta.get("instance_id", "unknown")
            doc_text = documents[i] if i < len(documents) else ""
            emb_list = embeddings[i] if i < len(embeddings) and embeddings[i] is not None and len(embeddings[i]) > 0 else None

            if dry_run:
                stats.documents_migrated += 1
                continue

            try:
                await _insert_vector_row(
                    db_session,
                    id=eid,
                    collection=coll_name,
                    instance_id=str(instance_id),
                    document=str(doc_text),
                    metadata_json=json.dumps(meta),
                    embedding=emb_list,
                )
                existing_ids.add(eid)
                stats.documents_migrated += 1
            except Exception as exc:
                stats.errors.append(f"Insert '{eid}' in '{coll_name}' failed: {exc}")

        offset += len(ids)
        if len(ids) < CHROMA_BATCH_SIZE:
            break

    if not dry_run:
        try:
            await db_session.commit()
        except Exception as exc:
            stats.errors.append(f"Commit for '{coll_name}' failed: {exc}")

    return stats


async def _insert_vector_row(
    db_session,
    id: str,
    collection: str,
    instance_id: str,
    document: str,
    metadata_json: str,
    embedding,
) -> None:
    """Insert a single row into vector_embeddings, preserving the ChromaDB embedding."""
    from ai.engine.core.models import VectorEmbedding

    # Convert numpy array to list for JSON serialization
    if embedding is not None and hasattr(embedding, 'tolist'):
        embedding = embedding.tolist()
    emb_json = json.dumps(embedding) if embedding is not None and len(embedding) > 0 else None

    row = VectorEmbedding(
        id=id,
        collection=collection,
        instance_id=instance_id,
        document=document,
        metadata_json=metadata_json,
        embedding_json=emb_json,
    )
    db_session.add(row)


# ── CLI entry point ───────────────────────────────────────────────────────────

async def _cli_main():
    """CLI entry point: connect, migrate, report."""
    import asyncio
    from ai.engine.core.config import get_settings
    from ai.engine.core.database import get_engine, get_session_factory

    settings = get_settings()

    if settings.VECTOR_BACKEND != "pgvector":
        logger.error(
            "VECTOR_BACKEND is '%s', but migration target must be 'pgvector'. "
            "Set VECTOR_BACKEND=pgvector in .env and ensure PULSE_DB_URL "
            "points to your PostgreSQL instance.",
            settings.VECTOR_BACKEND,
        )
        return

    engine = get_engine()
    session_factory = get_session_factory()

    async with session_factory() as session:
        stats = await migrate_chromadb_to_pgvector(session)

    logger.info("=" * 50)
    logger.info("Migration report:")
    logger.info("  Collections found:     %d", stats.collections_found)
    logger.info("  Collections processed: %d", stats.collections_processed)
    logger.info("  Documents migrated:    %d", stats.documents_migrated)
    logger.info("  Documents skipped:     %d", stats.documents_skipped)
    logger.info("  Errors:               %d", len(stats.errors))
    if stats.errors:
        logger.info("Errors:")
        for err in stats.errors:
            logger.info("  - %s", err)


if __name__ == "__main__":
    import asyncio
    asyncio.run(_cli_main())
