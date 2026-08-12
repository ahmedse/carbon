"""
Memory manager — unified retrieval across short-term, long-term, and episodic memory.
This is what the agent calls before each LLM invocation to get relevant context.
"""
import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.memory.short_term import ShortTermMemory
from ai.engine.memory.long_term import LongTermMemory
from ai.engine.memory.episodic import EpisodicMemory

logger = logging.getLogger("pulse.memory.manager")


@dataclass
class MemoryContext:
    """Combined memory context for agent reasoning."""

    recent_messages: list[dict] = field(default_factory=list)
    relevant_facts: list[dict] = field(default_factory=list)
    relevant_episodes: list[dict] = field(default_factory=list)
    active_insights: list[dict] = field(default_factory=list)  # Phase C: cognition insights

    def to_prompt_text(self) -> str:
        """Format memory context as text for the system prompt."""
        parts = []

        HARD_CONSTRAINT_CATEGORIES = {"business_rule", "correction"}

        mandatory = [
            f for f in self.relevant_facts
            if f.get("category") in HARD_CONSTRAINT_CATEGORIES
        ]
        context_facts = [
            f for f in self.relevant_facts
            if f.get("category") not in HARD_CONSTRAINT_CATEGORIES
        ]

        if mandatory:
            parts.append("MANDATORY CONSTRAINTS — apply these before responding; they override any tool output:")
            for fact in mandatory:
                parts.append(f"- {fact['content']}")

        if context_facts:
            if parts:
                parts.append("")
            parts.append("Known context:")
            for fact in context_facts:
                confidence_label = ""
                if fact.get("confidence", 1.0) < 0.5:
                    confidence_label = " (low confidence)"
                parts.append(
                    f"- [{fact['category']}]{confidence_label} {fact['content']}"
                )

        if self.relevant_episodes:
            parts.append("\nRecent events:")
            for ep in self.relevant_episodes:
                parts.append(f"- [{ep['event_type']}] {ep['summary']}")
                if ep.get("causal_chain"):
                    parts.append(f"  Cause: {ep['causal_chain'][:200]}")

        # Phase C: inject active insights from cognition synthesis
        if self.active_insights:
            parts.append("\nSystem intelligence (auto-generated insights):")
            for ins in self.active_insights:
                parts.append(
                    f"- [{ins.get('insight_type', 'insight')}] {ins['title']}: "
                    f"{ins['content'][:300]}"
                )

        if not parts:
            return "No memories available."

        return "\n".join(parts)


# Singleton short-term memory (in-process, shared across requests)
_short_term: ShortTermMemory | None = None


def get_short_term_memory() -> ShortTermMemory:
    global _short_term
    if _short_term is None:
        _short_term = ShortTermMemory()
    return _short_term


class MemoryManager:
    """Unified memory retrieval across all three memory types."""

    def __init__(self, db_session: AsyncSession):
        self.short_term = get_short_term_memory()
        self.long_term = LongTermMemory(db_session)
        self.episodic = EpisodicMemory(db_session)

    async def retrieve_relevant_context(
        self,
        instance_id: str,
        conversation_id: str,
        user_message: str,
        max_tokens: int = 4096,
        user_identifier: str | None = None,
        host_user_id: str | None = None,
    ) -> MemoryContext:
        """
        Gather relevant context from all memory systems:
        1. Short-term: recent conversation messages (token-budgeted)
        2. Long-term: semantically relevant facts (tenancy-filtered)
        3. Episodic: relevant past events (tenancy-filtered)
        4. Insights: active instance insights (tenancy-filtered)
        """
        # 1. Short-term context
        recent = self.short_term.get_context_window(
            conversation_id, max_tokens=max_tokens
        )

        # 2. Long-term facts — filtered by tenancy triplet
        facts = []
        try:
            facts = await self.long_term.get_relevant_facts(
                instance_id, user_message, top_k=5, host_user_id=host_user_id
            )
        except Exception as e:
            logger.warning(f"Long-term memory retrieval failed: {e}")

        # 3. Episodic events — filtered by tenancy triplet
        episodes = []
        try:
            episodes = await self.episodic.get_relevant_episodes(
                instance_id, user_message, top_k=3, host_user_id=host_user_id
            )
        except Exception as e:
            logger.warning(f"Episodic memory retrieval failed: {e}")

        # 4. Active insights from cognition synthesis (Phase C)
        insights = []
        try:
            insights = await self._get_active_insights(
                instance_id, host_user_id=host_user_id
            )
        except Exception as e:
            logger.debug(f"Insight retrieval failed (non-fatal): {e}")

        # 5. User-specific preferences
        effective_uid = host_user_id or user_identifier
        if effective_uid:
            try:
                user_prefs = await self._get_user_preferences(
                    instance_id, effective_uid, host_user_id=host_user_id
                )
                facts.extend(user_prefs)
            except Exception as e:
                logger.debug(f"User preference retrieval failed (non-fatal): {e}")

        return MemoryContext(
            recent_messages=recent,
            relevant_facts=facts,
            relevant_episodes=episodes,
            active_insights=insights,
        )

    async def learn_from_correction(
        self,
        instance_id: str,
        original_response: str,
        correction: str,
        message_id: str,
        host_user_id: str | None = None,
        user_question: str | None = None,
    ):
        """
        When a user corrects Pulse, store the correction as a long-term fact
        and record an episodic event.

        When ``user_question`` is provided, the stored fact is anchored on the
        triggering question so future similar questions deterministically
        retrieve this correction (keyword match runs over the fact content).
        This closes the learning loop for cases like an empty-result
        confabulation: the next time the same question is asked, the correction
        surfaces before the model can repeat the mistake.
        """
        _q = (user_question or "").strip()
        _anchor = f'For questions like "{_q[:160]}" — ' if _q else ""
        # Store as long-term correction (private to this user if host_user_id known)
        await self.long_term.store_fact(
            instance_id=instance_id,
            category="correction",
            content=(
                f"{_anchor}Correction: {correction} "
                f"(original response was about: {original_response[:100]})"
            ),
            source=f"user_feedback:{message_id}",
            confidence=0.95,
            host_user_id=host_user_id,
            visibility="private" if host_user_id else "shared",
        )

        # Record as episodic event
        await self.episodic.record_event(
            instance_id=instance_id,
            event_type="user_correction",
            summary=f"User corrected response: {correction[:100]}",
            details={
                "message_id": message_id,
                "original_response_excerpt": original_response[:200],
                "correction": correction,
                "user_question": _q[:300] or None,
            },
            host_user_id=host_user_id,
            visibility="private" if host_user_id else "shared",
        )

        logger.info(f"Learned from correction on message {message_id}")

    def track_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ):
        """Track a message in short-term memory."""
        self.short_term.add_message(conversation_id, role, content, metadata)

    def end_conversation(self, conversation_id: str):
        """Clear short-term memory for a finished conversation."""
        self.short_term.clear(conversation_id)

    async def _get_active_insights(
        self,
        instance_id: str,
        limit: int = 3,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """
        Fetch the most recent non-archived insights for this instance
        from BOTH Insight (cognition synthesis) and KgProactiveInsight
        (proactive triggers). Proactive insights are adapted into the
        same context dict shape and tagged by source.

        These are injected into the agent's context so it can use them.
        Closes the split-brain (B5): agent memory context now sees proactive insights.
        Results are filtered by the tenancy triplet.
        """
        from sqlalchemy import select, desc
        from ai.engine.core.models import Insight, _apply_tenancy_filter
        from ai.engine.knowledge_graph.models import KgProactiveInsight

        # ── Channel A: cognition-synthesized Insight rows ──
        base_stmt_a = (
            select(Insight)
            .where(Insight.archived == False)
            .where(Insight.confidence >= 0.5)
            .order_by(desc(Insight.created_at))
            .limit(limit)
        )
        stmt_a = _apply_tenancy_filter(base_stmt_a, Insight, instance_id, host_user_id)
        result_a = await self.long_term.db.execute(stmt_a)
        cognition_insights = [
            {
                "insight_type": r.insight_type,
                "title": r.title,
                "content": r.content,
                "confidence": r.confidence,
                "source": "cognition",
                "created_at": r.created_at,
            }
            for r in result_a.scalars().all()
        ]

        # ── Channel B: proactive KgProactiveInsight rows (adapt into same shape) ──
        # severity → confidence mapping: critical=0.95, warning=0.80, info=0.60
        _severity_confidence = {"critical": 0.95, "warning": 0.80, "info": 0.60}
        base_stmt_b = (
            select(KgProactiveInsight)
            .where(KgProactiveInsight.instance_id == instance_id)
            .where(KgProactiveInsight.disposition == "pending")
            .order_by(desc(KgProactiveInsight.created_at))
            .limit(limit)
        )
        result_b = await self.long_term.db.execute(base_stmt_b)
        proactive_insights = [
            {
                "insight_type": r.insight_type,
                "title": r.title,
                "content": r.narrative,
                "confidence": _severity_confidence.get(r.severity, 0.60),
                "source": "proactive",
                "created_at": r.created_at,
            }
            for r in result_b.scalars().all()
        ]

        # ── Merge both channels, sort by confidence desc then recency desc ──
        merged = cognition_insights + proactive_insights
        merged.sort(key=lambda x: (x["confidence"], x["created_at"]), reverse=True)
        # Strip created_at from final output (internal sort key only)
        return [
            {
                "insight_type": i["insight_type"],
                "title": i["title"],
                "content": i["content"],
                "confidence": i["confidence"],
                "source": i["source"],
            }
            for i in merged[:limit]
        ]

    async def _get_user_preferences(
        self,
        instance_id: str,
        user_identifier: str,
        host_user_id: str | None = None,
    ) -> list[dict]:
        """Retrieve auto-learned preferences for a specific user."""
        from ai.engine.core.models import MemoryLongTerm, _apply_tenancy_filter

        base_stmt = (
            select(MemoryLongTerm)
            .where(
                MemoryLongTerm.category == "preference",
                MemoryLongTerm.source == f"auto:user:{user_identifier}",
                MemoryLongTerm.archived == False,
            )
            .limit(3)
        )
        stmt = _apply_tenancy_filter(
            base_stmt, MemoryLongTerm, instance_id, host_user_id
        )
        result = await self.long_term.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "category": r.category,
                "content": r.content,
                "source": r.source,
                "confidence": r.confidence,
                "use_count": r.use_count,
            }
            for r in rows
        ]
