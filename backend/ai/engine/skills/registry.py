"""
SkillRegistry — thin async CRUD wrapper around the Skill ORM model.

Owned by PR-18. No tool wiring, no agent integration — pure storage layer.
"""
import logging
from datetime import datetime, timezone

from ai.engine.core.models import Skill
from ai.engine.core.query import first, or_
from ai.engine.ports.store import Session
from ai.engine.skills._authority import assert_allowed_transition

logger = logging.getLogger("pulse.skills.registry")


def _dt_key(value):
    """Sort key for datetimes (None-safe)."""
    if value is None:
        return 0
    if isinstance(value, datetime):
        return value.timestamp()
    return 0


class SkillRegistry:
    """Async CRUD for the Skill table. Stores a Session per instance."""

    def __init__(self, db: Session):
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
        return first(await self.db.select(Skill, ("id", skill_id)))

    async def list_by_user(self, instance_id: str, author_user_id: str) -> list[Skill]:
        """Return all skills authored by a given user (any status)."""
        logger.debug("SkillRegistry.list_by_user: instance_id=%s author=%s", instance_id, author_user_id)
        rows = await self.db.select(
            Skill,
            ("instance_id", instance_id),
            ("author_user_id", author_user_id),
        )
        rows.sort(key=lambda s: _dt_key(s.created_at), reverse=True)
        return rows

    async def list_promoted(self, instance_id: str, kind: str | None = None) -> list[Skill]:
        """Return instance-promoted skills, optionally filtered by kind."""
        logger.debug("SkillRegistry.list_promoted: instance_id=%s kind=%s", instance_id, kind)
        filters: list = [
            ("instance_id", instance_id),
            ("status", "instance_promoted"),
        ]
        if kind is not None:
            filters.append(("kind", kind))
        rows = await self.db.select(Skill, *filters)
        rows.sort(key=lambda s: _dt_key(s.promoted_at), reverse=True)
        return rows

    async def search(self, instance_id: str, author_user_id: str, query: str) -> list[Skill]:
        """LIKE search across name and description, scoped to user's own + promoted."""
        logger.debug("SkillRegistry.search: instance_id=%s author=%s query=%r", instance_id, author_user_id, query)
        own_or_promoted = or_(
            ("author_user_id", author_user_id),
            ("status", "instance_promoted"),
        )
        name_or_desc = or_(
            ("name__icontains", query),
            ("description__icontains", query),
        )
        rows = await self.db.select(
            Skill,
            ("instance_id", instance_id),
            own_or_promoted,
            name_or_desc,
        )
        rows.sort(
            key=lambda s: (s.status == "instance_promoted", _dt_key(s.created_at)),
            reverse=True,
        )
        return rows

    # ── Update ──────────────────────────────────────────────────────────────

    async def _update_status(
        self, skill_id: str, new_status: str, promoted_by: str | None = None
    ) -> Skill | None:
        """Transition a skill's status (P1-06).  Private.

        ``instance_promoted`` is gate-only and is refused here with a
        ``RuntimeError``; promotion must go through the admission gate.  All
        other transitions are validated against the explicit transition table.
        """
        if new_status == "instance_promoted":
            raise RuntimeError(
                "instance_promoted is gate-only: promote via the admission gate"
            )
        logger.debug(
            "SkillRegistry._update_status: id=%s new_status=%s promoted_by=%s",
            skill_id, new_status, promoted_by,
        )
        skill = await self.get(skill_id)
        if skill is None:
            logger.warning("SkillRegistry._update_status: skill not found id=%s", skill_id)
            return None

        assert_allowed_transition(skill.status, new_status)
        skill.status = new_status

        await self.db.commit()
        await self.db.refresh(skill)
        logger.info("Skill status updated: id=%s status=%s", skill.id, skill.status)
        return skill
