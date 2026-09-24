"""Arabic needles for ``action_deflection`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

RETRY_AR = (
    "أعد المحاولة", "حاول مرة أخرى", "المحاولة مرة أخرى",
    "إكمال", "اكمال", "أكمل", "اكمل", "خطوات", "عملية", "عمليه", "إجراءات",
    "التأكيد", "التاكيد", "أولا", "ثم",
)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
