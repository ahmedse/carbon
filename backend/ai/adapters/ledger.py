"""Host adapter for the ledger port over Django + ``scope_q()``.

P2-02b.  Writes one ``TurnLedgerRow`` per engine stage (S6 witness).  The write
is fail-visible, not disruptive: on any failure the adapter returns ``None``
instead of raising, so a ledger flush can never fail the turn (I7 / L7).
"""

from __future__ import annotations

import logging
from typing import Any

from ai.models.base import generate_uuid
from ai.models.core import TurnLedgerRow

logger = logging.getLogger("carbon.ai.adapters.ledger")


class DjangoLedgerAdapter:
    """Per-stage audit trail adapter implementing ``LedgerSink.record_stage``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def record_stage(
        self,
        turn_id: str,
        instance_id: str,
        conversation_id: str,
        host_user_id: str | None,
        stage: str,
        stage_index: int,
        payload: object | None = None,
        latency_ms: float | None = None,
        tokens_used: int | None = None,
        model_used: str | None = None,
        verdict: str | None = None,
        flags: list[str] | None = None,
    ) -> str | None:
        try:
            row = TurnLedgerRow(
                id=generate_uuid(),
                turn_id=turn_id,
                instance_id=instance_id,
                conversation_id=conversation_id,
                host_user_id=host_user_id,
                stage=stage,
                stage_index=stage_index,
                payload_json=payload,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
                model_used=model_used,
                verdict=verdict,
                flags_json=flags,
            )
            self.db.add(row)
            await self.db.commit()
            return row.id
        except Exception:  # noqa: BLE001 - fail-visible, never disruptive
            logger.exception("record_stage failed; returning None (fail-visible)")
            return None
