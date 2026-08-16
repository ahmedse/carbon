"""Thread-safe in-process cancellation registry for AI generations.

Sprint 14: ``send_message_stream`` registers a ``threading.Event`` per
conversation while a generation is in flight.  A concurrent ``stop`` request
(from another worker thread of the same Django server) sets that event; the
stream generator polls it between frames and cancels promptly.

The registry is deliberately process-local: a stop request only interrupts a
generation served by the same process.  The durable ``AIGeneration`` row is
the cross-process source of truth for reporting cancellation.
"""

from __future__ import annotations

import threading


class GenerationRegistry:
    """A per-conversation mapping of cancellation ``threading.Event``.

    ``start`` installs a fresh (unset) event; ``cancel`` sets the event if
    one is present; ``is_cancelled`` reports whether the event has been set;
    ``finish`` removes the entry so a later generation starts clean.
    """

    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self, conversation_id: str) -> None:
        """Install a fresh cancellation event for ``conversation_id``."""
        with self._lock:
            self._events[conversation_id] = threading.Event()

    def cancel(self, conversation_id: str) -> bool:
        """Set the cancellation event. Returns True if a generation was running."""
        with self._lock:
            event = self._events.get(conversation_id)
        if event is None:
            return False
        event.set()
        return True

    def is_cancelled(self, conversation_id: str) -> bool:
        """Return True if the generation for ``conversation_id`` was cancelled."""
        with self._lock:
            event = self._events.get(conversation_id)
        return event is not None and event.is_set()

    def finish(self, conversation_id: str) -> None:
        """Remove the registry entry for ``conversation_id``."""
        with self._lock:
            self._events.pop(conversation_id, None)


GENERATIONS = GenerationRegistry()
