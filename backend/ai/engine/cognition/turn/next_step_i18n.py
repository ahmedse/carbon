"""Arabic needles for ``next_step`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

NEXT_ASK_AR = ("ماذا بعد", "وش الخطوة", "وش بعدين", "ما الخطوة", "بعدين")
CONTINUER_AR = ("بعدها", "بعدين")
PAYROLL_AR = ("قسيمة", "راتب", "استقطاع")


OFFER = {
    "submit_in_agent": {
        "en": "Next: switch to Agent to submit. Chat will not send it.",
        "ar": "التالي: بدّل إلى الوكيل لإرسال الطلب. الدردشة لا تُرسل.",
    },
    "approve_in_agent": {
        "en": "Next: open Agent and Approve, then Run.",
        "ar": "التالي: افتح الوكيل واضغط اعتماد ثم تشغيل.",
    },
    "run_in_agent": {
        "en": "Next: open Agent and Run.",
        "ar": "التالي: افتح الوكيل وشغّل الخطة.",
    },
    "confirm_in_agent": {
        "en": "Next: open Agent and confirm the waiting step.",
        "ar": "التالي: افتح الوكيل وأكّد الخطوة المنتظرة.",
    },
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
