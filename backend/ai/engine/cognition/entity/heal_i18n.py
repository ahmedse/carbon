"""Arabic needles for ``heal`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

CORRECTION_AR = T("entity/heal_i18n.py::CORRECTION_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
