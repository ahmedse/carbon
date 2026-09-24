"""Arabic needles for ``memory_recall`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


STORE_REMEMBER_AR = T("turn/memory_recall_i18n.py::STORE_REMEMBER_AR")
HOST_IDENTITY_AR = T("turn/memory_recall_i18n.py::HOST_IDENTITY_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
