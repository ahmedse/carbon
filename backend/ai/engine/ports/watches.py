"""UserWatchStore port — user-configured anomaly watches (proactive, P2-02e).

Replaces the engine's direct ``ai.models.AIAnomalyWatch`` ORM access in
:class:`ai.engine.proactive.user_watches.run_user_watches` (P2-03).  The host
adapter persists watches and records fires; the engine only *evaluates* the
machine-evaluable ``condition`` spec and delivers insights.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypedDict


class WatchRecord(TypedDict, total=False):
    """A user-configured anomaly watch projection."""

    id: str
    instance_id: str
    name: str
    kpi_expression: str
    condition: dict[str, Any]
    threshold: float
    enabled: bool
    last_fired_at: datetime | None
    fire_count: int


class UserWatchStore(Protocol):
    """Lists enabled watches and records fires, scoped by instance."""

    async def list_enabled_watches(self, instance_id: str) -> list[WatchRecord]:
        """Return enabled watches for an instance."""
        ...

    async def record_fire(self, watch_id: str) -> WatchRecord | None:
        """Mark a watch as fired (increment count + timestamp); return the record."""
        ...
