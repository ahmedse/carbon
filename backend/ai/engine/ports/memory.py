"""Memory ports — durable cognitive-state seams.

Three Protocols replace the engine's direct ``ai.models.MemoryLongTerm`` /
``MemoryEpisodic`` / org-seed ORM access (P2-03).  The engine *requests* memory
through these; the host adapter persists it behind a tenant-scoped store and
applies ``scope_q()`` so cross-org/cross-app data never leaks (I4).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypedDict


class MemorySeed(TypedDict, total=False):
    """A single org-scoped long-term memory seed handed to the engine at boot."""

    content: str
    category: str
    confidence: float
    source: str | None
    host_user_id: str | None


class FactRecord(TypedDict, total=False):
    """A retrieved long-term memory fact (projection of ``MemoryLongTerm``)."""

    id: str
    category: str
    content: str
    confidence: float
    source: str | None
    host_user_id: str | None
    visibility: str
    valid_from: datetime | None
    valid_to: datetime | None
    archived: bool


class EpisodeRecord(TypedDict, total=False):
    """A retrieved episodic memory event (projection of ``MemoryEpisodic``)."""

    id: str
    event_type: str
    summary: str
    details: dict[str, Any] | None
    occurred_at: datetime
    caused_by_episode_id: str | None
    host_user_id: str | None
    visibility: str
    relevance_score: float


class EpisodicStore(Protocol):
    """Event-based memory with causal chains and typed decay.

    Mirrors :class:`ai.engine.memory.episodic.EpisodicMemory`.  Recording is
    scoped by ``instance_id`` and, when ``host_user_id`` is present, by the
    user's own visibility; the host adapter enforces tenancy.
    """

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
        """Record a system event and return its id.

        Event types: ``anomaly``, ``user_correction``, ``schema_change``,
        ``performance_shift``, ``error``, ``milestone``.  The host links causal
        predecessors and applies the per-type decay policy.
        """
        ...

    async def search(
        self,
        instance_id: str,
        event_type: str | None = None,
        query_text: str | None = None,
        limit: int = 10,
        host_user_id: str | None = None,
    ) -> list[EpisodeRecord]:
        """Return recent episodes, optionally filtered by type / semantic query."""
        ...

    async def get_chain(self, instance_id: str, episode_id: str) -> list[EpisodeRecord]:
        """Return the causal chain rooted at ``episode_id``."""
        ...

    async def decay(self, instance_id: str, now: datetime | None = None) -> int:
        """Apply the per-type decay policy; return the number of episodes changed."""
        ...


class LongTermStore(Protocol):
    """Durable fact memory with dedup, contradiction detection, and supersession.

    Mirrors :class:`ai.engine.memory.long_term.LongTermMemory`.  Facts survive
    across conversations; write-path semantic dedup and contradiction handling
    are host-side responsibilities (the engine supplies content + confidence).
    """

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
        """Store a fact and return its id (dedup may return an existing id).

        Categories: ``learned``, ``correction``, ``preference``, ``observation``.
        """
        ...

    async def retrieve(
        self,
        instance_id: str,
        query_text: str,
        limit: int = 10,
        host_user_id: str | None = None,
    ) -> list[FactRecord]:
        """Semantically retrieve facts, tenant + visibility scoped."""
        ...

    async def supersede_fact(self, instance_id: str, fact_id: str) -> str | None:
        """Mark a fact superseded; return the id of the replacement, if any."""
        ...

    async def forget(self, instance_id: str, fact_id: str) -> None:
        """Archive a fact so it is no longer retrieved."""
        ...


class OrgMemory(Protocol):
    """Org-scoped long-term memory seeds supplied by the host at instance boot.

    The engine does not know how org memory is stored; it asks the host for the
    seeds relevant to an instance (mirrors
    ``CarbonHostAdapter.get_org_memory_seeds``).
    """

    def get_org_memory_seeds(self, instance_id: str) -> list[MemorySeed]:
        """Return org-scoped long-term memory seeds for an instance."""
        ...
