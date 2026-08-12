"""
SkillRegistry — thin async CRUD wrapper around the Skill ORM model.

Owned by PR-18. No tool wiring, no agent integration — pure storage layer.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.clock import utcnow
from ai.engine.core.models import Skill

logger = logging.getLogger("pulse.skills.registry")


class SkillRegistry:
    """Async CRUD for the Skill table. Stores an AsyncSession per instance."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────────────────────────────────────

    async def add(self, skill_data: dict) -> Skill:
        """Insert a new skill and return the persisted row."""
        logger.debug("Adding skill: name=%r instance_id=%r", skill_data.get("name"), skill_data.get("instance_id"))
        skill = Skill(**skill_data)
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)
        logger.info("Skill created: id=%s name=%r", skill.id, skill.name)
        return skill

    # ── Read ────────────────────────────────────────────────────────────────

    async def get(self, skill_id: str) -> Skill | None:
        """Retrieve a single skill by primary key."""
        logger.debug("SkillRegistry.get: id=%s", skill_id)
        result = await self.db.execute(select(Skill).where(Skill.id == skill_id))
        return result.scalar_one_or_none()

    async def list_by_user(self, instance_id: str, author_user_id: str) -> list[Skill]:
        """Return all skills authored by a given user (any status)."""
        logger.debug("SkillRegistry.list_by_user: instance_id=%s author=%s", instance_id, author_user_id)
        result = await self.db.execute(
            select(Skill)
            .where(Skill.instance_id == instance_id, Skill.author_user_id == author_user_id)
            .order_by(Skill.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_promoted(self, instance_id: str, kind: str | None = None) -> list[Skill]:
        """Return instance-promoted skills, optionally filtered by kind."""
        logger.debug("SkillRegistry.list_promoted: instance_id=%s kind=%s", instance_id, kind)
        conditions = [Skill.instance_id == instance_id, Skill.status == "instance_promoted"]
        if kind is not None:
            conditions.append(Skill.kind == kind)
        result = await self.db.execute(
            select(Skill).where(*conditions).order_by(Skill.promoted_at.desc())
        )
        return list(result.scalars().all())

    async def search(self, instance_id: str, author_user_id: str, query: str) -> list[Skill]:
        """LIKE search across name and description, scoped to user's own + promoted."""
        logger.debug("SkillRegistry.search: instance_id=%s author=%s query=%r", instance_id, author_user_id, query)
        like_term = f"%{query}%"
        own_or_promoted = or_(
            Skill.author_user_id == author_user_id,
            Skill.status == "instance_promoted",
        )
        name_or_desc = or_(
            Skill.name.ilike(like_term),
            Skill.description.ilike(like_term),
        )
        result = await self.db.execute(
            select(Skill)
            .where(Skill.instance_id == instance_id, own_or_promoted, name_or_desc)
            .order_by(Skill.status == "instance_promoted", Skill.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Update ──────────────────────────────────────────────────────────────

    async def update_status(
        self, skill_id: str, new_status: str, promoted_by: str | None = None
    ) -> Skill | None:
        """Transition a skill's status. When promoting to instance_promoted,
        sets promoted_at and promoted_by."""
        logger.debug(
            "SkillRegistry.update_status: id=%s new_status=%s promoted_by=%s",
            skill_id, new_status, promoted_by,
        )
        skill = await self.get(skill_id)
        if skill is None:
            logger.warning("SkillRegistry.update_status: skill not found id=%s", skill_id)
            return None

        skill.status = new_status
        if new_status == "instance_promoted":
            skill.promoted_at = utcnow()
            skill.promoted_by = promoted_by

        await self.db.commit()
        await self.db.refresh(skill)
        logger.info("Skill status updated: id=%s status=%s", skill.id, skill.status)
        return skill
