"""User-preference store port — durable per-user preference persistence.

Replaces the engine's direct ``ai.models.AIUserProfile`` ORM access in
``ai.engine.learning.preferences.SessionPreferenceStore`` (P2-03).  The host
adapter reads/writes the durable profile; the engine owns the classifier and
the prompt-constraint rendering.  Methods are synchronous so async callers
(the turn runner) wrap them in ``sync_to_async`` as before.
"""
from __future__ import annotations

from typing import Protocol


class UserPreferenceStore(Protocol):
    """Durable per-user preference access keyed by ``host_user_id``."""

    def get_preferences(self, host_user_id: str) -> dict[str, str]:
        """Return the ``{'verbosity', 'format', 'depth'}`` triple."""
        ...

    def save_preferences(self, host_user_id: str, prefs: dict[str, str]) -> None:
        """Persist the verbosity/format/depth triple for ``host_user_id``."""
        ...

    def reset_preferences(self, host_user_id: str) -> None:
        """Reset preferences to their defaults for ``host_user_id``."""
        ...
