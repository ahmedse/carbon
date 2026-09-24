"""Arabic needles for ``memory_recall`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

STORE_REMEMBER_AR = ("تذكر", "احفظ")
HOST_IDENTITY_AR = ("مدير", "قسم", "رقم الموظف")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
