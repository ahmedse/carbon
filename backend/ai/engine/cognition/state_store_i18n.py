"""Arabic needles for ``state_store`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T

EMPTY_PAYSLIP_AR = T("state_store_i18n.py::EMPTY_PAYSLIP_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
