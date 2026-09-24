"""Arabic needles for ``tools.py`` compensation/leave/profile (ADR-0049 L7)."""
from __future__ import annotations

from ai.engine.cognition.turn.ess_read_i18n import LEAVE_TOPIC_AR, any_needle

COMPENSATION_AR = ("راتب", "أجر", "مرتب", "تعويض")
PAYSLIP_SPECIFIC_AR = (
    "قسيمة",
    "صافي",
    "صافي راتب",
    "صافي الراتب",
    "الاستقطاعات",
    "خصومات",
)
FIRST_PERSON_COMP_AR = ("راتبي", "أجري", "مرتبي", "تعويضي")
FIRST_PERSON_PROFILE_AR = (
    "رقم الموظف",
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
