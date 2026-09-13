"""ProcessRegistry port — process / run / journal registry (P3 process machine).

The engine's ReAct loop and skill invocation resolve governed processes by
``id@version`` and drive runs through this seam.  The host owns process
definitions, run state, and the append-only journal; the engine only requests
creation / resumption and observes outcomes.  Full wiring lands with P2-06 /
P3-07; this Protocol fixes the shape now so call sites never touch host models.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypedDict


class ProcessRecord(TypedDict, total=False):
    """A governed process definition (resolved by ``id@version``)."""

    id: str
    version: str
    name: str
    description: str | None
    states: list[str]
    owner: str | None
    active_revision: str | None


class RunRecord(TypedDict, total=False):
    """A process run (instance) with journal state."""

    id: str
    process_id: str
    process_version: str
    state: str
    created_at: datetime
    updated_at: datetime
    context: dict[str, Any]


class ProcessRegistry(Protocol):
    """Resolves processes and manages their runs + journal."""

    async def get_process(self, process_id: str, version: str | None = None) -> ProcessRecord | None:
        """Resolve a process by ``id@version`` (latest active if version omitted)."""
        ...

    async def register_process(self, process: ProcessRecord) -> str:
        """Register a process definition and return its id."""
        ...

    async def create_run(self, process_id: str, process_version: str, context: dict[str, Any] | None = None) -> RunRecord:
        """Create a new run and return its initial record."""
        ...

    async def resume_run(self, run_id: str) -> RunRecord | None:
        """Resume a run from its journaled state; return ``None`` if not found."""
        ...

    async def record_event(self, run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Append a journal event to a run (append-only)."""
        ...

    async def get_active_run(self, run_id: str) -> RunRecord | None:
        """Return the current run record if it is still active."""
        ...
