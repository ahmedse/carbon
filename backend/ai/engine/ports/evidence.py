"""Evidence-store port — durable evidence rows for executed tool calls.

Replaces the engine's direct ``ai.models.EvidenceRecord`` ORM access in
``ai.engine.cognition.turn.execute._register_evidence`` (P2-03).  The host
adapter persists the row; the engine only normalizes the tool payload.
"""
from __future__ import annotations

from typing import Any, Protocol


class EvidenceStore(Protocol):
    """Persist an evidence row for a successfully executed tool call."""

    async def record(
        self,
        *,
        instance_id: str,
        conversation_id: str,
        turn_id: str,
        host_user_id: str,
        source_type: str,
        source_identifier: str,
        query_description: str,
        content_json: Any,
        coverage: str = "unknown",
    ) -> None:
        """Create an ``EvidenceRecord`` row."""
        ...
