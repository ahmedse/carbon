"""PendingActionStore — tracks Pulse's open 'shall I remember/store X?' proposals.

Domain-agnostic, thread-safe, in-process store (GAP-M6). When Pulse asks a
yes/no question about remembering a fact, the pending action is recorded so the
next short user message can be recognised as a confirmation instead of being
routed to the LLM as a decontextualized query.

Memory-only in M0: it tracks learn_fact proposals. It never auto-executes
arbitrary host mutations — those stay on the existing RULE_21 propose→confirm
path (``create_pending_execution`` → user confirms the card).

Uses the same lock-per-dict singleton pattern as ``engine/memory/working.py``.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PendingAction:
    conv_id: str
    fact: str
    category: str = "observation"
    expires_turns: int = 2
    set_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Confirmation signals ─────────────────────────────────────────────────────
# Short affirmative messages only. A long message containing "yes" is NOT a
# confirmation — it is a fresh query that must flow through the normal pipeline.
_CONFIRMATION_SIGNALS: frozenset[str] = frozenset({
    "yes", "yeah", "yep", "ok", "okay", "sure",
    "do it", "go ahead", "please", "store it", "remember it",
    "yes please",
})

_MAX_CONFIRMATION_WORDS = 4

# ── Proposal detection (regex only, no LLM, no domain terms) ──────────────────
_PROPOSAL_PATTERN = re.compile(
    r"\b(?:shall|should|would you like me to|want me to|can i)\b\s+"
    r"(?:i\s+|we\s+)?"
    r"(?:store|remember|memorize|save|note)\s+(.+)",
    re.IGNORECASE,
)

_IDENTITY_PATTERN = re.compile(r"\bI am\b|\bmy name is\b|\bI'm\b", re.IGNORECASE)
_PREFERENCE_PATTERN = re.compile(r"\b(?:prefer|want|like|always)\b", re.IGNORECASE)

_TRAILING_PUNCT = re.compile(r"[.!?\s]+$")


def _infer_category(fact: str) -> str:
    """Infer the memory category from the fact's wording (regex only)."""
    if _IDENTITY_PATTERN.search(fact):
        return "identity"
    if _PREFERENCE_PATTERN.search(fact):
        return "preference"
    return "observation"


class PendingActionStore:
    """In-process per-conversation pending-action store. Thread-safe."""

    def __init__(self) -> None:
        self._store: dict[str, PendingAction] = {}
        self._lock = threading.Lock()

    def set_pending(
        self,
        conv_id: str,
        fact: str,
        category: str = "observation",
        expires_turns: int = 2,
    ) -> None:
        """Record an open proposal awaiting a yes/no."""
        with self._lock:
            self._store[conv_id] = PendingAction(
                conv_id=conv_id,
                fact=fact,
                category=category,
                expires_turns=expires_turns,
            )

    def get_pending(self, conv_id: str) -> dict | None:
        """Return the pending action for a conversation, or None."""
        with self._lock:
            pa = self._store.get(conv_id)
            return self._to_dict(pa) if pa else None

    def check_confirmation(self, conv_id: str, user_message: str) -> dict | None:
        """Return the pending action if ``user_message`` affirms it, else None.

        Confirmation requires BOTH:
          * a pending action exists for this conversation, and
          * the message is a short affirmative (≤ 4 words).

        A bare "yes" with no pending action returns None — it must not
        short-circuit a fresh query.
        """
        if not user_message:
            return None

        normalized = user_message.strip().lower()
        normalized = _TRAILING_PUNCT.sub("", normalized).strip()
        if not normalized:
            return None

        if len(normalized.split()) > _MAX_CONFIRMATION_WORDS:
            return None

        if normalized not in _CONFIRMATION_SIGNALS:
            return None

        with self._lock:
            pa = self._store.get(conv_id)
            return self._to_dict(pa) if pa else None

    def clear(self, conv_id: str) -> None:
        """Remove the pending action for a conversation."""
        with self._lock:
            self._store.pop(conv_id, None)

    def detect_proposal(self, response_text: str) -> dict | None:
        """Detect a memory proposal in the assistant's FINAL text.

        Returns ``{"fact": ..., "category": ...}`` or None. Purely regex-based —
        no domain terms, no LLM.
        """
        if not response_text:
            return None
        m = _PROPOSAL_PATTERN.search(response_text)
        if not m:
            return None
        fact = _TRAILING_PUNCT.sub("", m.group(1).strip()).strip()
        if not fact:
            return None
        return {"fact": fact, "category": _infer_category(fact)}

    @staticmethod
    def _to_dict(pa: PendingAction) -> dict:
        return {
            "fact": pa.fact,
            "category": pa.category,
            "conv_id": pa.conv_id,
        }


# ── Process-level singleton ───────────────────────────────────────────────────

_pending_action_store: PendingActionStore | None = None


def get_pending_action_store() -> PendingActionStore:
    global _pending_action_store
    if _pending_action_store is None:
        _pending_action_store = PendingActionStore()
    return _pending_action_store
