"""Arabic needles for ``chat_surface`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.pack_vocab import V


LEAVE_INTENT_AR = ("إجاز", "اجاز", "عارضة", "عارده", "سنوي")
LOAN_INTENT_AR = (V("t_قرض"),)
ATTENDANCE_INTENT_AR = ("استئذان", V("t_حضور"))
MANAGER_REVIEW_AR = (
    "موافق على",
    "اعتماد",
    "رفض",
)
PROFILE_CHANGE_AR = (
    "تغيير",
    "تحديث",
    "ملف",
    "بيانات",
    "جوال",
    "بريد",
    "عنوان",
    "آيبان",
    "ايبان",
)
ESS_TOPIC_AR = ("إجاز", "اجاز", V("t_قرض"), "استئذان", "تقديم")
ESS_WRITE_VERB_AR = ("أريد", "اريد", "أبغى", "ابغى", "اطلب", "أطلب", "تقديم", "قدّم", "قدm")

FIELD_LABELS = {
    "leave_type": (V("t_leave_type_2"), "نوع الإجازة"),
    "start_date": ("Start date", "تاريخ البداية"),
    "end_date": ("End date", "تاريخ النهاية"),
    "days": ("Days", "الأيام"),
    "reason": ("Reason", "السبب"),
    "loan_type": (V("t_loan_type"), "نوع القرض"),
    "principal": ("Principal", "المبلغ"),
    "term_months": ("Term (months)", "المدة (أشهر)"),
    "interest_rate": ("Interest rate", "الفائدة"),
    "permission_type": ("Permission type", "نوع الاستئذان"),
    "hours": ("Hours", "الساعات"),
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
