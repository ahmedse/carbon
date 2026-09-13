"""Clock port — the engine's single source of time.

The engine never calls ``datetime.now`` / ``time.time`` directly; it reads time
through a :class:`Clock`.  This makes reasoning, decay, and replay deterministic
under test (P0-07 replay fixtures) and correct under ``USE_TZ=True``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Source of time for the engine.

    Implementations must return **timezone-aware UTC** datetimes.  The host
    default wraps :func:`ai.engine.core.clock.utcnow`; a replay/test clock may
    freeze or script time to keep fixtures byte-for-byte stable.
    """

    def utcnow(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""
        ...
