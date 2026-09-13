"""SkillStore port — durable skill CRUD + promotion-state transitions.

Replaces the engine's direct ``ai.engine.core.models.Skill`` / SQLAlchemy access
in :class:`ai.engine.skills.registry.SkillRegistry` (P2-03 / P2-05).  Promotion
is **gate-only**: the ``instance_promoted`` status may not be reached through a
bare status write — it must pass the admission gate (P1-06).
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, TypedDict


class SkillRecord(TypedDict, total=False):
    """A skill projection handed across the port boundary."""

    id: str
    instance_id: str
    name: str
    kind: str
    description: str | None
    body: str | None
    author_user_id: str | None
    status: str
    gate_status: str
    created_at: datetime
    promoted_at: datetime | None


class SkillStore(Protocol):
    """Async CRUD for the Skill table, scoped by instance."""

    async def add(self, skill_data: dict) -> SkillRecord:
        """Insert a new skill and return the persisted record."""
        ...

    async def get(self, skill_id: str) -> SkillRecord | None:
        """Retrieve a single skill by primary key."""
        ...

    async def list_by_user(self, instance_id: str, author_user_id: str) -> list[SkillRecord]:
        """Return all skills authored by a given user (any status)."""
        ...

    async def list_promoted(self, instance_id: str, kind: str | None = None) -> list[SkillRecord]:
        """Return instance-promoted skills, optionally filtered by kind."""
        ...

    async def search(
        self, instance_id: str, author_user_id: str, query: str
    ) -> list[SkillRecord]:
        """Search names/descriptions, scoped to the user's own + promoted skills."""
        ...

    async def update_status(
        self, skill_id: str, new_status: str, promoted_by: str | None = None
    ) -> SkillRecord | None:
        """Transition a skill's status, enforcing the transition table.

        ``instance_promoted`` is refused here — promotion is gate-only and must
        go through the admission gate (P1-06).  All other transitions are
        validated against the explicit transition table.
        """
        ...
