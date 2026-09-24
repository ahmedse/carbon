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
from ai.engine.cognition.phrase_tables import T

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.engine.cognition.dialogue.affirmation import is_affirmation
from ai.engine.cognition.dialogue.affirmation import normalize as normalize_affirmation
from ai.engine.text.word_match import contains_any_phrase, has_any_word


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
# The general vocabulary lives in ``dialogue.affirmation`` (shared with the
# deixis gate and consent resume); these are the memory-card-specific extras.
_MEMORY_CONFIRMATION_SIGNALS = T("dialogue/pending_action.py::_MEMORY_CONFIRMATION_SIGNALS")

# ── Proposal detection (regex only, no LLM, no domain terms) ──────────────────
_PROPOSAL_PREFIX_PHRASES = T("dialogue/pending_action.py::_PROPOSAL_PREFIX_PHRASES")
_PROPOSAL_VERBS = T("dialogue/pending_action.py::_PROPOSAL_VERBS")


def _strip_trailing_punct(text: str) -> str:
    end = len(text)
    while end and (text[end - 1].isspace() or text[end - 1] in ".!?"):
        end -= 1
    return text[:end]


def _extract_proposal_fact(response_text: str) -> str | None:
    lower = response_text.casefold()
    for prefix in _PROPOSAL_PREFIX_PHRASES:
        pos = lower.find(prefix)
        if pos < 0:
            continue
        rest = response_text[pos + len(prefix):].lstrip()
        if rest.casefold().startswith("i "):
            rest = rest[2:].lstrip()
        elif rest.casefold().startswith("we "):
            rest = rest[3:].lstrip()
        verb_pos = -1
        matched_verb = ""
        for verb in _PROPOSAL_VERBS:
            if rest.casefold().startswith(verb):
                verb_pos = 0
                matched_verb = verb
                break
            needle = f" {verb} "
            idx = rest.casefold().find(needle)
            if idx >= 0 and (verb_pos < 0 or idx < verb_pos):
                verb_pos = idx + 1
                matched_verb = verb
        if verb_pos < 0:
            continue
        if verb_pos == 0:
            fact = rest[len(matched_verb):].lstrip(" :,-")
        else:
            fact = rest[verb_pos + len(matched_verb):].lstrip(" :,-")
        fact = _strip_trailing_punct(fact.strip())
        return fact or None
    return None


def _infer_category(fact: str) -> str:
    """Infer the memory category from the fact's wording (regex only)."""
    if contains_any_phrase(fact, ("i am", "my name is", "i'm")):
        return "identity"
    if has_any_word(fact, ("prefer", "want", "like", "always")):
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

        normalized = normalize_affirmation(user_message)
        if not normalized:
            return None

        if not (
            is_affirmation(user_message)
            or normalized in _MEMORY_CONFIRMATION_SIGNALS
        ):
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
        fact = _extract_proposal_fact(response_text)
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
