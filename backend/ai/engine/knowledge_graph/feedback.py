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

from ai.engine.core.clock import utcnow
from ai.store import first

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
    db,
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
    from ai.models.core import Message

    window_sec = get_settings().KG_FEEDBACK_REPHRASE_WINDOW_SEC

    user_messages = await db.select(
        Message,
        ("conversation_id", conversation_id),
        ("role", "user"),
    )
    user_messages.sort(key=lambda m: m.timestamp or datetime.min, reverse=True)
    recent = user_messages[:2]

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
    db,
    conversation_id: str,
) -> bool:
    """
    Detect if a conversation was abandoned after a single exchange.
    True if the conversation has exactly 1 user message and 1 assistant
    message, and the assistant's message is the last one.
    """
    from ai.models.core import Message

    messages = await db.select(Message, ("conversation_id", conversation_id))
    messages.sort(key=lambda m: m.timestamp or datetime.min)

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
    db,
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
    from ai.models.knowledge_graph import KgFeedbackRecord, KgGoldenPair

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
    # Flush so rec.id is populated before the golden pair references it.
    await db.flush()

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
        db,
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
        from ai.models.knowledge_graph import KnowledgeNode

        nodes = await db.select(
            KnowledgeNode,
            ("instance_id", self.instance_id),
            ("node_type", "ENTITY"),
        )
        node = None
        term_lower = term.lower()
        for candidate in nodes:
            if (candidate.name or "").lower() == term_lower:
                node = candidate
                break

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
        db,
        pair_id: str,
        reviewed_by: str = "system",
    ) -> bool:
        """
        Mark a KgGoldenPair as approved (making it available for few-shot).
        """
        from ai.models.knowledge_graph import KgGoldenPair

        pair = first(
            await db.select(
                KgGoldenPair,
                ("id", pair_id),
                ("instance_id", self.instance_id),
            )
        )
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
        db,
        limit: int = 20,
    ) -> list[dict]:
        """
        Fetch the most recent approved golden pairs for prompt injection.
        """
        from ai.models.knowledge_graph import KgGoldenPair

        pairs = await db.select(
            KgGoldenPair,
            ("instance_id", self.instance_id),
            ("review_status", "approved"),
        )
        pairs.sort(key=lambda p: p.reviewed_at or datetime.min, reverse=True)
        return [
            {"question": p.question, "sql": p.sql}
            for p in pairs[:limit]
        ]

    # ── Prompt tuning channel ─────────────────────────────────────────────────

    async def analyze_weak_spots(
        self,
        db,
        lookback_days: int = 7,
) -> list[dict]:
        """
        Identify query classes with disproportionately high error rates.
        Returns a list of {"signal_type": ..., "avg_score": ..., "count": ...}
        sorted by avg_score ascending (weakest first).
        """
        from ai.models.knowledge_graph import KgFeedbackRecord

        cutoff = utcnow() - timedelta(days=lookback_days)

        records = await db.select(
            KgFeedbackRecord,
            ("instance_id", self.instance_id),
            ("created_at__gte", cutoff),
        )
        grouped: dict[str, list[float]] = {}
        for rec in records:
            grouped.setdefault(rec.signal_type, []).append(rec.quality_score or 0.0)

        result = []
        for signal_type, scores in grouped.items():
            if len(scores) < 3:
                continue
            result.append({
                "signal_type": signal_type,
                "avg_score": round(sum(scores) / len(scores), 3),
                "count": len(scores),
            })
        result.sort(key=lambda row: row["avg_score"])
        return result

    async def compute_daily_quality(
        self,
        db,
        date_str: str,
    ) -> float:
        """
        Compute the average quality score for a given date (YYYY-MM-DD).
        Writes a KgQualityScore row for dimension='overall'.
        Returns the score (0.0–1.0), or the neutral default if no data.
        """
        from ai.engine.core.config import get_settings
        from ai.models.knowledge_graph import KgFeedbackRecord, KgQualityScore

        neutral = get_settings().KG_FEEDBACK_QUALITY_NEUTRAL

        day_start = datetime.strptime(date_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)

        records = await db.select(
            KgFeedbackRecord,
            ("instance_id", self.instance_id),
            ("created_at__gte", day_start),
            ("created_at__lt", day_end),
        )
        scores = [rec.quality_score or 0.0 for rec in records]
        avg_score = (sum(scores) / len(scores)) if scores else neutral
        sample_count = len(scores)

        # Upsert quality score
        existing = first(
            await db.select(
                KgQualityScore,
                ("instance_id", self.instance_id),
                ("dimension", "overall"),
                ("date", date_str),
            )
        )
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
        db,
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
        from ai.models.knowledge_graph import KgReviewItem

        # Check for existing pending item with same title/category
        existing = first(
            await db.select(
                KgReviewItem,
                ("instance_id", self.instance_id),
                ("category", category),
                ("title", title),
                ("status", "pending"),
            )
        )

        if existing:
            existing.frequency += 1
            # Append new evidence (JSONField round-trip: may be str or list)
            ev_list = existing.evidence_json
            if isinstance(ev_list, str):
                try:
                    ev_list = json.loads(ev_list)
                except (json.JSONDecodeError, TypeError):
                    ev_list = []
            elif not isinstance(ev_list, list):
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
        db,
        limit: int = 50,
    ) -> list[dict]:
        """
        List pending review items sorted by frequency (highest first).
        """
        from ai.models.knowledge_graph import KgReviewItem

        items = await db.select(
            KgReviewItem,
            ("instance_id", self.instance_id),
            ("status", "pending"),
        )
        items.sort(key=lambda i: (i.frequency or 0, i.created_at or datetime.min), reverse=True)
        items = items[:limit]
        result = []
        for i in items:
            ev = i.evidence_json
            if isinstance(ev, str):
                try:
                    ev = json.loads(ev)
                except (json.JSONDecodeError, TypeError):
                    ev = []
            elif not isinstance(ev, list):
                ev = []
            result.append({
                "id": i.id,
                "category": i.category,
                "title": i.title,
                "description": i.description,
                "frequency": i.frequency,
                "evidence": ev,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            })
        return result

    async def resolve(
        self,
        db,
        item_id: str,
        status: str,           # "approved" | "rejected"
        reviewed_by: str = "",
        resolution: str = "",
    ) -> bool:
        """
        Mark a review item as approved or rejected.
        Returns True if the item was found and updated.
        """
        from ai.models.knowledge_graph import KgReviewItem

        item = first(
            await db.select(
                KgReviewItem,
                ("id", item_id),
                ("instance_id", self.instance_id),
            )
        )
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

    async def pending_count(self, db) -> int:
        """Count pending review items for this instance."""
        from ai.models.knowledge_graph import KgReviewItem

        stats = await db.aggregate(
            KgReviewItem,
            {"n": ("Count", "id")},
            ("instance_id", self.instance_id),
            ("status", "pending"),
        )
        return stats.get("n") or 0


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
        db,
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
        from ai.models.knowledge_graph import KgQualityScore

        settings = get_settings()
        threshold = settings.KG_FEEDBACK_DRIFT_THRESHOLD
        window = settings.KG_FEEDBACK_DRIFT_WINDOW_DAYS

        cutoff = (utcnow() - timedelta(days=window)).strftime("%Y-%m-%d")

        rows = await db.select(
            KgQualityScore,
            ("instance_id", self.instance_id),
            ("dimension", dimension),
            ("date__gte", cutoff),
        )
        scores = [r.score or 0.0 for r in rows]
        rolling_avg = (sum(scores) / len(scores)) if scores else 1.0
        sample_count = len(scores)

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
        db,
        dimension: str = "overall",
        days: int = 30,
    ) -> list[dict]:
        """
        Return daily quality scores for the last *days* days.
        Used for the quality score trend chart.
        """
        from ai.models.knowledge_graph import KgQualityScore

        cutoff = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        rows = await db.select(
            KgQualityScore,
            ("instance_id", self.instance_id),
            ("dimension", dimension),
            ("date__gte", cutoff),
        )
        rows.sort(key=lambda r: r.date or "")
        return [
            {
                "date": row.date,
                "score": round(float(row.score), 3),
                "sample_count": row.sample_count,
            }
            for row in rows
        ]
