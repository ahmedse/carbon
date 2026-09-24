"""Arabic needles and bilingual maps for ``ess_read`` (ADR-0049 L7).

No ``compiled regex`` in this module.
"""
from __future__ import annotations

LEAVE_TOPIC_AR = (
    "رصيد الاجاز",
    "رصيد الإجاز",
    "رصيد الاجازات",
    "رصيد الإجازات",
    "اجازة متبقي",
    "إجازة متبقي",
    "الاجازات المتبقي",
    "الإجازات المتبقي",
    "اجازاتي",
    "إجازاتي",
    "اجازتي",
    "إجازتي",
    "عن الاجاز",
    "عن الإجاز",
    "عن الاجازلت",
    "عن الإجازات",
    "الاجاز",
    "الإجاز",
    "الاجازة",
    "الإجازة",
    "الاجازات",
    "الإجازات",
    "الاجازلت",
    "اجازلت",
    "إجازات",
    "اجازات",
    "إجازة",
    "اجازة",
)
LEAVE_HISTORY_AR = (
    "طلبات الاجاز",
    "طلبات الإجاز",
    "سجل الاجاز",
    "سجل الإجاز",
    "سجل إجازاتي",
    "سجل اجازاتي",
    "اجازاتي السابق",
    "إجازاتي السابق",
    "اجازاتي السابقة",
    "إجازاتي السابقة",
    "عرض طلبات اجاز",
    "عرض طلبات إجاز",
)
LOAN_TOPIC_AR = ("قرض", "قروض", "سلف", "سلفة", "سلفه", "أقساط")
LOAN_SELF_AR = ("قروضي", "سلفتي", "أقساطي", "ما هي قروضي", "ما هو قروضي")
PAYSLIP_TOPIC_AR = (
    "قسيمة",
    "قسائم",
    "صافي الراتب",
    "صافي راتب",
    "صافي المرتب",
    "راتبي",
    "مرتبي",
    "مرتبتي",
)
ATTENDANCE_AR_TOKENS = (
    "حضور",
    "حضرت",
    "سجلت حضور",
    "ساعات حضور",
)
NAMED_EMP_AR = ("لـ",)
LEAVE_ZERO_CLAIM_AR = (
    "رصيد الاجاز",
    "رصيد الإجاز",
    "المتبقي: 0",
    "المتبقي 0",
    "المستخدمة: 0",
    "المستخدمة 0",
    "المعلقة: 0",
    "المعلقة 0",
    "0 يوم",
)
BARE_PLACE_AR = frozenset({
    "إجازة", "اجازة", "إجازات", "اجازات",
    "قرض", "قروض", "رواتب", "راتب", "قسائم", "قسيمة", "حضور",
})

ASPECT_FOLLOWUP_NEEDLES = (
    "ما هو الرصيد", "ماهو الرصيد", "الرصيد",
    "what's the balance", "what is the balance", "what is my balance",
    "what's my balance", "leave balance",
    "كل الأنواع", "كل الانواع", "all the types", "all types",
    "حاول مرة", "try again",
    "ليس صفر", "مو صفر", "not zero", "not a zero",
)
COMPREHENSIVE_NEEDLES = (
    "comprehensive", "full report", "all of it", "all of them", "everything",
    "تقرير شامل", "شامل", "كل شي", "كل شيء", "التفاصيل كلها",
)

HONEST_EMPTY = {
    "en": {
        "leave_history": (
            "You have no leave requests on record yet. "
            "That is not the same as a zero leave balance — "
            "ask for your leave balance if you want remaining days by type."
        ),
        "loan_history": (
            "You have no loans on record. "
            "I will not invent installment or balance figures."
        ),
        "payslip": (
            "No committed payslip lines were found for you for that period. "
            "I will not invent net-pay figures."
        ),
    },
    "ar": {
        "leave_history": (
            "لا توجد طلبات إجازة مسجّلة حتى الآن. "
            "هذا ليس معناه أن رصيد الإجازات صفر — "
            "اطلب رصيد الإجازات إن أردت الأيام المتبقية حسب النوع."
        ),
        "loan_history": (
            "لا توجد قروض مسجّلة لك. "
            "لن أخترع أرقام أقساط أو أرصدة."
        ),
        "payslip": (
            "لا توجد بنود قسيمة راتب معتمدة لهذه الفترة. "
            "لن أخترع أرقام صافي الراتب."
        ),
    },
}

UNAUTHORIZED_TEXT = {
    "en": "You are not authorized to read that data.",
    "ar": "غير مصرح لك بقراءة هذه البيانات.",
}

EMPTY_BALANCE_TEXT = {
    "en": "Your leave balance is not available from the host right now — no rows were returned.",
    "ar": "رصيد إجازاتك غير متاح من النظام حالياً — لم تُرجَع أي صفوف.",
}

RENDER_SCOPE = {
    "balance": {
        "en": "Your leave balance",
        "ar": "رصيد إجازاتك",
    },
    "leave_history": {
        "en": "Your leave requests",
        "ar": "طلبات إجازاتك",
    },
    "loans": {
        "en": "Your loans",
        "ar": "قروضك",
    },
    "payslip": {
        "en": "Your payslip lines",
        "ar": "قسائم راتبك",
    },
    "attendance": {
        "en": "Your attendance",
        "ar": "حضورك",
    },
    "permissions": {
        "en": "Your attendance permissions",
        "ar": "أذونات حضورك",
    },
}

UNSUMMARIZED_FALLBACK = {
    "en": (
        "I retrieved your records but couldn't summarize them. "
        "Open My to see the details."
    ),
    "ar": (
        "استرجعت سجلاتك لكن لم أتمكن من تلخيصها. "
        "افتح «My» لعرض التفاصيل."
    ),
}

EMPTY_RENDER = {
    "no_leave_requests": {
        "en": "No leave requests on record.",
        "ar": "لا توجد طلبات إجازة مسجّلة.",
    },
    "no_balance_configured": {
        "en": "Your leave balance has no rows configured yet.",
        "ar": "رصيد إجازاتك لا يحتوي على صفوف مُهيّأة بعد.",
    },
    "no_loans": {
        "en": "No existing loans.",
        "ar": "لا توجد قروض قائمة.",
    },
    "no_payslips": {
        "en": (
            "No committed payslip lines were found for you for that period. "
            "I will not invent net-pay figures."
        ),
        "ar": (
            "لا توجد بنود قسيمة راتب معتمدة لهذه الفترة. "
            "لن أخترع أرقام صافي الراتب."
        ),
    },
    "no_attendance_rows": {
        "en": "No attendance rows on record for that period.",
        "ar": "لا توجد سجلات حضور لهذه الفترة.",
    },
    "no_attendance_permissions": {
        "en": "No attendance permissions on record.",
        "ar": "لا توجد استئذانات حضور مسجّلة.",
    },
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
