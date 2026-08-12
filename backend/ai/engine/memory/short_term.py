"""
Short-term memory — per-conversation context kept in-process.
Holds recent messages for the active conversation with token-budgeted retrieval.
"""
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("pulse.memory.short_term")

# Approximate: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4


@dataclass
class MemoryMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class ShortTermMemory:
    """In-process conversation memory. Thread-safe dict of conversation_id → messages."""

    def __init__(self):
        self._store: dict[str, list[MemoryMessage]] = {}
        self._lock = threading.Lock()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ):
        """Append a message to the conversation's short-term memory."""
        msg = MemoryMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []
            self._store[conversation_id].append(msg)

    def get_context_window(
        self, conversation_id: str, max_tokens: int = 4096
    ) -> list[dict]:
        """
        Return the most recent messages that fit within the token budget.
        Walks backwards from newest, stops when budget is exhausted.
        """
        with self._lock:
            messages = self._store.get(conversation_id, [])

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
        with self._lock:
            messages = self._store.get(conversation_id, [])
        return [{"role": m.role, "content": m.content} for m in messages]

    def clear(self, conversation_id: str):
        """Remove all messages for a conversation (e.g. on disconnect)."""
        with self._lock:
            self._store.pop(conversation_id, None)
        logger.debug(f"Cleared short-term memory for conversation {conversation_id}")

    def conversation_count(self) -> int:
        """How many active conversations are being tracked."""
        with self._lock:
            return len(self._store)
