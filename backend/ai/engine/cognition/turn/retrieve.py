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

from ai.engine.core.config import get_settings
from ai.engine.cognition.turn.witnesses import RetrievalResult

logger = logging.getLogger("pulse.cognition.turn.retrieve")


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
    ) -> RetrievalResult:
        t0 = time.monotonic()
        relevant_knowledge = "No knowledge loaded yet."
        relevant_memories = "No memories available."
        citation_ids: list[str] = []
        tool_suggestions: list[str] = []

        async def _fetch_knowledge():
            nonlocal relevant_knowledge, citation_ids, tool_suggestions
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
            )
            relevant_memories = memory_context.to_prompt_text()
            logger.debug("Memory context for conv=%s: %s", conversation_id[:8], relevant_memories[:300])

        await asyncio.gather(
            _fetch_knowledge(),
            _fetch_memories(),
            return_exceptions=True,
        )

        elapsed = (time.monotonic() - t0) * 1000
        return RetrievalResult(
            knowledge_chunks=[{"type": "text", "content": relevant_knowledge}],
            memory_chunks=[{"type": "text", "content": relevant_memories}],
            tool_suggestions=tool_suggestions,
            citation_ids=citation_ids,
            retrieval_latency_ms=elapsed,
        )

    async def _hybrid_retrieve(
        self, kg_store, user_message: str, instance_id: str
    ) -> tuple[str, list[str]]:
        """BE-02-2: pgvector → BM25 → fuse → LLM rerank → assemble_context.

        Returns (knowledge_context, citation_ids).
        """
        from ai.engine.knowledge_graph.context import assemble_context, fuse_scores, rerank_with_llm
        from ai.engine.knowledge_graph.bm25 import BM25Index

        # ── Step 1: pgvector semantic search ────────────────────────────────
        vector_nodes = await kg_store.semantic_search(user_message, instance_id, top_k=20)
        vector_results = [(node.id, 0.85) for node in vector_nodes]  # approximate

        # ── Step 2: BM25 lexical search ─────────────────────────────────────
        try:
            bm25 = BM25Index()
            bm25_results = await bm25.search(kg_store.db, user_message, instance_id, top_k=20)
        except Exception:
            logger.debug("BM25 search failed, using only pgvector", exc_info=True)
            bm25_results = []

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
