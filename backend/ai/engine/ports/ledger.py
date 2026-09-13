"""LedgerSink port — per-stage turn audit trail (S6 witness).

Replaces the engine's direct ``ai.engine.core.models.TurnLedgerRow`` write in
:class:`ai.engine.cognition.turn.ledger.LedgerWitness` (P2-03).  One row per
stage (six per turn) proves learn/deliver/escalate happened (I7 / L7).
"""
from __future__ import annotations

from typing import Any, Protocol


class LedgerSink(Protocol):
    """Persists per-stage ``turn_ledger`` rows to the host's audit store."""

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
        """Write a single stage row and return its id (or ``None`` on failure).

        The host adapter is savepoint-protected and returns ``None`` rather than
        raising so a ledger flush can never fail the turn (fail-visible, not
        disruptive).
        """
        ...
