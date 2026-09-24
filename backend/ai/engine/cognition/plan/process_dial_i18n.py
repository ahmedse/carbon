"""Arabic needles for ``process_dial`` (ADR-0049 L7). No ``compiled regex``."""
from __future__ import annotations

LOAN_BRIEF_AR = ("قرض", "قروضي", "أريد قرض", "اريد قرض", "تقديم قرض")
ATTENDANCE_BRIEF_AR = (
    "استئذان",
    "إذن حضور",
    "اذن حضور",
    "ساعات قصيرة",
    "سجل حضوري الآن",
    "سجل حضورى الان",
)
COMPOSITE_CONDITIONAL_AR = (
    "إذا",
    "اذا",
    "إن كان",
    "ان كان",
    "لو",
    "في حال",
    "توقف",
    "وإلا",
    "والا",
    "فلا",
    "لا تقدم",
    "لا تطلب",
    "إذا لا",
    "اذا لا",
    "إن لم",
    "ان لم",
)
COMPOSITE_PARALLEL_AR = (
    "في الوقت نفسه",
    "في نفس الوقت",
    "بالتوازي",
    "بشكل متواز",
)
COMPOSITE_READ_WRITE_AR = (
    "راجع",
    "تحقق",
    "افحص",
    "تأكد",
    "اطلع",
    "شوف",
    "ثم",
    "بعدها",
    "وبعد ذلك",
    "قبل أن",
    "قبل ان",
    "قدّم",
    "قدم",
    "اطلب",
    "أرسل",
    "ارسل",
)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
