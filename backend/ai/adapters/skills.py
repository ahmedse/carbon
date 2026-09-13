"""Host adapter for the skill port over Django + ``scope_q()``.

P2-02c.  Async skill CRUD + promotion-state transitions.  Promotion is
gate-only: ``update_status`` refuses ``instance_promoted`` (P1-06) and
validates every other transition against the explicit table in
``ai.engine.skills._authority``.
"""

from __future__ import annotations

from typing import Any

from ai.engine.skills._authority import assert_allowed_transition
from ai.models.base import generate_uuid
from ai.models.core import Skill
from ai.store import first, scope_q


def _skill_to_record(skill: Any) -> dict[str, Any]:
    """Project a Django ``Skill`` row into the port's SkillRecord."""
    return {
        "id": skill.id,
        "instance_id": skill.instance_id,
        "name": skill.name,
        "kind": skill.kind,
        "description": skill.description,
        "body": skill.body,
        "author_user_id": skill.author_user_id,
        "status": skill.status,
        "gate_status": skill.gate_status,
        "created_at": skill.created_at,
        "promoted_at": skill.promoted_at,
    }


class DjangoSkillAdapter:
    """Async skill CRUD adapter implementing ``SkillStore``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def add(self, skill_data: dict) -> dict[str, Any]:
        skill = Skill(
            id=skill_data.get("id") or generate_uuid(),
            instance_id=skill_data.get("instance_id") or "",
            name=skill_data.get("name") or "",
            kind=skill_data.get("kind") or "",
            description=skill_data.get("description") or "",
            body=skill_data.get("body") if skill_data.get("body") is not None else {},
            author_user_id=skill_data.get("author_user_id") or "",
            status=skill_data.get("status") or "draft",
            gate_status=skill_data.get("gate_status") or "pending",
        )
        if skill_data.get("promoted_at") is not None:
            skill.promoted_at = skill_data["promoted_at"]
        self.db.add(skill)
        await self.db.commit()
        return _skill_to_record(skill)

    async def get(self, skill_id: str) -> dict[str, Any] | None:
        rows = await self.db.select(Skill, ("id", skill_id))
        skill = first(rows)
        return _skill_to_record(skill) if skill is not None else None

    async def list_by_user(
        self, instance_id: str, author_user_id: str
    ) -> list[dict[str, Any]]:
        rows = await self.db.select(
            Skill,
            scope_q(Skill, instance_id, author_user_id),
            ("author_user_id", author_user_id),
        )
        return [_skill_to_record(s) for s in rows]

    async def list_promoted(
        self, instance_id: str, kind: str | None = None
    ) -> list[dict[str, Any]]:
        filters: list[Any] = [
            scope_q(Skill, instance_id, None),
            ("status", "instance_promoted"),
        ]
        if kind:
            filters.append(("kind", kind))
        rows = await self.db.select(Skill, *filters)
        return [_skill_to_record(s) for s in rows]

    async def search(
        self, instance_id: str, author_user_id: str, query: str
    ) -> list[dict[str, Any]]:
        rows = await self.db.select(
            Skill,
            scope_q(Skill, instance_id, author_user_id),
        )
        needle = query.lower()
        rows = [
            s for s in rows
            if needle in (s.name or "").lower()
            or needle in (s.description or "").lower()
        ]
        return [_skill_to_record(s) for s in rows]

    async def update_status(
        self, skill_id: str, new_status: str, promoted_by: str | None = None
    ) -> dict[str, Any] | None:
        if new_status == "instance_promoted":
            raise RuntimeError(
                "skill promotion is gate-only; update_status cannot set "
                "'instance_promoted' (P1-06)"
            )
        rows = await self.db.select(Skill, ("id", skill_id))
        skill = first(rows)
        if skill is None:
            return None
        assert_allowed_transition(skill.status, new_status)
        skill.status = new_status
        if promoted_by:
            skill.promoted_by = promoted_by
        await self.db.commit()
        return _skill_to_record(skill)
