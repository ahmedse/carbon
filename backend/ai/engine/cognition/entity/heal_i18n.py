"""Arabic needles for ``heal`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

CORRECTION_AR = ("غلط", "مخطأ", "ليس صحيح", "ليس صحيحاً", "هذا خطأ")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
