"""EventBus port — transient pub/sub event transport.

The engine emits events for proactive delivery / SSE without knowing the
transport (Redis today, in-process for tests).  The bus is **fire-and-forget
and never durable** (RULE_6): a failed publish logs and drops, a dropped
subscription ends the stream — it must never crash a caller.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class EventBus(Protocol):
    """Transient, best-effort event transport (transport-only, not a store)."""

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        """Publish ``payload`` to ``channel``.  Never raises.

        Unreachable transport logs a warning and drops the event.
        """
        ...

    def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded event frames from ``channel``.  Never raises.

        On transport failure or connection drop the iterator simply ends.
        """
        ...
