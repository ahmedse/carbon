"""
Short-term memory — per-conversation context kept in Redis (Pulse 0.2 Phase A1).

Redis is the source of truth so short-term memory survives restarts and is
shared across worker processes. The in-process dict is a fallback used only
when Redis is unreachable, and that fallback is always announced with a
visible warning (never silent).
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.memory._redis import get_redis_client, memory_key

logger = logging.getLogger("pulse.memory.short_term")

# Approximate: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4


@dataclass
class MemoryMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


class ShortTermMemory:
    """Per-conversation short-term memory backed by Redis with in-process fallback.

    Redis is the source of truth (L1). ``_store`` is used only when Redis is
    unreachable so callers degrade gracefully instead of crashing.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[MemoryMessage]] = {}
        self._lock = threading.Lock()

    # ── Redis plumbing ──────────────────────────────────────────────────

    def _key(self, conversation_id: str) -> str:
        return memory_key("st", conversation_id)

    def _ttl(self) -> int:
        return get_settings().PULSE_MEMORY_REDIS_TTL_SECONDS

    @staticmethod
    def _serialize(messages: list[MemoryMessage]) -> str:
        return json.dumps(
            [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata or {},
                }
                for m in messages
            ],
            default=str,
        )

    @staticmethod
    def _deserialize(payload: str) -> list[MemoryMessage]:
        raw = json.loads(payload)
        messages: list[MemoryMessage] = []
        for item in raw:
            ts = item.get("timestamp")
            try:
                timestamp = (
                    datetime.fromisoformat(ts) if ts else datetime.now(timezone.utc)
                )
            except (TypeError, ValueError):
                timestamp = datetime.now(timezone.utc)
            messages.append(
                MemoryMessage(
                    role=item.get("role", ""),
                    content=item.get("content", ""),
                    timestamp=timestamp,
                    metadata=item.get("metadata") or {},
                )
            )
        return messages

    # ── Public API (signatures preserved) ───────────────────────────────

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """Append a message to the conversation's short-term memory."""
        msg = MemoryMessage(role=role, content=content, metadata=metadata or {})

        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                existing = client.get(key)
                messages = self._deserialize(existing) if existing else []
                messages.append(msg)
                client.set(key, self._serialize(messages), ex=self._ttl())
                return
            except Exception as exc:  # noqa: BLE001 — lenient fallback
                logger.warning(
                    "Redis write failed for %s — falling back to in-process store: %s",
                    key,
                    exc,
                )

        with self._lock:
            self._store.setdefault(conversation_id, []).append(msg)

    def get_context_window(
        self, conversation_id: str, max_tokens: int = 4096
    ) -> list[dict]:
        """
        Return the most recent messages that fit within the token budget.
        Walks backwards from newest, stops when budget is exhausted.
        """
        messages = self._read_messages(conversation_id)
        if not messages:
            return []

        budget = max_tokens * CHARS_PER_TOKEN
        selected: list[MemoryMessage] = []
        used = 0

        for msg in reversed(messages):
            msg_chars = len(msg.content) + len(msg.role) + 10  # overhead
            if used + msg_chars > budget:
                break
            selected.append(msg)
            used += msg_chars

        # Restore chronological order
        selected.reverse()
        return [{"role": m.role, "content": m.content} for m in selected]

    def get_all_messages(self, conversation_id: str) -> list[dict]:
        """Return all messages for a conversation (no token budget)."""
        messages = self._read_messages(conversation_id)
        return [{"role": m.role, "content": m.content} for m in messages]

    def clear(self, conversation_id: str) -> None:
        """Remove all messages for a conversation (e.g. on disconnect)."""
        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                client.delete(key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis delete failed for %s — %s", key, exc)

        with self._lock:
            self._store.pop(conversation_id, None)
        logger.debug("Cleared short-term memory for conversation %s", conversation_id)

    def conversation_count(self) -> int:
        """How many active conversations are being tracked."""
        client = get_redis_client()
        if client is not None:
            pattern = f"pulse:st:{get_settings().PULSE_INSTANCE_ID}:*"
            try:
                return sum(1 for _ in client.scan_iter(match=pattern))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis scan failed for %s — %s", pattern, exc)

        with self._lock:
            return len(self._store)

    # ── Internal read path (Redis first, dict only as fallback) ────────

    def _read_messages(self, conversation_id: str) -> list[MemoryMessage]:
        """Read messages from Redis (source of truth); fall back to the dict."""
        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                payload = client.get(key)
                if payload is not None:
                    return self._deserialize(payload)
                return []
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Redis read failed for %s — falling back to in-process store: %s",
                    key,
                    exc,
                )

        with self._lock:
            return list(self._store.get(conversation_id, []))
