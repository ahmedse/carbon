"""Arabic needles and bilingual maps for ``handoff_agent`` (ADR-0049 L7).

No ``compiled regex`` in this module.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V


READY_TO_SUBMIT_AR = T("turn/handoff_agent_i18n.py::READY_TO_SUBMIT_AR")
QUESTION_AR = T("turn/handoff_agent_i18n.py::QUESTION_AR")
AFFIRM_AR = T("turn/handoff_agent_i18n.py::AFFIRM_AR")
JAILBREAK_AR = T("turn/handoff_agent_i18n.py::JAILBREAK_AR")

LOAN_EMERGENCY_AR = T("turn/handoff_agent_i18n.py::LOAN_EMERGENCY_AR")
LOAN_HOUSING_AR = T("turn/handoff_agent_i18n.py::LOAN_HOUSING_AR")
LOAN_SALARY_AR = T("turn/handoff_agent_i18n.py::LOAN_SALARY_AR")
LOAN_CAR_AR = T("turn/handoff_agent_i18n.py::LOAN_CAR_AR")
LOAN_PERSONAL_AR = T("turn/handoff_agent_i18n.py::LOAN_PERSONAL_AR")

LEAVE_ANNUAL_AR = T("turn/handoff_agent_i18n.py::LEAVE_ANNUAL_AR")
LEAVE_SICK_AR = T("turn/handoff_agent_i18n.py::LEAVE_SICK_AR")
LEAVE_EMERGENCY_AR = T("turn/handoff_agent_i18n.py::LEAVE_EMERGENCY_AR")
LEAVE_UNPAID_AR = T("turn/handoff_agent_i18n.py::LEAVE_UNPAID_AR")
LEAVE_MATERNITY_AR = T("turn/handoff_agent_i18n.py::LEAVE_MATERNITY_AR")

PERM_OFFICIAL_AR = T("turn/handoff_agent_i18n.py::PERM_OFFICIAL_AR")
PERM_MEDICAL_AR = T("turn/handoff_agent_i18n.py::PERM_MEDICAL_AR")
PERM_EMERGENCY_AR = T("turn/handoff_agent_i18n.py::PERM_EMERGENCY_AR")
PERM_PERSONAL_AR = T("turn/handoff_agent_i18n.py::PERM_PERSONAL_AR")

AMOUNT_CURRENCY_AR = T("turn/handoff_agent_i18n.py::AMOUNT_CURRENCY_AR")
AMOUNT_PREFIX_AR = T("turn/handoff_agent_i18n.py::AMOUNT_PREFIX_AR")
MONTHS_AR = T("turn/handoff_agent_i18n.py::MONTHS_AR")
DAYS_AR = T("turn/handoff_agent_i18n.py::DAYS_AR")
HOURS_AR = T("turn/handoff_agent_i18n.py::HOURS_AR")
SLOT_STATUS_AR = T("turn/handoff_agent_i18n.py::SLOT_STATUS_AR")
RELATIVE_DAY_AR = T("turn/handoff_agent_i18n.py::RELATIVE_DAY_AR")

CLARIFY_TEXT = {
    "submit_my_loan": {
        "loan_type": {
            "en": V("t_what_type_of_loan_are_you"),
            "ar": V("t_أي_نوع_قرض_تريد"),
        },
        "principal": {
            "en": "How much do you need?",
            "ar": "كم المبلغ الذي تحتاجه؟",
        },
    },
    "submit_my_leave": {
        "leave_type": {
            "en": V("t_what_type_of_leave_do_you"),
            "ar": V("t_أي_نوع_إجازة_تريد"),
        },
        "start_date": {
            "en": V("t_which_dates_do_you_want_to"),
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
