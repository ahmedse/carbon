"""
Monthly fact decay sweep (PR-14).

Reduces confidence on learned facts whose decay_at has passed.
Facts that fall below the archival threshold (0.1) are archived.
Confirmed facts are NOT decayed (they've passed promotion).
"""
import logging

from ai.engine.core.clock import utcnow
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.models import MemoryLongTerm

logger = logging.getLogger("pulse.cognition.distill.decay")

_DECAY_AMOUNT = 0.05
_ARCHIVE_THRESHOLD = 0.1


async def run_decay(db: AsyncSession, instance) -> int:
    """Top-level entry point called by the cognition scheduler.

    Returns the number of facts decayed.
    """
    sweeper = DecaySweep(db)
    count = await sweeper.sweep(instance.id)
    logger.info(
        "Decay sweep for %s: %d facts decayed", instance.name, count
    )
    return count


class DecaySweep:
    """Decays confidence on eligible learned facts, archiving those that drop too low."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sweep(self, instance_id: str) -> int:
        """Decay facts whose decay_at has passed."""
        now = utcnow()

        # Find learned facts past their decay_at date
        stmt = select(MemoryLongTerm).where(
            MemoryLongTerm.instance_id == instance_id,
            MemoryLongTerm.category == "learned",
            MemoryLongTerm.decay_at.isnot(None),
            MemoryLongTerm.decay_at <= now,
            MemoryLongTerm.archived.is_(False),
        )
        result = await self.db.execute(stmt)
        facts = result.scalars().all()

        decayed = 0
        archived = 0
        for fact in facts:
            new_confidence = fact.confidence - _DECAY_AMOUNT
            if new_confidence < _ARCHIVE_THRESHOLD:
                fact.archived = True
                fact.confidence = 0.0
                archived += 1
                logger.debug("Archiving fact %s (confidence dropped below %.2f)",
                             fact.id, _ARCHIVE_THRESHOLD)
            else:
                fact.confidence = new_confidence
                decayed += 1

        if decayed or archived:
            await self.db.commit()
            logger.debug(
                "Decay sweep done: %d decayed, %d archived in %s",
                decayed, archived, instance_id,
            )

        return decayed + archived
