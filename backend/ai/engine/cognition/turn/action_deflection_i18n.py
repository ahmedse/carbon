"""Arabic needles for ``action_deflection`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

RETRY_AR = T("turn/action_deflection_i18n.py::RETRY_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
