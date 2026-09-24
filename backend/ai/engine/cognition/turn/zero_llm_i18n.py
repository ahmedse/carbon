"""Arabic needles and bilingual reply maps for ``zero_llm`` (ADR-0049 L7).

No ``compiled regex`` in this module — Arabic literals stay outside harness
``arabic_regex`` windows in ``zero_llm.py``.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V


THANKS_AR = T("turn/zero_llm_i18n.py::THANKS_AR")
THANKS_WRITE_AR = T("turn/zero_llm_i18n.py::THANKS_WRITE_AR")
DAY_SPAN_AR = T("turn/zero_llm_i18n.py::DAY_SPAN_AR")
WHEN_START_AR = T("turn/zero_llm_i18n.py::WHEN_START_AR")
CLOCK_AR = T("turn/zero_llm_i18n.py::CLOCK_AR")
MONTH_ASK_AR = T("turn/zero_llm_i18n.py::MONTH_ASK_AR")
NOTIFICATION_AR = T("turn/zero_llm_i18n.py::NOTIFICATION_AR")
SHOW_OPEN_AR = T("turn/zero_llm_i18n.py::SHOW_OPEN_AR")
PAYROLL_SCHEDULE_AR = T("turn/zero_llm_i18n.py::PAYROLL_SCHEDULE_AR")
PAYSLIP_DOWNLOAD_AR = T("turn/zero_llm_i18n.py::PAYSLIP_DOWNLOAD_AR")
PAYROLL_FOLLOWUP_AR = T("turn/zero_llm_i18n.py::PAYROLL_FOLLOWUP_AR")
COWORKER_FOLLOWUP_AR = T("turn/zero_llm_i18n.py::COWORKER_FOLLOWUP_AR")
PAYROLL_POLICY_AR = T("turn/zero_llm_i18n.py::PAYROLL_POLICY_AR")
EMPTY_PAYSLIP_REPLY_AR = T("turn/zero_llm_i18n.py::EMPTY_PAYSLIP_REPLY_AR")
PROFILE_ASK_AR = T("turn/zero_llm_i18n.py::PROFILE_ASK_AR")

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
        V("t_i_don_t_have_next_month")
        + "That date is on the committed run in People — I won't guess it."
    ),
    "ar": (
        V("t_ليس_لدي_تاريخ_معالجة_رواتب_الشهر")
        + V("t_التاريخ_على_مسير_الرواتب_المعتمد_في")
    ),
}
PAYSLIP_DOWNLOAD_TEXT = {
    "en": (
        V("t_payslips_are_in_my_if_none")
    ),
    "ar": (
        "القسائم في تطبيقاتي. إذا لم تُعتمد قسيمة بعد، فلا يوجد ما يُحمَّل."
    ),
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)
