"""Knowledge-entity store port — read-only lexical access to host entities.

Replaces the engine's direct ``ai.models.KnowledgeEntity`` ORM access in
``ai.engine.knowledge.store.KnowledgeStore._lexical_search`` (P2-03).  The
host adapter reads the durable PostgreSQL rows; the engine only scores and
ranks the normalized projections.
"""
from __future__ import annotations

from typing import Any, Protocol


class KnowledgeEntityStore(Protocol):
    """Read-only lexical access to host knowledge entities for an instance."""

    async def list_by_instance(self, instance_id: str) -> list[dict[str, Any]]:
        """Return all knowledge entities for ``instance_id``.

        Each dict carries the keys ``id``, ``name``, ``entity_type``,
        ``semantic_description``, ``schema_json`` and ``relationships``.
        """
        ...
