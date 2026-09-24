"""Arabic needles for ``plan_dial`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

RESTYLE_AR = (
    "بالعرب", "بالإنجليز", "بالانجليز", "بالتفصيل", "أكثر تفصيل", "اكثر تفصيل",
    "بتفصيل أكثر", "بتفصيل اكثر", "وضّح أكثر", "وضح اكثر", "أعد الصياغة", "اعد الصياغة",
    "باختصار", "مختصر",
)
NEW_CONTENT_AR = ('قرض', 'إجاز', 'اجاز', 'استئذان', 'راتب', 'رواتب', 'تقرير', 'قدّم', 'قدم', 'اطلب')


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
