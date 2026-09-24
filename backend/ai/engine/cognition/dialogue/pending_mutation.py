from __future__ import annotations
from ai.engine.pack_vocab import V
V("t_consent_resume_remember_an_action_the")


import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.engine.cognition.dialogue.pending_mutation_i18n import (
    ACTION_VERB_AR,
    ASKS_PERMISSION_AR,
    FIRST_PERSON_AR,
    any_needle,
)

#: Proposals older than this are stale — the user moved on.
DEFAULT_TTL_TURNS = 2

_MAX_PROPOSAL_CHARS = 1200

# ── Proposal detection ───────────────────────────────────────────────────────
# Two signals must BOTH be present in the assistant's final text:
#   1. an offer to act on the user's behalf, and
#   2. a request for the go-ahead.
# Prose that merely reports data ("you have 23 days left") never qualifies.

# Detection is built from three independent MARKERS rather than whole
# sentences. Matching full phrasings is a losing game — the model rewords the
# same offer every turn ("هل أتابع؟", "هل تريدني الآن أن أبدأ تعديل الخطة؟",
# "Shall I proceed?") and each new wording silently reopened the loop.

#: The assistant speaking about its OWN next act, in the first person.
_FIRST_PERSON = re.compile(
    r"\b(?:i'?ll|i\s+will|i\s+can|i\s+am\s+going\s+to|let\s+me|"
    r"shall\s+i|should\s+i|may\s+i|me\s+to)\b",
    re.IGNORECASE,
)

#: A verb that changes something — reading data is not a proposal.
_ACTION_VERB = re.compile(
    r"\b(?:submit|file|create|request|book|register|raise|send|apply|"
    r"prepare|draft|record|schedule|update|edit|modify|revise|cancel|"
    r"approve|replan|fork|proceed|execute|run|start|begin|continue)\b",
    re.IGNORECASE,
)

#: Explicitly handing the decision back to the user.
_ASKS_PERMISSION = re.compile(
    r"[?\u061F]\s*$"
    r"|\b(?:please\s+)?confirm\b"
    r"|\blet\s+me\s+know\b",
    re.IGNORECASE | re.MULTILINE,
)


def detect_action_proposal(response_text: str) -> str | None:
    """Return the proposal text when the assistant offered to act and asked.

    Requires all three markers: the assistant talking about its own next act,
    a verb that would change something, and the decision handed back to the
    user. An ordinary answer ("you have 23 days left") has none of them.
    """
    text = (response_text or "").strip()
    if not text:
        return None
    if not (_FIRST_PERSON.search(text) or any_needle(text, FIRST_PERSON_AR)):
        return None
    if not (_ACTION_VERB.search(text) or any_needle(text, ACTION_VERB_AR)):
        return None
    if not (_ASKS_PERMISSION.search(text) or any_needle(text, ASKS_PERMISSION_AR)):
        return None
    return text[:_MAX_PROPOSAL_CHARS]


def build_resume_message(proposal: str, *, original_request: str = "") -> str:
    """Turn an approved proposal into an explicit instruction for the model."""
    lines = [
        "The user has just approved the action I proposed in my previous "
        "message. Carry it out now by calling the matching platform action "
        "with the details below — do not ask the same confirmation question "
        "again, and do not answer with a summary only.",
        "",
        "Proposal the user approved:",
        (proposal or "").strip(),
    ]
    if (original_request or "").strip():
        lines += ["", "The user's original request:", original_request.strip()]
    return "\n".join(lines)


@dataclass
class PendingMutation:
    conv_id: str
    proposal: str
    original_request: str = ""
    ttl_turns: int = DEFAULT_TTL_TURNS
    set_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PendingMutationStore:
    """In-process per-conversation proposal store. Thread-safe."""

    def __init__(self) -> None:
        self._store: dict[str, PendingMutation] = {}
        self._lock = threading.Lock()

    def set_pending(
        self,
        conv_id: str,
        proposal: str,
        *,
        original_request: str = "",
        ttl_turns: int = DEFAULT_TTL_TURNS,
    ) -> None:
        if not conv_id or not (proposal or "").strip():
            return
        with self._lock:
            self._store[conv_id] = PendingMutation(
                conv_id=conv_id,
                proposal=proposal.strip()[:_MAX_PROPOSAL_CHARS],
                original_request=(original_request or "").strip()[:500],
                ttl_turns=ttl_turns,
            )

    def get(self, conv_id: str) -> dict | None:
        with self._lock:
            pm = self._store.get(conv_id)
            return self._to_dict(pm) if pm else None

    def take_if_affirmed(self, conv_id: str, user_message: str) -> dict | None:
        """Pop the proposal when ``user_message`` is a short yes, else None."""
        from ai.engine.cognition.dialogue.affirmation import is_affirmation

        if not conv_id or not is_affirmation(user_message):
            return None
        with self._lock:
            pm = self._store.pop(conv_id, None)
            return self._to_dict(pm) if pm else None

    def age_out(self, conv_id: str) -> None:
        """Consume one turn of the proposal's lifetime; drop it at zero."""
        with self._lock:
            pm = self._store.get(conv_id)
            if pm is None:
                return
            pm.ttl_turns -= 1
            if pm.ttl_turns <= 0:
                self._store.pop(conv_id, None)

    def clear(self, conv_id: str) -> None:
        with self._lock:
            self._store.pop(conv_id, None)

    @staticmethod
    def _to_dict(pm: PendingMutation) -> dict:
        return {
            "conv_id": pm.conv_id,
            "proposal": pm.proposal,
            "original_request": pm.original_request,
            "set_at": pm.set_at,
        }


_pending_mutation_store: PendingMutationStore | None = None


def get_pending_mutation_store() -> PendingMutationStore:
    global _pending_mutation_store
    if _pending_mutation_store is None:
        _pending_mutation_store = PendingMutationStore()
    return _pending_mutation_store
