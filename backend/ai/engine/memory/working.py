"""Working memory — per-conversation active entity focus store (GAP-2).

Thread-safe in-process store. Holds the most recently focused entity per
conversation so the anaphora resolver and draft witness can reference it
without re-scanning the full message history.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WorkingFocus:
    entity: str
    entity_type: str
    set_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class WorkingMemory:
    """In-process per-conversation entity focus store. Thread-safe.

    Uses the same lock-per-dict pattern as ShortTermMemory to remain
    safe under concurrent asyncio task access.
    """

    def __init__(self) -> None:
        self._store: dict[str, WorkingFocus] = {}
        self._lock = threading.Lock()

    def set_focus(
        self, conversation_id: str, entity: str, entity_type: str = "item"
    ) -> None:
        """Store or update the active entity for a conversation."""
        with self._lock:
            self._store[conversation_id] = WorkingFocus(
                entity=entity,
                entity_type=entity_type,
            )

    def get_focus(self, conversation_id: str) -> WorkingFocus | None:
        """Return the active entity focus, or None if not set."""
        with self._lock:
            return self._store.get(conversation_id)

    def clear(self, conversation_id: str) -> None:
        """Remove the focus entry for a conversation."""
        with self._lock:
            self._store.pop(conversation_id, None)

    def to_prompt_fragment(self, conversation_id: str) -> str:
        """One-line context injection for LLM system prompts."""
        focus = self.get_focus(conversation_id)
        if not focus:
            return ""
        return f"Currently active: {focus.entity} (type: {focus.entity_type})"


# ── Process-level singleton ────────────────────────────────────────────────────

_working_memory: WorkingMemory | None = None


def get_working_memory() -> WorkingMemory:
    global _working_memory
    if _working_memory is None:
        _working_memory = WorkingMemory()
    return _working_memory
