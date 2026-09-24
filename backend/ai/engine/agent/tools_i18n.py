from __future__ import annotations
from ai.engine.pack_vocab import V
V("t_arabic_needles_for_tools_py_compensation")


from ai.engine.cognition.turn.ess_read_i18n import LEAVE_TOPIC_AR, any_needle

COMPENSATION_AR = (V("t_راتب"), "أجر", "مرتب", "تعويض")
PAYSLIP_SPECIFIC_AR = (
    "قسيمة",
    "قسيمه",  # common typo of قسيمة
    "صافي",
    V("t_صافي_راتب"),
    "صافي الراتب",
    "الاستقطاعات",
    "خصومات",
)
FIRST_PERSON_COMP_AR = ("راتبي", "أجري", "مرتبي", "تعويضي")
FIRST_PERSON_PROFILE_AR = (
    V("t_رقم_الموظف"),
    "بياناتي",
    "قسمي",
    "مديري",
)
NAMED_LEAVE_AR = ("لـ",)

__all__ = [
    "COMPENSATION_AR",
    "FIRST_PERSON_COMP_AR",
    "FIRST_PERSON_PROFILE_AR",
    "LEAVE_TOPIC_AR",
    "NAMED_LEAVE_AR",
    "PAYSLIP_SPECIFIC_AR",
    "any_needle",
]
