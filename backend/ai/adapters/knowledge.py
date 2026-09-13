"""DjangoKnowledgeEntityAdapter — host implementation of the KnowledgeEntityStore port.

Reads ``ai.models.core.KnowledgeEntity`` rows directly through the Django ORM
(the lexical fallback is host-owned durable state and does not flow through a
Store session), normalizing each row into the dict shape the engine expects.
"""
from __future__ import annotations

from typing import Any

from ai.models.core import KnowledgeEntity


class DjangoKnowledgeEntityAdapter:
    """Read-only lexical access to knowledge entities over the Django ORM."""

    def __init__(self) -> None:
        pass

    async def list_by_instance(self, instance_id: str) -> list[dict[str, Any]]:
        from asgiref.sync import sync_to_async

        def _run() -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for r in KnowledgeEntity.objects.filter(instance_id=instance_id):
                out.append({
                    "id": r.id,
                    "name": r.name,
                    "entity_type": r.entity_type,
                    "semantic_description": r.semantic_description,
                    "schema_json": r.schema_json,
                    "relationships": r.relationships,
                })
            return out

        return await sync_to_async(_run, thread_sensitive=True)()
