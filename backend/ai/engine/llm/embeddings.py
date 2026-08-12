"""
Text → vector embedding.
Uses LLM provider's embedding model first; falls back to local ONNX (all-MiniLM-L6-v2, 384-dim)
when the provider doesn't support embeddings.
"""
import logging

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.llm.embeddings")

# ── Lazy-loaded local ONNX fallback ──────────────────────────────────────────
_local_ef = None


def _get_local_ef():
    """Return a cached ChromaDB DefaultEmbeddingFunction (ONNX all-MiniLM-L6-v2, 384-dim)."""
    global _local_ef
    if _local_ef is None:
        from chromadb.utils import embedding_functions

        _local_ef = embedding_functions.DefaultEmbeddingFunction()
        logger.info("Local ONNX embedding function loaded (all-MiniLM-L6-v2, 384-dim)")
    return _local_ef


async def embed_text(text: str) -> list[float]:
    """Convert text to embedding vector. Falls back to local ONNX if LLM provider fails."""
    settings = get_settings()

    # Try LLM provider's embedding model first
    if settings.LLM_API_KEY and settings.LLM_BASE_URL:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
            response = await client.embeddings.create(
                model=settings.LLM_EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(
                f"LLM embedding failed — falling back to local ONNX: {e}"
            )

    # Fall back to local ONNX embedding (all-MiniLM-L6-v2, 384-dim)
    try:
        ef = _get_local_ef()
        vectors = ef([text])
        if vectors and len(vectors) > 0:
            # ChromaDB ONNX returns numpy float32 — convert to native float
            return [float(x) for x in vectors[0]]
    except Exception as e:
        logger.error(f"Local ONNX embedding also failed: {e}", exc_info=True)

    logger.error("All embedding methods failed — returning empty list")
    return []


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed multiple texts. Falls back to local ONNX if LLM provider fails."""
    settings = get_settings()

    if settings.LLM_API_KEY and settings.LLM_BASE_URL:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
            response = await client.embeddings.create(
                model=settings.LLM_EMBEDDING_MODEL,
                input=texts,
            )
            return [d.embedding for d in response.data]
        except Exception as e:
            logger.warning(
                f"LLM batch embedding failed — falling back to local ONNX: {e}"
            )

    # Fall back to local ONNX embedding (all-MiniLM-L6-v2, 384-dim)
    try:
        ef = _get_local_ef()
        vectors = ef(texts)
        if vectors:
            # ChromaDB ONNX returns numpy float32 — convert to native float
            return [[float(x) for x in v] for v in vectors]
    except Exception as e:
        logger.error(f"Local ONNX batch embedding also failed: {e}", exc_info=True)

    logger.error("All embedding methods failed — returning empty list")
    return []
