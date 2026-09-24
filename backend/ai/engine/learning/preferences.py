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

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ai.engine.ports.preferences import UserPreferenceStore
from ai.engine.text.word_match import contains_any_phrase, has_any_word

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


# ── Signal detection (no pre-compiled regex — ADR-0049 L7) ───────────────────

_BRIEF_PHRASES = (
    "in a hurry", "keep it short", "2-minute", "2 minute", "two-minute",
    "two minute", "tl;dr", "tl,dr", "don't go into detail", "dont go into detail",
    "skip the intro", "no intro", "quick answer",
)
_BRIEF_WORDS = (
    "quickly", "quick", "briefly", "brief", "shortly", "short", "concisely",
    "concise", "summarize", "summarise",
)
_VERBOSE_PHRASES = (
    "explain in detail", "in depth", "step by step", "give me the full",
    "give me full", "give me the complete", "give me complete", "more detail",
    "walk me through", "in full",
)
_VERBOSE_WORDS = (
    "explain", "detailed", "thoroughly", "thorough", "elaborate", "comprehensive",
)
_BULLETS_PHRASES = (
    "bullet points", "bullet point", "as a list", "list format", "numbered list",
    "in bullets", "in bullet",
)
_BULLETS_WORDS = ("bulleted",)
_PROSE_WORDS = ("prose", "paragraph", "narrative")
_PROSE_PHRASES = (
    "no bullets", "no bullet", "not as a list", "flowing text",
)
_EXPERT_PHRASES = (
    "i am an expert", "i'm an expert", "i am a expert", "i'm a expert",
    "expert level", "technical detail", "assume i know", "skip the basics",
    "skip basics", "i know the basics",
)
_EXPERT_WORDS = ("advanced",)
_BEGINNER_WORDS = ("beginner",)
_BEGINNER_PHRASES = (
    "explain it simply", "explain simply", "explain to me", "explain from scratch",
    "i am new to this", "i'm new to this", "i am new", "i'm new",
    "not familiar", "not sure", "not certain", "what is a", "what is an",
)


def _is_brief_signal(text: str) -> bool:
    return has_any_word(text, _BRIEF_WORDS) or contains_any_phrase(text, _BRIEF_PHRASES)


def _is_verbose_signal(text: str) -> bool:
    return has_any_word(text, _VERBOSE_WORDS) or contains_any_phrase(text, _VERBOSE_PHRASES)


def _is_bullets_signal(text: str) -> bool:
    return has_any_word(text, _BULLETS_WORDS) or contains_any_phrase(text, _BULLETS_PHRASES)


def _is_prose_signal(text: str) -> bool:
    return has_any_word(text, _PROSE_WORDS) or contains_any_phrase(text, _PROSE_PHRASES)


def _is_expert_signal(text: str) -> bool:
    return has_any_word(text, _EXPERT_WORDS) or contains_any_phrase(text, _EXPERT_PHRASES)


def _is_beginner_signal(text: str) -> bool:
    return has_any_word(text, _BEGINNER_WORDS) or contains_any_phrase(text, _BEGINNER_PHRASES)


class PreferenceClassifier:
    """Reads a user message and returns detected preference signals.

    Zero LLM cost. No domain terms.
    """

    def classify(self, user_message: str) -> PreferenceSignal:
        signal = PreferenceSignal()

        if _is_brief_signal(user_message):
            signal.verbosity = Verbosity.BRIEF
        elif _is_verbose_signal(user_message):
            signal.verbosity = Verbosity.VERBOSE

        if _is_bullets_signal(user_message):
            signal.format = Format.BULLETS
        elif _is_prose_signal(user_message):
            signal.format = Format.PROSE

        if _is_expert_signal(user_message):
            signal.depth = Depth.EXPERT
        elif _is_beginner_signal(user_message):
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
