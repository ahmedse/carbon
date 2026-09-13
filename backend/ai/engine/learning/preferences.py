"""Preference classifier and durable per-user preference store (GAP-4).

Detects user preference signals from natural language messages and
applies them as system-prompt constraints for remaining turns.

Domain-agnostic: signals are about communication style (verbosity, format,
depth), not topic or domain content.

P1-12: preferences are persisted on ``AIUserProfile`` (host-owned durable
state), keyed by ``host_user_id``, so they survive process restarts. The
classifier remains domain-agnostic; only the persistence seam reaches into
the host adapter (``ai.adapters.preferences``) via the
``ai.engine.ports.preferences.UserPreferenceStore`` port.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ai.engine.ports.preferences import UserPreferenceStore

# Host-injected adapter provider (constructed once in host code). The engine
# never imports ``ai.adapters``; callers wire it during bootstrap.
_user_preference_store_provider: Callable[[], UserPreferenceStore] | None = None


def set_user_preference_store_provider(provider: Callable[[], UserPreferenceStore]) -> None:
    """Inject the host's ``UserPreferenceStore`` adapter at bootstrap."""
    global _user_preference_store_provider
    _user_preference_store_provider = provider


def _resolve_user_preference_store() -> UserPreferenceStore:
    if _user_preference_store_provider is None:
        raise RuntimeError(
            "UserPreferenceStore adapter not injected; call "
            "ai.engine.learning.preferences.set_user_preference_store_provider() during bootstrap"
        )
    return _user_preference_store_provider()


class Verbosity(str, Enum):
    BRIEF = "brief"
    NORMAL = "normal"
    VERBOSE = "verbose"


class Format(str, Enum):
    BULLETS = "bullets"
    PROSE = "prose"
    MIXED = "mixed"


class Depth(str, Enum):
    BEGINNER = "beginner"
    NORMAL = "normal"
    EXPERT = "expert"


@dataclass
class PreferenceSignal:
    verbosity: Optional[Verbosity] = None
    format: Optional[Format] = None
    depth: Optional[Depth] = None

    def is_empty(self) -> bool:
        return (
            self.verbosity is None
            and self.format is None
            and self.depth is None
        )


@dataclass
class SessionPreferences:
    verbosity: Verbosity = Verbosity.NORMAL
    format: Format = Format.MIXED
    depth: Depth = Depth.NORMAL

    def apply_signal(self, signal: PreferenceSignal) -> None:
        if signal.verbosity is not None:
            self.verbosity = signal.verbosity
        if signal.format is not None:
            self.format = signal.format
        if signal.depth is not None:
            self.depth = signal.depth

    def to_prompt_constraints(self) -> str:
        """Return constraint lines to append to the system prompt."""
        constraints: list[str] = []
        if self.verbosity == Verbosity.BRIEF:
            constraints.append(
                "RESPONSE STYLE: Be concise — aim for 2 minutes of reading "
                "time or less (~150–200 words)."
            )
        elif self.verbosity == Verbosity.VERBOSE:
            constraints.append(
                "RESPONSE STYLE: Be thorough and detailed in your response."
            )
        if self.format == Format.BULLETS:
            constraints.append(
                "RESPONSE FORMAT: Use bullet points only, no long paragraphs."
            )
        elif self.format == Format.PROSE:
            constraints.append(
                "RESPONSE FORMAT: Use flowing prose, avoid bullet lists."
            )
        if self.depth == Depth.BEGINNER:
            constraints.append(
                "RESPONSE DEPTH: Explain concepts clearly for a non-expert audience."
            )
        elif self.depth == Depth.EXPERT:
            constraints.append(
                "RESPONSE DEPTH: Assume expert-level background; skip basics."
            )
        return "\n".join(constraints)


# ── Signal detection patterns ──────────────────────────────────────────────────

_BRIEF_RE = re.compile(
    r"\b(?:in\s+a\s+hurry|quick(?:ly)?|brief(?:ly)?|short(?:ly)?|concise(?:ly)?|"
    r"keep\s+it\s+short|2[- ]minute|two[- ]minute|tl[;,]?dr|"
    r"don'?t\s+go\s+into\s+detail|skip\s+the\s+intro|no\s+intro|"
    r"quick\s+answer|summarize|summarise)\b",
    re.IGNORECASE,
)
_VERBOSE_RE = re.compile(
    r"\b(?:explain(?:\s+in\s+detail)?|detailed|thorough(?:ly)?|in\s+depth|"
    r"step\s+by\s+step|elaborate|give\s+me\s+(?:the\s+)?(?:full|complete)|"
    r"more\s+detail|comprehensive|walk\s+me\s+through|in\s+full)\b",
    re.IGNORECASE,
)
_BULLETS_RE = re.compile(
    r"\b(?:bullet\s+points?|as\s+a\s+list|list\s+format|numbered\s+list|"
    r"bulleted|in\s+bullets?)\b",
    re.IGNORECASE,
)
_PROSE_RE = re.compile(
    r"\b(?:prose|paragraph|no\s+bullets?|not\s+as\s+a\s+list|"
    r"flowing\s+text|narrative)\b",
    re.IGNORECASE,
)
_EXPERT_RE = re.compile(
    r"\b(?:I(?:'m|\s+am)\s+(?:an?\s+)?expert|expert\s+level|technical\s+detail|advanced|"
    r"assume\s+I\s+know|skip\s+(?:the\s+)?basics?|I\s+know\s+the\s+basics)\b",
    re.IGNORECASE,
)
_BEGINNER_RE = re.compile(
    r"\b(?:beginner|explain\s+(?:it\s+)?(?:simply|to\s+me|from\s+scratch)|"
    r"I(?:'m|\s+am)\s+new(?:\s+to\s+this)?|not\s+(?:familiar|sure|certain)|"
    r"what\s+is\s+(?:a|an)\b)\b",
    re.IGNORECASE,
)


class PreferenceClassifier:
    """Reads a user message and returns detected preference signals.

    Zero LLM cost. No domain terms.
    """

    def classify(self, user_message: str) -> PreferenceSignal:
        signal = PreferenceSignal()

        if _BRIEF_RE.search(user_message):
            signal.verbosity = Verbosity.BRIEF
        elif _VERBOSE_RE.search(user_message):
            signal.verbosity = Verbosity.VERBOSE

        if _BULLETS_RE.search(user_message):
            signal.format = Format.BULLETS
        elif _PROSE_RE.search(user_message):
            signal.format = Format.PROSE

        if _EXPERT_RE.search(user_message):
            signal.depth = Depth.EXPERT
        elif _BEGINNER_RE.search(user_message):
            signal.depth = Depth.BEGINNER

        return signal


class SessionPreferenceStore:
    """Durable per-user preference store backed by ``AIUserProfile`` (P1-12).

    Replaces the in-memory, conversation-keyed dict with host-owned durable
    state: preferences are keyed by ``host_user_id`` (the authenticated user)
    and survive process restarts. The classifier stays domain-agnostic; only
    the persistence seam reaches into the host adapter
    (``DjangoUserPreferenceAdapter``).

    Methods are synchronous Django-ORM calls; async callers (the turn runner)
    wrap them in ``sync_to_async``.
    """

    def __init__(self, store: UserPreferenceStore | None = None):
        if store is None:
            store = _resolve_user_preference_store()
        self._store = store

    def get(self, host_user_id: str) -> SessionPreferences:
        prefs = self._store.get_preferences(host_user_id)
        return SessionPreferences(
            verbosity=Verbosity(prefs["verbosity"]),
            format=Format(prefs["format"]),
            depth=Depth(prefs["depth"]),
        )

    def update(self, host_user_id: str, signal: PreferenceSignal) -> None:
        if signal.is_empty():
            return
        prefs = self.get(host_user_id)
        prefs.apply_signal(signal)
        self._store.save_preferences(
            host_user_id,
            {
                "verbosity": prefs.verbosity.value,
                "format": prefs.format.value,
                "depth": prefs.depth.value,
            },
        )

    def to_prompt_constraints(self, host_user_id: str) -> str:
        return self.get(host_user_id).to_prompt_constraints()

    def clear(self, host_user_id: str) -> None:
        self._store.reset_preferences(host_user_id)


# ── Process-level singleton ────────────────────────────────────────────────────

_session_preference_store: SessionPreferenceStore | None = None


def get_session_preference_store() -> SessionPreferenceStore:
    global _session_preference_store
    if _session_preference_store is None:
        _session_preference_store = SessionPreferenceStore()
    return _session_preference_store
