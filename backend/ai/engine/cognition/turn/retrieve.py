"""S2 — Retrieval witness (semantic search + memory).

BE-01-5: Wraps knowledge and memory retrieval (previously in PulseAgent.think())
lines ~140–195. Does NOT call the LLM — purely reads from knowledge store
and memory manager.

PR-17: Replaced the broken `kg_store.search_and_plan()` path (method did not
exist on KnowledgeGraphStore) with `assemble_context()` from
`knowledge_graph/context.py`, which is the same path the agent's own
`_build_knowledge_context()` uses successfully. Also populates citation_ids
from the semantic search results.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.cognition.turn.witnesses import RetrievalResult
from ai.engine.knowledge.classes import KnowledgeItemProjection
from ai.engine.knowledge.retrieval import applicability_first

logger = logging.getLogger("pulse.cognition.turn.retrieve")

# Placeholder emitted when retrieval finds nothing. It is prompt-fodder for the
# S3 draft stage (honest "you have no knowledge loaded" context), but must NEVER
# be surfaced as a grounded knowledge_chunk — the S4 critic treats any non-empty
# chunk as retrieval evidence, which would false-flag ``ungrounded_claim`` on
# perfectly valid general-knowledge answers.
_NO_KNOWLEDGE_PLACEHOLDER = "No knowledge loaded yet."


def _serialize_dt(dt):
    """ISO-format a datetime for a chunk dict (``None`` stays ``None``)."""
    return dt.isoformat() if dt is not None else None


def _curated_knowledge_chunks(knowledge_items, scope, process_state) -> list[dict]:
    """Apply applicability-first selection and render chunk dicts.

    Each chunk carries the resolved content plus freshness metadata
    (``knowledge_class``, ``version``, effective window, ``ingested_at``,
    ``is_mandatory``, ``source``) so downstream stages can attach freshness.
    Returns ``[]`` when ``knowledge_items`` is empty/None or the selection
    raises — the curated layer degrades to the graph semantic path rather than
    breaking the turn.
    """
    if not knowledge_items:
        return []
    try:
        settings = get_settings()
        top_k = getattr(settings, "RETRIEVAL_TOP_K", 10)
        selected = applicability_first(
            knowledge_items,
            scope=scope,
            objects=None,
            process_state=process_state,
            now=datetime.now(timezone.utc),
            top_k=top_k,
        )
    except Exception:  # noqa: BLE001 — curated layer is best-effort, never fatal
        logger.warning("Applicability-first retrieval failed; using graph path", exc_info=True)
        return []

    chunks: list[dict] = []
    for item in selected:
        chunks.append(
            {
                "type": "text",
                "content": item.content,
                "knowledge_class": item.knowledge_class,
                "version": item.version,
                "effective_start": _serialize_dt(item.effective_start),
                "effective_end": _serialize_dt(item.effective_end),
                "ingested_at": _serialize_dt(item.ingested_at),
                "is_mandatory": item.is_mandatory,
                "source": item.source,
            }
        )
    return chunks


class RetrievalWitness:
    """Semantic knowledge + memory retrieval. Zero LLM cost."""

    def __init__(self, knowledge_store=None, memory_manager=None):
        self.knowledge_store = knowledge_store
        self.memory_manager = memory_manager

    async def retrieve(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        user_info: dict | None = None,
        *,
        knowledge_items: list[KnowledgeItemProjection] | None = None,
        scope: dict | None = None,
        process_state: dict | None = None,
        host_user_id: str | None = None,
    ) -> RetrievalResult:
        t0 = time.monotonic()
        relevant_knowledge = _NO_KNOWLEDGE_PLACEHOLDER
        relevant_memories = "No memories available."
        citation_ids: list[str] = []
        tool_suggestions: list[str] = []
        curated_chunks: list[dict] = []

        async def _fetch_knowledge():
            nonlocal relevant_knowledge, citation_ids, tool_suggestions, curated_chunks
            # P4-02: applicability-first curated knowledge — the authoritative
            # layer. Computed first so a curated item always surfaces even when
            # the graph semantic path is missing or fails.
            curated_chunks = _curated_knowledge_chunks(
                knowledge_items, scope, process_state
            )
            if not self.knowledge_store:
                return
            from ai.engine.knowledge_graph.store import KnowledgeGraphStore
            if isinstance(self.knowledge_store, KnowledgeGraphStore):
                # ── BE-02-2: Hybrid retrieval pipeline ──────────────────────
                # pgvector → BM25 → fuse → LLM rerank → assemble_context
                relevant_knowledge, citation_ids = await self._hybrid_retrieve(
                    self.knowledge_store, user_message, instance_id
                )
            else:
                entities = await self.knowledge_store.search(
                    instance_id, user_message, top_k=10
                )
                if entities:
                    knowledge_lines = [
                        f"- {e['name']}: {e.get('semantic_description', 'No description')}"
                        for e in entities
                    ]
                    relevant_knowledge = "\n".join(knowledge_lines)

        async def _fetch_memories():
            nonlocal relevant_memories
            if not self.memory_manager:
                return
            memory_context = await self.memory_manager.retrieve_relevant_context(
                instance_id, conversation_id, user_message,
                user_identifier=user_info.get("username") if user_info else None,
                host_user_id=host_user_id,
            )
            relevant_memories = memory_context.to_prompt_text()
            logger.debug("Memory context for conv=%s: %s", conversation_id[:8], relevant_memories[:300])

        await asyncio.gather(
            _fetch_knowledge(),
            _fetch_memories(),
            return_exceptions=True,
        )

        elapsed = (time.monotonic() - t0) * 1000
        # Empty retrieval must not masquerade as evidence: keep knowledge_chunks
        # EMPTY when nothing was found (see _NO_KNOWLEDGE_PLACEHOLDER). The
        # runner already re-supplies the placeholder for the draft prompt, so
        # nothing downstream loses context; the critic now correctly sees
        # "no retrieval evidence" and skips the grounding flag.
        # P4-02: curated (applicability-first) chunks take precedence as the
        # authoritative layer; the graph semantic result is appended afterwards
        # and still feeds citation_ids.
        knowledge_chunks = list(curated_chunks)
        if relevant_knowledge and relevant_knowledge != _NO_KNOWLEDGE_PLACEHOLDER:
            knowledge_chunks.append({"type": "text", "content": relevant_knowledge})
        return RetrievalResult(
            knowledge_chunks=knowledge_chunks,
            memory_chunks=[{"type": "text", "content": relevant_memories}],
            tool_suggestions=tool_suggestions,
            citation_ids=citation_ids,
            retrieval_latency_ms=elapsed,
        )

    async def _hybrid_retrieve(
        self, kg_store, user_message: str, instance_id: str
    ) -> tuple[str, list[str]]:
        """BE-02-2: pgvector → fuse → LLM rerank → assemble_context.

        The BM25 lexical lane is retired (P1-15); ``bm25_results`` is always
        empty so fusion degrades to pure pgvector.  Returns
        (knowledge_context, citation_ids).
        """
        from ai.engine.knowledge_graph.context import assemble_context, fuse_scores, rerank_with_llm

        # ── Step 1: pgvector semantic search ────────────────────────────────
        vector_nodes = await kg_store.semantic_search(user_message, instance_id, top_k=20)
        vector_results = [(node.id, 0.85) for node in vector_nodes]  # approximate

        # ── Step 2: BM25 lexical search — retired no-op (P1-15) ─────────────
        bm25_results: list[tuple[str, float]] = []

        # ── Step 3: Fuse scores ─────────────────────────────────────────────
        settings = get_settings()
        fused = fuse_scores(vector_results, bm25_results, settings.RETRIEVAL_HYBRID_ALPHA)

        # ── Step 4: Build candidate dicts for LLM rerank ────────────────────
        if settings.RETRIEVAL_LLM_RERANK and fused:
            try:
                # Build proper candidate dicts with node details
                candidate_dicts: list[dict] = []
                for item in fused[:20]:
                    nid = item["node_id"]
                    score = item["fused_score"]
                    node = await kg_store.get_node(nid)
                    if node:
                        candidate_dicts.append({
                            "node_id": nid,
                            "name": node.name,
                            "description": node.description or "",
                            "vector_score": item.get("vector_score", score),
                            "bm25_score": item.get("bm25_score", 0.0),
                            "fused_score": score,
                        })
                    else:
                        candidate_dicts.append({
                            "node_id": nid,
                            "name": nid,
                            "description": "",
                            "vector_score": item.get("vector_score", score),
                            "bm25_score": item.get("bm25_score", 0.0),
                            "fused_score": score,
                        })
                reranked = await rerank_with_llm(
                    user_message, candidate_dicts, instance_id, top_k=10
                )
                seed_ids = [r["node_id"] for r in reranked[:10]]
            except Exception:
                logger.debug("LLM rerank failed, using fused scores", exc_info=True)
                seed_ids = [item["node_id"] for item in fused[:10]]
        else:
            seed_ids = [item["node_id"] for item in fused[:10]]

        # ── Step 5: Assemble context from reranked seeds ────────────────────
        try:
            context = await assemble_context(kg_store, user_message, instance_id)
            return context, seed_ids
        except Exception:
            logger.exception("Context assembly failed in hybrid retrieve")
            return "No knowledge loaded yet.", seed_ids

    async def _build_knowledge_context(
        self, kg_store, user_message: str, instance_id: str
    ) -> tuple[str, object | None]:
        """Build knowledge context using assemble_context (same path as the agent).

        PR-17: Replaced the broken ``kg_store.search_and_plan()`` call with
        ``assemble_context()`` from ``knowledge_graph/context.py``, which the
        agent's own ``_build_knowledge_context`` uses successfully.
        """
        from ai.engine.knowledge_graph.context import assemble_context

        try:
            context = await assemble_context(kg_store, user_message, instance_id)
            return context, None
        except Exception:
            logger.exception("Knowledge graph context assembly failed")
            return "No knowledge loaded yet.", None
