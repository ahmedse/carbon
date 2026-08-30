"""Working memory — per-conversation active entity focus store (GAP-2).

Redis-backed (Pulse 0.2 Phase A1). Holds the most recently focused entity per
conversation so the anaphora resolver and draft witness can reference it
without re-scanning the full message history. Redis is the source of truth;
the in-process dict is a fallback only when Redis is unreachable.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.memory._redis import get_redis_client, memory_key

logger = logging.getLogger("pulse.memory.working")


@dataclass
class WorkingFocus:
    entity: str
    entity_type: str
    set_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class WorkingMemory:
    """Per-conversation entity focus store backed by Redis with in-process fallback.

    Redis is the source of truth (L1). ``_store`` is used only when Redis is
    unreachable so callers degrade gracefully instead of crashing.
    """

    def __init__(self) -> None:
        self._store: dict[str, WorkingFocus] = {}
        self._lock = threading.Lock()

    # ── Redis plumbing ──────────────────────────────────────────────────

    def _key(self, conversation_id: str) -> str:
        return memory_key("wm", conversation_id)

    def _ttl(self) -> int:
        return get_settings().PULSE_MEMORY_REDIS_TTL_SECONDS

    @staticmethod
    def _serialize(focus: WorkingFocus) -> str:
        return json.dumps(
            {
                "entity": focus.entity,
                "entity_type": focus.entity_type,
                "set_at": focus.set_at,
            }
        )

    @staticmethod
    def _deserialize(payload: str) -> WorkingFocus | None:
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return None
        return WorkingFocus(
            entity=data.get("entity", ""),
            entity_type=data.get("entity_type", "item"),
            set_at=data.get("set_at") or datetime.now(timezone.utc).isoformat(),
        )

    # ── Public API (signatures preserved) ───────────────────────────────

    def set_focus(
        self, conversation_id: str, entity: str, entity_type: str = "item"
    ) -> None:
        """Store or update the active entity for a conversation."""
        focus = WorkingFocus(entity=entity, entity_type=entity_type)

        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                client.set(key, self._serialize(focus), ex=self._ttl())
                return
            except Exception as exc:  # noqa: BLE001 — lenient fallback
                logger.warning(
                    "Redis write failed for %s — falling back to in-process store: %s",
                    key,
                    exc,
                )

        with self._lock:
            self._store[conversation_id] = focus

    def get_focus(self, conversation_id: str) -> WorkingFocus | None:
        """Return the active entity focus, or None if not set."""
        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                payload = client.get(key)
                if payload is None:
                    return None
                return self._deserialize(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Redis read failed for %s — falling back to in-process store: %s",
                    key,
                    exc,
                )

        with self._lock:
            return self._store.get(conversation_id)

    def clear(self, conversation_id: str) -> None:
        """Remove the focus entry for a conversation."""
        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                client.delete(key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis delete failed for %s — %s", key, exc)

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
