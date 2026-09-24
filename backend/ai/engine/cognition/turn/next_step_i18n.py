"""Arabic needles for ``next_step`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


NEXT_ASK_AR = T("turn/next_step_i18n.py::NEXT_ASK_AR")
CONTINUER_AR = T("turn/next_step_i18n.py::CONTINUER_AR")
PAYROLL_AR = T("turn/next_step_i18n.py::PAYROLL_AR")


OFFER = T("turn/next_step_i18n.py::OFFER")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
