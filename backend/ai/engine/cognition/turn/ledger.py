"""S6 — Ledger witness (per-stage audit trail).

Writes one TurnLedgerRow per stage (6 rows per turn) into the turn_ledger table.
"""
import json
import logging

from ai.engine.core.models import TurnLedgerRow

logger = logging.getLogger("pulse.cognition.turn.ledger")


class LedgerWitness:
    """Persists per-stage turn_ledger rows to the database."""

    async def record_stage(
        self,
        db,
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
    ) -> TurnLedgerRow | None:
        """Write a single stage row to turn_ledger (savepoint-protected)."""
        row = TurnLedgerRow(
            turn_id=turn_id,
            instance_id=instance_id,
            host_user_id=host_user_id,
            conversation_id=conversation_id,
            stage=stage,
            stage_index=stage_index,
            payload_json=json.dumps(payload, default=str) if payload else None,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            model_used=model_used,
            verdict=verdict,
            flags_json=json.dumps(flags) if flags else None,
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
        except Exception as exc:
            logger.warning("turn_ledger stage=%s idx=%d flush failed: %s", stage, stage_index, exc)
            return None

        logger.debug(
            "turn_ledger stage=%s idx=%d turn=%s verdict=%s",
            stage, stage_index, turn_id[:8], verdict,
        )
        return row
