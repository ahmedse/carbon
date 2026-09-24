"""Arabic needles for ``contracts`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

NONEXISTENCE_AR = ("لا يوجد", "غير موجود", "لم يتم العثور")
UNIVERSAL_AR = ("جميع الموظفين",)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
