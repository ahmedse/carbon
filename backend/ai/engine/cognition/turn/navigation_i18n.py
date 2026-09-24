"""Arabic needles for ``navigation`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

HOW_WHERE_AR = ("كيف أقدم", "كيف اقدم", "كيف أفتح", "كيف افتح", "وين ", "أين ", "اين ")
PLACE_TOPIC_AR = (
    "قرض",
    "قروض",
    "إجازة",
    "اجازة",
    "راتب",
    "رواتب",
    "قسيمة",
    "حضور",
    "رئيسية",
    "إشعار",
)
SELF_READ_POSSESSIVE_EN = (
    "my ",
    " mine",
)
SELF_READ_POSSESSIVE_AR = (
    "إجازاتي",
    "اجازاتي",
    "إجازتي",
    "اجازتي",
    "راتبي",
    "مرتبي",
    "قروضي",
    "حضوري",
    "سلفتي",
    "قسيمة راتبي",
    "استئذاناتي",
)

NAV_VERB_AR = (
    "افتح",
    "تفتح",
    "اذهب",
    "تذهب",
    "ارني",
    "روح",
    "وديني",
    "خذني",
)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
