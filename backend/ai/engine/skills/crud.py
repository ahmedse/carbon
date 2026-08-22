"""
SkillsStore — async CRUD for procedural skills (BE-02-4).

Companion to skills/registry.py (SkillRegistry). SkillsStore adds
procedure-specific validation, stats tracking, and resolution logic
that the Phase 3 orchestrator and Phase 4 evolution engine consume.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.engine.core.clock import utcnow
from ai.engine.core.models import Skill
from ai.engine.skills.schema import ProcedureBody

logger = logging.getLogger("pulse.skills.crud")


class SkillsStore:
    """Procedure-aware CRUD. Coexists with SkillRegistry (general CRUD)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ──────────────────────────────────────────────────────────────

    async def create_procedure(
        self,
        instance_id: str,
        name: str,
        description: str,
        steps: list[dict],
        preconditions: dict | None = None,
        author_user_id: str = "system",
    ) -> Skill:
        """Create a new procedure skill with validated body."""
        # Validate body against ProcedureBody schema
        try:
            body_obj = ProcedureBody(steps=steps)
        except Exception as exc:
            raise ValueError(f"Invalid procedure body for {name!r}: {exc}") from exc

        skill = Skill(
            instance_id=instance_id,
            name=name,
            description=description,
            kind="procedure",
            status="draft",
            author_user_id=author_user_id,
            body=body_obj.model_dump_json(),
            signature='{"inputs":[],"outputs":[]}',
            preconditions=json.dumps(preconditions) if preconditions else None,
        )
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)
        logger.info(
            "SkillsStore.create_procedure: id=%s name=%r steps=%d",
            skill.id, name, len(steps),
        )
        return skill

    # ── Read ────────────────────────────────────────────────────────────────

    async def get_by_name(
        self, instance_id: str, name: str, kind: str = "procedure"
    ) -> Skill | None:
        """Look up a skill by name and kind."""
        result = await self.db.execute(
            select(Skill).where(
                Skill.instance_id == instance_id,
                Skill.name == name,
                Skill.kind == kind,
            )
        )
        return result.scalar_one_or_none()

    async def list_procedures(
        self, instance_id: str, status: str | None = None, limit: int = 50
    ) -> list[Skill]:
        """List procedures, optionally filtered by status."""
        conditions = [
            Skill.instance_id == instance_id,
            Skill.kind == "procedure",
        ]
        if status:
            conditions.append(Skill.status == status)

        result = await self.db.execute(
            select(Skill)
            .where(*conditions)
            .order_by(Skill.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def resolve_skill(
        self, instance_id: str, skill_ref: str
    ) -> Skill | None:
        """Resolve a skill reference (name or ID) to a Skill row.

        Prefers instance_promoted, falls back to draft by author.
        """
        # Try by ID first
        result = await self.db.execute(
            select(Skill).where(
                Skill.id == skill_ref,
                Skill.instance_id == instance_id,
            )
        )
        skill = result.scalar_one_or_none()
        if skill is not None:
            return skill

        # Try by name — prefer promoted, then draft
        result = await self.db.execute(
            select(Skill).where(
                Skill.instance_id == instance_id,
                Skill.name == skill_ref,
            ).order_by(
                # instance_promoted sorts after draft alphabetically,
                # so reverse: promoted first, then draft
                Skill.status.desc(),
                Skill.created_at.desc(),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    # ── Update ──────────────────────────────────────────────────────────────

    async def update_stats(
        self, skill_id: str, success: bool, latency_ms: float
    ) -> None:
        """Update usage_count, success_rate, avg_latency_ms after execution."""
        skill = await self.db.get(Skill, skill_id)
        if skill is None:
            logger.warning("SkillsStore.update_stats: skill not found id=%s", skill_id)
            return

        new_count = skill.usage_count + 1
        new_success_count = (skill.success_rate * skill.usage_count) + (1.0 if success else 0.0)
        new_success_rate = new_success_count / new_count if new_count > 0 else 0.0

        # Rolling average latency
        if skill.avg_latency_ms == 0.0:
            new_avg_latency = latency_ms
        else:
            alpha = 0.3  # EMA weight for newest observation
            new_avg_latency = (1 - alpha) * skill.avg_latency_ms + alpha * latency_ms

        # Mutate in place and let the store's commit flush it back — the
        # Django backend re-saves tracked objects on commit, so a raw SQL
        # ``update()`` here would be clobbered by the stale tracked row.
        skill.usage_count = new_count
        skill.success_rate = round(new_success_rate, 4)
        skill.avg_latency_ms = round(new_avg_latency, 2)
        skill.last_executed_at = utcnow()
        await self.db.commit()
        logger.debug(
            "SkillsStore.update_stats: id=%s count=%d rate=%.3f latency=%.1f",
            skill_id, new_count, new_success_rate, new_avg_latency,
        )

    async def promote_to_instance(
        self, skill_id: str, promoted_by: str
    ) -> Skill | None:
        """Promote a user-owned skill to instance-global."""
        skill = await self.db.get(Skill, skill_id)
        if skill is None:
            logger.warning("SkillsStore.promote_to_instance: not found id=%s", skill_id)
            return None

        now = utcnow()
        skill.status = "instance_promoted"
        skill.promoted_at = now
        skill.promoted_by = promoted_by
        await self.db.commit()
        await self.db.refresh(skill)
        logger.info(
            "SkillsStore.promote_to_instance: id=%s name=%r promoted_by=%r",
            skill_id, skill.name, promoted_by,
        )
        return skill
