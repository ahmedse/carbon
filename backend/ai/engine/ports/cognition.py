"""Cognition sweep-run persistence port — durable per-task run ledger.

Replaces the engine's direct ``ai.models.CognitionSweepRun`` ORM access in
``ai.engine.cognition.loop._persist_sweep_run`` (P2-03).  The host adapter
upserts the row keyed by task name; the engine only reports the run outcome.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class SweepRunStore(Protocol):
    """Upsert a cognition sweep-run row keyed by task name."""

    async def record_run(
        self,
        task_name: str,
        last_run: datetime,
        last_status: str,
        last_duration_ms: int,
        last_error: str | None,
    ) -> None:
        """Insert or update the ``CognitionSweepRun`` row for ``task_name``."""
        ...
