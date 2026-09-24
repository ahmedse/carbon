"""Arabic needles for ``state_store`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

EMPTY_PAYSLIP_AR = ("لم أجد قسائم",)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
