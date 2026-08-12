"""
Cache warmer — Stage 9.

Mines the top-N most frequent successful queries from the past 30 days
(sourced from kg_query_feedback) and re-executes them to pre-warm the cache.

Runs in a background asyncio task; never blocks startup.
A small inter-query sleep avoids thundering-herd on the host DB.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sqlfunc, select

logger = logging.getLogger("pulse.knowledge_graph.cache_warmer")

_INTER_QUERY_SLEEP = 0.15   # seconds between warm-up executions


class CacheWarmer:
    """
    Warm the caches for *instance_id* by replaying historical queries.

    Parameters
    ----------
    instance_id : str
        The Pulse instance to warm.
    llm_client  : AsyncOpenAI-compatible client
        Used to build a minimal SynthesizedAnswer for each result.
    model : str
        Fast (cheap) model for answer enrichment during warm-up.
    """

    def __init__(self, instance_id: str, llm_client=None, model: str = ""):
        self.instance_id = instance_id
        self.llm_client = llm_client  # kept for backward compat
        self.model = model

    async def warm(self, db_factory) -> int:
        """
        Mine and re-execute top-N queries.

        *db_factory* must be a zero-argument async context manager factory that
        yields an AsyncSession (use ``get_session_factory()`` from core.database).

        Returns the number of cache entries successfully written.
        """
        from ai.engine.core.config import get_settings
        settings = get_settings()

        if not settings.KG_CACHE_ENABLED or not settings.KG_CACHE_WARMUP_ENABLED:
            return 0

        top_n = settings.KG_CACHE_WARMUP_TOP_N
        lookback_days = settings.KG_CACHE_WARMUP_LOOKBACK_DAYS
        cutoff = (
            datetime.now(timezone.utc).replace(tzinfo=None)
            - timedelta(days=lookback_days)
        )

        try:
            candidates = await self._mine_queries(db_factory, cutoff, top_n)
        except Exception as exc:
            logger.warning("cache_warmer: mining failed: %s", exc)
            return 0

        if not candidates:
            logger.info("cache_warmer: no warm-up candidates found for instance=%s", self.instance_id)
            return 0

        logger.info(
            "cache_warmer: warming %d queries for instance=%s", len(candidates), self.instance_id
        )

        warmed = 0
        for utterance, sql in candidates:
            try:
                await self._warm_one(utterance, sql, db_factory)
                warmed += 1
                await asyncio.sleep(_INTER_QUERY_SLEEP)
            except Exception as exc:
                logger.debug("cache_warmer: failed to warm '%s': %s", utterance[:60], exc)

        logger.info(
            "cache_warmer: done  warmed=%d/%d  instance=%s",
            warmed, len(candidates), self.instance_id,
        )
        return warmed

    # ── internals ─────────────────────────────────────────────────────────────

    async def _mine_queries(
        self,
        db_factory,
        cutoff: datetime,
        top_n: int,
    ) -> list[tuple[str, str]]:
        """Return ``(utterance, sql)`` pairs ordered by frequency (desc)."""
        from ai.engine.knowledge_graph.models import KgQueryFeedback

        async with db_factory() as db:
            result = await db.execute(
                select(
                    KgQueryFeedback.question,
                    KgQueryFeedback.sql_final,
                    sqlfunc.count(KgQueryFeedback.id).label("freq"),
                ).where(
                    KgQueryFeedback.instance_id == self.instance_id,
                    KgQueryFeedback.succeeded == True,       # noqa: E712 — SQLAlchemy requires ==
                    KgQueryFeedback.created_at >= cutoff,
                    KgQueryFeedback.sql_final != "",
                ).group_by(
                    KgQueryFeedback.question,
                    KgQueryFeedback.sql_final,
                ).order_by(
                    sqlfunc.count(KgQueryFeedback.id).desc()
                ).limit(top_n)
            )
            return [(row.question, row.sql_final) for row in result.all()]

    async def _warm_one(
        self,
        utterance: str,
        sql: str,
        db_factory,
    ) -> None:
        """Execute one warm-up query and write results to cache layers 1 and 2."""
        from ai.engine.knowledge_graph.cache_store import QueryCacheStore
        from ai.engine.knowledge_graph.engine import ExecutionEngine
        from ai.engine.knowledge_graph.synthesis import ResponseSynthesizer

        engine = ExecutionEngine(self.instance_id)
        exec_result = await engine.execute(sql)
        if not exec_result.success:
            return

        # Minimal QueryOutcome-shaped object the synthesizer understands
        class _Outcome:
            succeeded = True
            retry_count = 0
            final_result = exec_result

        synthesizer = ResponseSynthesizer(llm_client=self.llm_client, model=self.model, instance_id=self.instance_id)
        synthesis = await synthesizer.synthesize(
            answer_text="",
            outcome=_Outcome(),
            question=utterance,
            plan=None,
        )

        store = QueryCacheStore()
        async with db_factory() as db:
            await store.set_query(
                sql=sql,
                instance_id=self.instance_id,
                synthesis=synthesis,
                db=db,
                utterance=utterance,
            )
            await store.set_semantic(
                utterance=utterance,
                instance_id=self.instance_id,
                synthesis=synthesis,
                db=db,
                sql_executed=sql,
            )
