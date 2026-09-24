"""Arabic needles for ``report_clarify`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


BROAD_REPORT_AR = T("turn/report_clarify_i18n.py::BROAD_REPORT_AR")
SCOPED_AR = T("turn/report_clarify_i18n.py::SCOPED_AR")
ASPECT_PICK_AR = T("turn/report_clarify_i18n.py::ASPECT_PICK_AR")
PRIOR_CLARIFY_AR = T("turn/report_clarify_i18n.py::PRIOR_CLARIFY_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)


def broad_report_ar(text: str) -> bool:
    raw = text or ""
    if "تقرير" not in raw and "report" not in raw.casefold():
        return False
    return any(n in raw for n in BROAD_REPORT_AR)
