"""
Feedback — Stage 11.

Signal detection, quality scoring, and feedback record creation.

Captures both explicit signals (thumbs up/down, corrections, SQL edits)
and implicit signals (rephrases, contradictions, abandonments, exports).

Quality scoring:
  explicit_positive  → 1.0
  export             → 0.9
  (no signal)        → 0.7  (neutral)
  rephrase           → 0.3
  explicit_negative  → 0.1
  correction         → 0.0  (for the original; the correction itself is 1.0)
  contradiction      → 0.2
  abandonment        → 0.2
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.clock import utcnow

logger = logging.getLogger("pulse.knowledge_graph.feedback")


# ── Quality score map ─────────────────────────────────────────────────────────

_SIGNAL_SCORES: dict[str, float] = {
    "explicit_positive": 1.0,
    "export":            0.9,
    "explicit_negative": 0.1,
    "correction":        0.0,
    "rephrase":          0.3,
    "contradiction":     0.2,
    "abandonment":       0.2,
}


def quality_score_for(signal_type: str) -> float:
    """Return the quality score for a given signal type."""
    from ai.engine.core.config import get_settings
    return _SIGNAL_SCORES.get(signal_type, get_settings().KG_FEEDBACK_QUALITY_NEUTRAL)


# ── Signal detection ──────────────────────────────────────────────────────────

async def detect_rephrase(
    db: AsyncSession,
    conversation_id: str,
    current_utterance: str,
    current_time: datetime,
) -> bool:
    """
    Detect if the current utterance is a rephrase of the immediately
    preceding user message (same conversation, within the rephrase window).

    Heuristic: if the previous user message shares ≥ 50% of significant words
    with the current one, and it arrived within the window.
    """
    from ai.engine.core.config import get_settings
    from ai.engine.core.models import Message

    window_sec = get_settings().KG_FEEDBACK_REPHRASE_WINDOW_SEC

    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == "user",
        )
        .order_by(desc(Message.timestamp))
        .limit(2)
    )
    result = await db.execute(stmt)
    recent = result.scalars().all()

    if len(recent) < 2:
        return False

    prev_msg = recent[1]  # second most recent
    prev_time = prev_msg.timestamp
    if prev_time.tzinfo is None:
        prev_time = prev_time.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    if (current_time - prev_time) > timedelta(seconds=window_sec):
        return False

    return _word_overlap(prev_msg.content, current_utterance) >= 0.5


async def detect_abandonment(
    db: AsyncSession,
    conversation_id: str,
) -> bool:
    """
    Detect if a conversation was abandoned after a single exchange.
    True if the conversation has exactly 1 user message and 1 assistant
    message, and the assistant's message is the last one.
    """
    from ai.engine.core.models import Message

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    if len(messages) < 2 or len(messages) > 3:
        return False

    roles = [m.role for m in messages]
    return roles[-1] == "assistant" and roles.count("user") == 1


def detect_contradiction(user_message: str) -> bool:
    """
    Simple heuristic: does the user message contain phrases that suggest
    the prior answer was wrong?
    """
    lower = user_message.lower()
    markers = [
        "that doesn't seem right",
        "that's not right",
        "that's wrong",
        "are you sure",
        "that can't be",
        "i don't think so",
        "incorrect",
        "not correct",
        "that's not what i",
        "no, i meant",
        "that's inaccurate",
    ]
    return any(m in lower for m in markers)


# ── Record creation ───────────────────────────────────────────────────────────

async def record_feedback(
    db: AsyncSession,
    *,
    instance_id: str,
    conversation_id: str,
    message_id: str = "",
    signal_type: str,
    user_id: str = "",
    original_utterance: str = "",
    resolved_utterance: str = "",
    generated_sql: str = "",
    corrected_sql: Optional[str] = None,
    user_comment: Optional[str] = None,
) -> str:
    """
    Create a KgFeedbackRecord and return its ID.
    Also creates a candidate golden pair if the signal is a correction
    with corrected_sql provided.
    """
    from ai.engine.knowledge_graph.models import KgFeedbackRecord, KgGoldenPair

    score = quality_score_for(signal_type)

    rec = KgFeedbackRecord(
        instance_id=instance_id,
        conversation_id=conversation_id,
        message_id=message_id,
        signal_type=signal_type,
        user_id=user_id,
        original_utterance=original_utterance[:1000],
        resolved_utterance=resolved_utterance[:1000],
        generated_sql=generated_sql[:2000],
        corrected_sql=corrected_sql[:2000] if corrected_sql else None,
        user_comment=user_comment[:1000] if user_comment else None,
        quality_score=score,
    )
    db.add(rec)

    # Auto-create candidate golden pair from corrections
    if signal_type == "correction" and corrected_sql:
        question = resolved_utterance or original_utterance
        if question:
            pair = KgGoldenPair(
                instance_id=instance_id,
                question=question[:1000],
                sql=corrected_sql[:2000],
                source_feedback_id=rec.id,
                review_status="pending",
            )
            db.add(pair)

    await db.commit()
    logger.info(
        "feedback recorded  instance=%s  signal=%s  score=%.1f  conv=%s",
        instance_id, signal_type, score, conversation_id[:8],
    )
    return rec.id


# ── Helpers ───────────────────────────────────────────────────────────────────

def _word_overlap(text_a: str, text_b: str) -> float:
    """Jaccard-like overlap of significant words (length ≥ 3)."""
    words_a = {w.lower() for w in text_a.split() if len(w) >= 3}
    words_b = {w.lower() for w in text_b.split() if len(w) >= 3}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


logger = logging.getLogger("pulse.knowledge_graph.feedback")


class FeedbackLearner:
    """
    Processes approved review items and applies them to the appropriate
    learning channel.
    """

    def __init__(self, instance_id: str):
        self.instance_id = instance_id

    # ── Synonym channel ───────────────────────────────────────────────────────

    async def apply_synonym(
        self,
        db: AsyncSession,
        term: str,
        synonym: str,
        source_review_id: Optional[str] = None,
    ) -> bool:
        """
        Add a synonym mapping to the knowledge graph.
        Finds the ENTITY node for *term* and appends *synonym* to its
        properties.synonyms list.
        Returns True if the node was found and updated.
        """
        from ai.engine.knowledge_graph.models import KnowledgeNode

        stmt = (
            select(KnowledgeNode)
            .where(
                KnowledgeNode.instance_id == self.instance_id,
                KnowledgeNode.node_type == "ENTITY",
                sa_func.lower(KnowledgeNode.name) == term.lower(),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        node = result.scalar_one_or_none()

        if not node:
            logger.debug("apply_synonym: no ENTITY node for %r", term)
            return False

        try:
            props = json.loads(node.properties) if node.properties else {}
        except (json.JSONDecodeError, TypeError):
            props = {}

        existing = props.get("synonyms", [])
        if synonym.lower() not in {s.lower() for s in existing}:
            existing.append(synonym)
            props["synonyms"] = existing
            node.properties = json.dumps(props)
            await db.commit()
            logger.info(
                "synonym added  term=%r  synonym=%r  instance=%s",
                term, synonym, self.instance_id,
            )
        return True

    # ── Golden pair channel ───────────────────────────────────────────────────

    async def promote_golden_pair(
        self,
        db: AsyncSession,
        pair_id: str,
        reviewed_by: str = "system",
    ) -> bool:
        """
        Mark a KgGoldenPair as approved (making it available for few-shot).
        """
        from ai.engine.knowledge_graph.models import KgGoldenPair

        stmt = select(KgGoldenPair).where(
            KgGoldenPair.id == pair_id,
            KgGoldenPair.instance_id == self.instance_id,
        )
        result = await db.execute(stmt)
        pair = result.scalar_one_or_none()
        if not pair:
            return False

        pair.review_status = "approved"
        pair.reviewed_by = reviewed_by
        pair.reviewed_at = utcnow()
        await db.commit()
        logger.info("golden pair approved  id=%s  instance=%s", pair_id, self.instance_id)
        return True

    async def get_approved_pairs(
        self,
        db: AsyncSession,
        limit: int = 20,
    ) -> list[dict]:
        """
        Fetch the most recent approved golden pairs for prompt injection.
        """
        from ai.engine.knowledge_graph.models import KgGoldenPair

        stmt = (
            select(KgGoldenPair)
            .where(
                KgGoldenPair.instance_id == self.instance_id,
                KgGoldenPair.review_status == "approved",
            )
            .order_by(KgGoldenPair.reviewed_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        pairs = result.scalars().all()
        return [
            {"question": p.question, "sql": p.sql}
            for p in pairs
        ]

    # ── Prompt tuning channel ─────────────────────────────────────────────────

    async def analyze_weak_spots(
        self,
        db: AsyncSession,
        lookback_days: int = 7,
    ) -> list[dict]:
        """
        Identify query classes with disproportionately high error rates.
        Returns a list of {"error_category": ..., "avg_score": ..., "count": ...}
        sorted by avg_score ascending (weakest first).
        """
        from ai.engine.knowledge_graph.models import KgFeedbackRecord

        cutoff = utcnow() - timedelta(days=lookback_days)

        stmt = (
            select(
                KgFeedbackRecord.signal_type,
                sa_func.avg(KgFeedbackRecord.quality_score).label("avg_score"),
                sa_func.count().label("count"),
            )
            .where(
                KgFeedbackRecord.instance_id == self.instance_id,
                KgFeedbackRecord.created_at >= cutoff,
            )
            .group_by(KgFeedbackRecord.signal_type)
            .having(sa_func.count() >= 3)
            .order_by(sa_func.avg(KgFeedbackRecord.quality_score))
        )
        result = await db.execute(stmt)
        return [
            {
                "signal_type": row.signal_type,
                "avg_score": round(float(row.avg_score), 3),
                "count": row.count,
            }
            for row in result
        ]

    # ── Aggregate quality scoring ─────────────────────────────────────────────

    async def compute_daily_quality(
        self,
        db: AsyncSession,
        date_str: str,
    ) -> float:
        """
        Compute the average quality score for a given date (YYYY-MM-DD).
        Writes a KgQualityScore row for dimension='overall'.
        Returns the score (0.0–1.0), or the neutral default if no data.
        """
        from ai.engine.core.config import get_settings
        from ai.engine.knowledge_graph.models import KgFeedbackRecord, KgQualityScore

        neutral = get_settings().KG_FEEDBACK_QUALITY_NEUTRAL

        stmt = (
            select(
                sa_func.avg(KgFeedbackRecord.quality_score).label("avg"),
                sa_func.count().label("n"),
            )
            .where(
                KgFeedbackRecord.instance_id == self.instance_id,
                sa_func.date(KgFeedbackRecord.created_at) == date_str,
            )
        )
        result = await db.execute(stmt)
        row = result.one_or_none()

        avg_score = float(row.avg) if row and row.avg is not None else neutral
        sample_count = row.n if row else 0

        # Upsert quality score
        existing_stmt = select(KgQualityScore).where(
            KgQualityScore.instance_id == self.instance_id,
            KgQualityScore.dimension == "overall",
            KgQualityScore.date == date_str,
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            existing.score = avg_score
            existing.sample_count = sample_count
        else:
            qs = KgQualityScore(
                instance_id=self.instance_id,
                dimension="overall",
                dimension_value="all",
                date=date_str,
                score=avg_score,
                sample_count=sample_count,
            )
            db.add(qs)
        await db.commit()
        return avg_score


# ReviewQueue
# ══════════════════════════════════════════════════════════════════════════════

class ReviewQueue:
    """
    Create, query, and resolve review items.
    Items are created automatically from feedback signals and grouped
    by similarity (same utterance pattern or same correction target).
    """

    def __init__(self, instance_id: str):
        self.instance_id = instance_id

    async def add_item(
        self,
        db: AsyncSession,
        *,
        category: str,
        title: str,
        description: str = "",
        evidence: list[dict] | None = None,
    ) -> str:
        """
        Add a new review item, or increment the frequency of an existing
        item with the same title + category.
        Returns the item ID.
        """
        from ai.engine.knowledge_graph.models import KgReviewItem

        # Check for existing pending item with same title/category
        stmt = select(KgReviewItem).where(
            KgReviewItem.instance_id == self.instance_id,
            KgReviewItem.category == category,
            KgReviewItem.title == title,
            KgReviewItem.status == "pending",
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.frequency += 1
            # Append new evidence
            try:
                ev_list = json.loads(existing.evidence_json)
            except (json.JSONDecodeError, TypeError):
                ev_list = []
            if evidence:
                ev_list.extend(evidence)
                ev_list = ev_list[-20:]  # keep last 20
            existing.evidence_json = json.dumps(ev_list)
            await db.commit()
            return existing.id

        item = KgReviewItem(
            instance_id=self.instance_id,
            category=category,
            title=title,
            description=description,
            evidence_json=json.dumps(evidence or []),
            frequency=1,
            status="pending",
        )
        db.add(item)
        await db.commit()
        return item.id

    async def list_pending(
        self,
        db: AsyncSession,
        limit: int = 50,
    ) -> list[dict]:
        """
        List pending review items sorted by frequency (highest first).
        """
        from ai.engine.knowledge_graph.models import KgReviewItem

        stmt = (
            select(KgReviewItem)
            .where(
                KgReviewItem.instance_id == self.instance_id,
                KgReviewItem.status == "pending",
            )
            .order_by(KgReviewItem.frequency.desc(), KgReviewItem.created_at)
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        return [
            {
                "id": i.id,
                "category": i.category,
                "title": i.title,
                "description": i.description,
                "frequency": i.frequency,
                "evidence": json.loads(i.evidence_json) if i.evidence_json else [],
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]

    async def resolve(
        self,
        db: AsyncSession,
        item_id: str,
        status: str,           # "approved" | "rejected"
        reviewed_by: str = "",
        resolution: str = "",
    ) -> bool:
        """
        Mark a review item as approved or rejected.
        Returns True if the item was found and updated.
        """
        from ai.engine.knowledge_graph.models import KgReviewItem

        stmt = select(KgReviewItem).where(
            KgReviewItem.id == item_id,
            KgReviewItem.instance_id == self.instance_id,
        )
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            return False

        item.status = status
        item.reviewed_by = reviewed_by
        item.resolution = resolution
        await db.commit()
        logger.info(
            "review item resolved  id=%s  status=%s  by=%s",
            item_id, status, reviewed_by,
        )
        return True

    async def pending_count(self, db: AsyncSession) -> int:
        """Count pending review items for this instance."""
        from ai.engine.knowledge_graph.models import KgReviewItem

        stmt = select(sa_func.count()).where(
            KgReviewItem.instance_id == self.instance_id,
            KgReviewItem.status == "pending",
        )
        result = await db.execute(stmt)
        return result.scalar() or 0


# ══════════════════════════════════════════════════════════════════════════════
# DriftDetector
# ══════════════════════════════════════════════════════════════════════════════

class DriftDetector:
    """
    Monitors rolling quality scores and detects drift.
    """

    def __init__(self, instance_id: str):
        self.instance_id = instance_id

    async def check_drift(
        self,
        db: AsyncSession,
        dimension: str = "overall",
    ) -> dict:
        """
        Check if the rolling quality score for *dimension* has drifted
        below the configured threshold.

        Returns:
            {
                "drifting": bool,
                "rolling_avg": float,
                "threshold": float,
                "window_days": int,
                "sample_count": int,
            }
        """
        from ai.engine.core.config import get_settings
        from ai.engine.knowledge_graph.models import KgQualityScore

        settings = get_settings()
        threshold = settings.KG_FEEDBACK_DRIFT_THRESHOLD
        window = settings.KG_FEEDBACK_DRIFT_WINDOW_DAYS

        cutoff = (utcnow() - timedelta(days=window)).strftime("%Y-%m-%d")

        stmt = (
            select(
                sa_func.avg(KgQualityScore.score).label("avg"),
                sa_func.count().label("n"),
            )
            .where(
                KgQualityScore.instance_id == self.instance_id,
                KgQualityScore.dimension == dimension,
                KgQualityScore.date >= cutoff,
            )
        )
        result = await db.execute(stmt)
        row = result.one_or_none()

        rolling_avg = float(row.avg) if row and row.avg is not None else 1.0
        sample_count = row.n if row else 0

        drifting = rolling_avg < threshold and sample_count >= 3

        if drifting:
            logger.warning(
                "DRIFT DETECTED  instance=%s  dimension=%s  "
                "rolling_avg=%.3f  threshold=%.3f  samples=%d",
                self.instance_id, dimension, rolling_avg, threshold, sample_count,
            )

        return {
            "drifting": drifting,
            "rolling_avg": round(rolling_avg, 3),
            "threshold": threshold,
            "window_days": window,
            "sample_count": sample_count,
        }

    async def get_quality_trend(
        self,
        db: AsyncSession,
        dimension: str = "overall",
        days: int = 30,
    ) -> list[dict]:
        """
        Return daily quality scores for the last *days* days.
        Used for the quality score trend chart.
        """
        from ai.engine.knowledge_graph.models import KgQualityScore

        cutoff = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        stmt = (
            select(
                KgQualityScore.date,
                KgQualityScore.score,
                KgQualityScore.sample_count,
            )
            .where(
                KgQualityScore.instance_id == self.instance_id,
                KgQualityScore.dimension == dimension,
                KgQualityScore.date >= cutoff,
            )
            .order_by(KgQualityScore.date)
        )
        result = await db.execute(stmt)
        return [
            {
                "date": row.date,
                "score": round(float(row.score), 3),
                "sample_count": row.sample_count,
            }
            for row in result
        ]
