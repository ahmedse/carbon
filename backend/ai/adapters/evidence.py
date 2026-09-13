"""DjangoEvidenceAdapter — host implementation of the EvidenceStore port.

Persists ``ai.models.core.EvidenceRecord`` rows directly through the Django
ORM (the execute witness already normalizes the payload and runs outside a
Store session), mirroring the pre-migration ``objects.create`` call exactly.
"""
from __future__ import annotations

from typing import Any

from ai.models.core import EvidenceRecord


class DjangoEvidenceAdapter:
    """Evidence-row writer adapter implementing ``EvidenceStore``."""

    def __init__(self) -> None:
        pass

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
        from asgiref.sync import sync_to_async

        await sync_to_async(EvidenceRecord.objects.create, thread_sensitive=True)(
            instance_id=instance_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            host_user_id=host_user_id,
            source_type=source_type,
            source_identifier=source_identifier,
            query_description=query_description,
            content_json=content_json,
            coverage=coverage,
        )
