"""Arabic needles for ``pending_mutation`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

FIRST_PERSON_AR = T("dialogue/pending_mutation_i18n.py::FIRST_PERSON_AR")
ACTION_VERB_AR = T("dialogue/pending_mutation_i18n.py::ACTION_VERB_AR")
ASKS_PERMISSION_AR = T("dialogue/pending_mutation_i18n.py::ASKS_PERMISSION_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
