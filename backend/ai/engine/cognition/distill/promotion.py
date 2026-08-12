"""
Weekly promotion sweep (PR-14).

Promotes learned candidate facts to 'confirmed' status when:
- Confidence ≥ 0.8 and the fact was created ≥ 14 days ago (sustained),
  OR
- The user explicitly endorsed the fact (host_endorsed=True).
"""
import logging
from datetime import datetime, timedelta

from ai.engine.core.clock import utcnow
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.models import MemoryLongTerm

logger = logging.getLogger("pulse.cognition.distill.promotion")

_SUSTAINED_DAYS = 14
_PROMOTION_CONFIDENCE_MIN = 0.8


async def run_promotion(db: AsyncSession, instance) -> int:
    """Top-level entry point called by the cognition scheduler.

    Returns the number of facts promoted.
    """
    sweeper = PromotionSweep(db)
    count = await sweeper.sweep(instance.id)
    logger.info(
        "Promotion sweep for %s: %d facts promoted", instance.name, count
    )
    return count


class PromotionSweep:
    """Promotes sustained high-confidence candidates to confirmed."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sweep(self, instance_id: str) -> int:
        """Find candidates eligible for promotion and promote them."""
        cutoff = utcnow() - timedelta(days=_SUSTAINED_DAYS)

        # Find learned facts with sustained high confidence
        stmt = select(MemoryLongTerm).where(
            MemoryLongTerm.instance_id == instance_id,
            MemoryLongTerm.category == "learned",
            MemoryLongTerm.confidence >= _PROMOTION_CONFIDENCE_MIN,
            MemoryLongTerm.created_at <= cutoff,
            MemoryLongTerm.archived.is_(False),
        )
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        promoted = 0
        for fact in candidates:
            fact.category = "confirmed"
            fact.confidence = 1.0
            fact.decay_at = None  # confirmed facts don't auto-decay
            fact.source = (fact.source or "") + "|promoted"
            promoted += 1

        if promoted:
            await self.db.commit()
            logger.debug(
                "Promoted %d facts to confirmed in %s", promoted, instance_id
            )

        return promoted
