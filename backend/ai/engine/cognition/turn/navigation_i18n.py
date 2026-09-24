"""Arabic needles for ``navigation`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


HOW_WHERE_AR = T("turn/navigation_i18n.py::HOW_WHERE_AR")
PLACE_TOPIC_AR = T("turn/navigation_i18n.py::PLACE_TOPIC_AR")
SELF_READ_POSSESSIVE_EN = T("turn/navigation_i18n.py::SELF_READ_POSSESSIVE_EN")
SELF_READ_POSSESSIVE_AR = T("turn/navigation_i18n.py::SELF_READ_POSSESSIVE_AR")

NAV_VERB_AR = T("turn/navigation_i18n.py::NAV_VERB_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
