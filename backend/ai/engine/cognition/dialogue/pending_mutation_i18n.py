"""Arabic needles for ``pending_mutation`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

FIRST_PERSON_AR = (
    "سأ",
    "سوف أ",
    "يمكنني",
    "أستطيع",
    "هل أ",
    "أن أ",
    "تريدني",
    "تريد أن أ",
    "دعني",
)
ACTION_VERB_AR = (
    "تقديم",
    "أقدم",
    "إعداد",
    "أعد",
    "إنشاء",
    "أنشئ",
    "تسجيل",
    "أسجل",
    "إرسال",
    "أرسل",
    "حجز",
    "أحجز",
    "تعديل",
    "أعدل",
    "تحديث",
    "أحدث",
    "إلغاء",
    "ألغي",
    "اعتماد",
    "تنفيذ",
    "أنفذ",
    "أبدأ",
    "البدء",
    "أتابع",
    "المتابعة",
    "إكمال",
    "أكمل",
)
ASKS_PERMISSION_AR = (
    "يرجى",
    "يُرجى",
    "الرجاء",
    "برجاء",
    "التأكيد",
    "هل تريد",
    "قبل تقديم",
    "قبل إرسال",
    "قبل تنفيذ",
)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
