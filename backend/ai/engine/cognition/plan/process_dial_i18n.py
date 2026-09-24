"""Arabic needles for ``process_dial`` (ADR-0049 L7). No ``compiled regex``."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


LOAN_BRIEF_AR = T("plan/process_dial_i18n.py::LOAN_BRIEF_AR")
ATTENDANCE_BRIEF_AR = T("plan/process_dial_i18n.py::ATTENDANCE_BRIEF_AR")
COMPOSITE_CONDITIONAL_AR = T("plan/process_dial_i18n.py::COMPOSITE_CONDITIONAL_AR")
COMPOSITE_PARALLEL_AR = T("plan/process_dial_i18n.py::COMPOSITE_PARALLEL_AR")
COMPOSITE_READ_WRITE_AR = T("plan/process_dial_i18n.py::COMPOSITE_READ_WRITE_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
