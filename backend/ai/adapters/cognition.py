"""DjangoSweepRunAdapter — host implementation of the SweepRunStore port.

Upserts a ``ai.models.core.CognitionSweepRun`` row keyed by task name through
the supplied Store session (the same ``AI_STORE_BACKEND`` seam the loop used
before migration, so it works identically under ``inmemory`` and ``django``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ai.models.core import CognitionSweepRun
from ai.store import first


class DjangoSweepRunAdapter:
    """Cognition sweep-run ledger adapter implementing ``SweepRunStore``."""

    def __init__(self, db: Any) -> None:
        self.db = db

    async def record_run(
        self,
        task_name: str,
        last_run: datetime,
        last_status: str,
        last_duration_ms: int,
        last_error: str | None,
    ) -> None:
        rows = await self.db.select(CognitionSweepRun, ("task_name", task_name))
        row = first(rows)
        if row is not None:
            row.last_run = last_run
            row.last_status = last_status
            row.last_duration_ms = last_duration_ms
            row.run_count += 1
            row.last_error = last_error
        else:
            self.db.add(CognitionSweepRun(
                task_name=task_name,
                last_run=last_run,
                last_status=last_status,
                last_duration_ms=last_duration_ms,
                run_count=1,
                last_error=last_error,
            ))
        await self.db.commit()
