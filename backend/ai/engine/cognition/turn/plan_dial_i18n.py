"""Arabic needles for ``plan_dial`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


RESTYLE_AR = T("turn/plan_dial_i18n.py::RESTYLE_AR")
NEW_CONTENT_AR = T("turn/plan_dial_i18n.py::NEW_CONTENT_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
