"""Arabic needles and bilingual reply maps for ``zero_llm`` (ADR-0049 L7).

No ``compiled regex`` in this module — Arabic literals stay outside harness
``arabic_regex`` windows in ``zero_llm.py``.
"""
from __future__ import annotations

THANKS_AR = ("شكرا", "شكراً", "مشكور")
THANKS_WRITE_AR = ("قدّم", "قدم", "أرسل", "ارسل")
DAY_SPAN_AR = ("من الآن", "من الان", "حتى إجاز", "حتى اجاز")
WHEN_START_AR = ("متى تبدأ", "متى تبدا", "متى يبدأ", "متى يبدا")
CLOCK_AR = (
    "ما هو تاريخ",
    "ما تاريخ",
    "ما هو اليوم",
    "ما اليوم",
    "ما هو الشهر",
    "اليوم كم",
)
MONTH_ASK_AR = ("الشهر",)
NOTIFICATION_AR = ("إشعارات", "اشعارات", "تنبيهات")
SHOW_OPEN_AR = ("أرني", "ارني", "افتح", "وين", "أين")
PAYROLL_SCHEDULE_AR = (
    "متى ستتم معالجة الرواتب",
    "متى يتم معالجة الرواتب",
    "متى سيكون الراتب",
)
PAYSLIP_DOWNLOAD_AR = ("تحميل قسيمة", "تحميل القسيمة")
PAYROLL_FOLLOWUP_AR = (
    "راتبي",
    "الراتب",
    "صافي",
    "الاستقطاعات",
    "خصومات",
    "قسيمة",
)
COWORKER_FOLLOWUP_AR = ("قسم", "منصب", "مدير")
PAYROLL_POLICY_AR = ("اعتراض", "شهادة طبية", "سياسة")
EMPTY_PAYSLIP_REPLY_AR = ("لم أجد قسائم",)
PROFILE_ASK_AR = ("رقم الموظف", "قسم", "مدير")

THANKS_TEXT = {
    "en": "You're welcome. Ask if you need anything else.",
    "ar": "على الرحب والسعة. أنا هنا إذا احتجت شيئاً آخر.",
}
NOTIFICATION_TEXT = {
    "en": (
        "Notifications are in the bell in the header — "
        "there is no separate notifications page."
    ),
    "ar": "الإشعارات في الجرس أعلى الصفحة — لا توجد صفحة منفصلة للإشعارات.",
}
PAYROLL_SCHEDULE_TEXT = {
    "en": (
        "I don't have next month's payroll run date. "
        "That date is on the committed run in People — I won't guess it."
    ),
    "ar": (
        "ليس لدي تاريخ معالجة رواتب الشهر القادم. "
        "التاريخ على مسير الرواتب المعتمد في تطبيقاتي، ولن أخمنه."
    ),
}
PAYSLIP_DOWNLOAD_TEXT = {
    "en": (
        "Payslips are in My. If none are committed yet, there is nothing to download."
    ),
    "ar": (
        "القسائم في تطبيقاتي. إذا لم تُعتمد قسيمة بعد، فلا يوجد ما يُحمَّل."
    ),
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
