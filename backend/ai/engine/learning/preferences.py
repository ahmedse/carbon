"""In-session preference classifier and session preference store (GAP-4).

Detects user preference signals from natural language messages and
applies them as system-prompt constraints for remaining turns.

Domain-agnostic: signals are about communication style (verbosity, format,
depth), not topic or domain content.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional


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
    """Thread-safe store of SessionPreferences keyed by conversation_id."""

    def __init__(self) -> None:
        self._store: dict[str, SessionPreferences] = {}
        self._lock = threading.Lock()

    def get(self, conversation_id: str) -> SessionPreferences:
        with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = SessionPreferences()
            return self._store[conversation_id]

    def update(self, conversation_id: str, signal: PreferenceSignal) -> None:
        if signal.is_empty():
            return
        with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = SessionPreferences()
            self._store[conversation_id].apply_signal(signal)

    def to_prompt_constraints(self, conversation_id: str) -> str:
        return self.get(conversation_id).to_prompt_constraints()

    def clear(self, conversation_id: str) -> None:
        with self._lock:
            self._store.pop(conversation_id, None)


# ── Process-level singleton ────────────────────────────────────────────────────

_session_preference_store: SessionPreferenceStore | None = None


def get_session_preference_store() -> SessionPreferenceStore:
    global _session_preference_store
    if _session_preference_store is None:
        _session_preference_store = SessionPreferenceStore()
    return _session_preference_store
