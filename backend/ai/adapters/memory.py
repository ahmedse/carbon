"""Host adapters for the engine memory ports over Django + ``scope_q()``.

P2-02a.  These adapters persist cognitive state (episodic events, long-term
facts, and org-scoped seeds) behind the tenant-scoped ``ai.store`` session,
applying ``scope_q()`` to every read so cross-tenant / cross-user data never
leaks (I4).  Rows are projected into the port's plain-dict shapes on the way
out, keeping the engine free of Django models (RULE_20).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

from ai.models.base import generate_uuid
from ai.models.core import MemoryEpisodic, MemoryLongTerm
from ai.store import first, scope_q

# Decay policy — mirrors ai.engine.memory.episodic.EpisodicMemory.
_DECAY_RATES: dict[str, float] = {
    "error": 0.01,
    "anomaly": 0.02,
    "performance_shift": 0.03,
    "schema_change": 0.04,
    "user_correction": 0.05,
    "milestone": 0.08,
}
_HALF_LIFE_DAYS: dict[str, int] = {
    "error": 30,
    "anomaly": 14,
    "performance_shift": 14,
    "schema_change": 7,
    "user_correction": 7,
    "milestone": 3,
}
_ARCHIVE_THRESHOLD = 0.1


def _episode_to_dict(ep: Any) -> dict[str, Any]:
    """Project a Django ``MemoryEpisodic`` row into the port's EpisodeRecord."""
    return {
        "id": ep.id,
        "event_type": ep.event_type,
        "summary": ep.summary,
        "details": ep.details,
        "occurred_at": ep.occurred_at,
        "caused_by_episode_id": ep.caused_by_episode_id,
        "host_user_id": ep.host_user_id,
        "visibility": ep.visibility,
        "relevance_score": ep.relevance_score,
    }


def _fact_to_dict(fact: Any) -> dict[str, Any]:
    """Project a Django ``MemoryLongTerm`` row into the port's FactRecord."""
    return {
        "id": fact.id,
        "category": fact.category,
        "content": fact.content,
        "confidence": fact.confidence,
        "source": fact.source,
        "host_user_id": fact.host_user_id,
        "visibility": fact.visibility,
        "valid_from": fact.valid_from,
        "valid_to": fact.valid_to,
        "archived": fact.archived,
    }


class DjangoEpisodicAdapter:
    """Event memory adapter implementing ``ai.engine.ports.memory.EpisodicStore``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def record_event(
        self,
        instance_id: str,
        event_type: str,
        summary: str,
        details: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
        host_user_id: str | None = None,
        visibility: str = "private",
    ) -> str:
        episode_id = generate_uuid()
        effective_visibility = visibility if host_user_id else "shared"
        episode = MemoryEpisodic(
            id=episode_id,
            instance_id=instance_id,
            event_type=event_type,
            summary=summary,
            details=details,
            occurred_at=occurred_at or timezone.now(),
            host_user_id=host_user_id,
            visibility=effective_visibility,
        )
        self.db.add(episode)
        await self.db.commit()
        return episode_id

    async def search(
        self,
        instance_id: str,
        event_type: str | None = None,
        query_text: str | None = None,
        limit: int = 10,
        host_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[Any] = [
            scope_q(MemoryEpisodic, instance_id, host_user_id),
            ("archived", False),
        ]
        if event_type:
            filters.append(("event_type", event_type))
        rows = await self.db.select(MemoryEpisodic, *filters)
        if query_text:
            needle = query_text.lower()
            rows = [r for r in rows if needle in (r.summary or "").lower()]
        rows.sort(key=lambda r: r.occurred_at, reverse=True)
        return [_episode_to_dict(r) for r in rows[:limit]]

    async def get_chain(
        self, instance_id: str, episode_id: str
    ) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        seen: set[str] = set()
        current_id: str | None = episode_id
        for _ in range(20):
            if not current_id or current_id in seen:
                break
            seen.add(current_id)
            rows = await self.db.select(
                MemoryEpisodic,
                scope_q(MemoryEpisodic, instance_id, None),
                ("id", current_id),
            )
            ep = first(rows)
            if ep is None:
                break
            chain.insert(0, _episode_to_dict(ep))
            current_id = ep.caused_by_episode_id
        return chain

    async def decay(
        self, instance_id: str, now: datetime | None = None
    ) -> int:
        now = now or timezone.now()
        rows = await self.db.select(
            MemoryEpisodic,
            scope_q(MemoryEpisodic, instance_id, None),
            ("archived", False),
        )
        changed = 0
        for ep in rows:
            age_days = (now - ep.occurred_at).total_seconds() / 86400.0
            half_life = _HALF_LIFE_DAYS.get(ep.event_type, 7)
            if age_days <= half_life:
                continue
            rate = _DECAY_RATES.get(ep.event_type, 0.05)
            ep.relevance_score = max(
                0.0, ep.relevance_score - rate * (age_days - half_life)
            )
            if ep.relevance_score < _ARCHIVE_THRESHOLD:
                ep.archived = True
            changed += 1
        if changed:
            await self.db.commit()
        return changed


class DjangoLongTermAdapter:
    """Durable fact memory adapter implementing ``LongTermStore``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def store_fact(
        self,
        instance_id: str,
        category: str,
        content: str,
        source: str | None = None,
        confidence: float = 1.0,
        host_user_id: str | None = None,
        visibility: str = "private",
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        memory_type: str | None = None,
    ) -> str:
        fact_id = generate_uuid()
        effective_visibility = visibility if host_user_id else "shared"
        fact = MemoryLongTerm(
            id=fact_id,
            instance_id=instance_id,
            category=category,
            content=content,
            source=source,
            confidence=confidence,
            host_user_id=host_user_id,
            visibility=effective_visibility,
            valid_from=valid_from,
            valid_to=valid_to,
            memory_type=memory_type,
        )
        self.db.add(fact)
        await self.db.commit()
        return fact_id

    async def retrieve(
        self,
        instance_id: str,
        query_text: str,
        limit: int = 10,
        host_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        now = timezone.now()
        rows = await self.db.select(
            MemoryLongTerm,
            scope_q(MemoryLongTerm, instance_id, host_user_id),
            ("archived", False),
        )
        active = [
            r for r in rows
            if r.valid_to is None or r.valid_to >= now
        ]
        if query_text:
            needle = query_text.lower()
            active = [
                r for r in active
                if needle in (r.content or "").lower()
                or needle in (r.category or "").lower()
            ]
        active.sort(
            key=lambda r: (r.confidence, r.created_at or now),
            reverse=True,
        )
        return [_fact_to_dict(r) for r in active[:limit]]

    async def supersede_fact(
        self, instance_id: str, fact_id: str
    ) -> str | None:
        rows = await self.db.select(
            MemoryLongTerm,
            scope_q(MemoryLongTerm, instance_id, None),
            ("id", fact_id),
        )
        fact = first(rows)
        if fact is None:
            return None
        fact.archived = True
        fact.valid_to = timezone.now()
        await self.db.commit()
        return None

    async def forget(self, instance_id: str, fact_id: str) -> None:
        rows = await self.db.select(
            MemoryLongTerm,
            scope_q(MemoryLongTerm, instance_id, None),
            ("id", fact_id),
        )
        fact = first(rows)
        if fact is not None:
            fact.archived = True
            await self.db.commit()


class DjangoOrgMemoryAdapter:
    """Org-scoped memory seed adapter implementing ``OrgMemory``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def get_org_memory_seeds(self, instance_id: str) -> list[dict[str, Any]]:
        qs = MemoryLongTerm.objects.filter(
            scope_q(MemoryLongTerm, instance_id, None),
            archived=False,
            superseded_by__isnull=True,
        ).order_by("-confidence", "-created_at")
        seeds: list[dict[str, Any]] = []
        for fact in qs:
            content = (fact.content or "").strip()
            if not content:
                continue
            seeds.append(
                {
                    "content": content,
                    "category": (fact.category or "").strip(),
                    "confidence": float(fact.confidence or 1.0),
                    "source": fact.source or None,
                    "host_user_id": fact.host_user_id,
                }
            )
        return seeds
