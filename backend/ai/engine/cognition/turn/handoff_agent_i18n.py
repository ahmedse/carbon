"""Arabic needles and bilingual maps for ``handoff_agent`` (ADR-0049 L7).

No ``compiled regex`` in this module.
"""
from __future__ import annotations

READY_TO_SUBMIT_AR = ("هل تحتاج", "هل ينقص", "هل بقي")
QUESTION_AR = ("؟", "متى", "هل", "كيف", "لماذا", "ما", "أين", "وين")
AFFIRM_AR = ("نعم", "أجل", "بالضبط", "هذا كل شيء", "تمام", "موافق")
JAILBREAK_AR = ("تجاهل", "تجاوز")

LOAN_EMERGENCY_AR = ("طارئ", "طارئة", "طارئه")
LOAN_HOUSING_AR = ("سكن", "عقاري")
LOAN_SALARY_AR = ("راتب",)
LOAN_CAR_AR = ("سيارة", "سياره")
LOAN_PERSONAL_AR = ("شخصي",)

LEAVE_ANNUAL_AR = ("سنوي", "سنوية", "سنويه")
LEAVE_SICK_AR = ("مرض", "مرضية", "مرضيه")
LEAVE_EMERGENCY_AR = ("طارئ", "طارئة", "عارضة", "عارضه")
LEAVE_UNPAID_AR = ("بدون راتب", "بدون  راتب")
LEAVE_MATERNITY_AR = ("وضع", "أمومة")

PERM_OFFICIAL_AR = ("رسمي",)
PERM_MEDICAL_AR = ("طبي",)
PERM_EMERGENCY_AR = ("طارئ",)
PERM_PERSONAL_AR = ("شخصي",)

AMOUNT_CURRENCY_AR = ("ريال", "دينار", "دنانير")
AMOUNT_PREFIX_AR = ("مبلغ", "قرض")
MONTHS_AR = ("شهر", "أشهر", "اشهر")
DAYS_AR = ("يوم", "أيام", "ايام")
HOURS_AR = ("ساعة", "ساعات")
SLOT_STATUS_AR = ("تم تسجيله",)
RELATIVE_DAY_AR = ("اليوم",)

CLARIFY_TEXT = {
    "submit_my_loan": {
        "loan_type": {
            "en": "What type of loan are you interested in?",
            "ar": "أي نوع قرض تريد؟",
        },
        "principal": {
            "en": "How much do you need?",
            "ar": "كم المبلغ الذي تحتاجه؟",
        },
    },
    "submit_my_leave": {
        "leave_type": {
            "en": "What type of leave do you want to take?",
            "ar": "أي نوع إجازة تريد؟",
        },
        "start_date": {
            "en": "Which dates do you want to take leave?",
            "ar": "ما تواريخ الإجازة؟",
        },
    },
    "submit_my_attendance_permission": {
        "permission_type": {
            "en": "What type of permission do you need?",
            "ar": "أي نوع استئذان تحتاج؟",
        },
        "hours": {
            "en": "How many hours do you need?",
            "ar": "كم ساعة تحتاج؟",
        },
    },
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
