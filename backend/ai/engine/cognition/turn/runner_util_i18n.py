"""Arabic needles for ``runner_util`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

ESS_TOPIC_AR = (
    "إجاز",
    "اجاز",
    "قرض",
    "راتب",
    "رواتب",
    "حضور",
    "غياب",
    "قسيم",
    "استئذان",
    "سلف",
)
FIRST_PERSON_AR = (
    "أنا",
    "انا",
    "عندي",
    "لدي",
    "أريد",
    "اريد",
    "طلبت",
    "راتبي",
    "إجازتي",
    "اجازتي",
    "قرضي",
    "حضوري",
    "رصيدي",
    "قسيمتي",
)
SCOPE_BYPASS_AR = (
    "تجاهل",
    "تجاوز",
    "صلاحيات",
    "قيود",
    "حماي",
    "كلمة المرور",
    "كلمات المرور",
    "كلمات مرور",
    "كلمة السر",
    "موجه النظام",
    "صلاحيات المدير",
)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
