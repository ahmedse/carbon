"""Arabic needles for ``report_clarify`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

BROAD_REPORT_AR = (
    "تقرير",
    "رواتب",
    "راتب",
    "مسير",
    "الأجور",
    "كامل",
    "شامل",
    "مفصل",
)
SCOPED_AR = (
    "مجلس",
    "إدارة",
    "توزيع",
    "شرائح",
    "تأمينات",
    "استقطاع",
    "حسب",
    "رسوم",
    "مخططات",
)
ASPECT_PICK_AR = (
    "توزيع",
    "شرائح",
    "مسيرات",
    "ملتزم",
    "مسودة",
    "فشل",
    "تأمينات",
    "مجلس",
    "ملخص",
    "كل",
    "أربعة",
    "الجوانب",
    "الخيارات",
    "ما سبق",
)
PRIOR_CLARIFY_AR = (
    "على ماذا تريد التركيز",
    "بكل سرور أساعد في تقرير الرواتب",
)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)


def broad_report_ar(text: str) -> bool:
    raw = text or ""
    if "تقرير" not in raw and "report" not in raw.casefold():
        return False
    return any(n in raw for n in BROAD_REPORT_AR)
