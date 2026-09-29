from __future__ import annotations
from ai.engine.pack_vocab import LV, V
LV("t_arabic_needles_for_tools_py_compensation")


from ai.engine.cognition.turn.ess_read_i18n import LEAVE_TOPIC_AR, any_needle

COMPENSATION_AR = (
    LV("t_راتب"), LV("t_rx_n_wage_ar"), LV("t_rx_n_salary_ar"), LV("t_rx_n_comp_ar"),
)
PAYSLIP_SPECIFIC_AR = (
    LV("t_rx_n_slip"),
    LV("t_rx_n_slip_typo"),
    LV("t_rx_n_net"),
    LV("t_صافي_راتب"),
    LV("t_rx_n_net_salary"),
    LV("t_rx_n_deductions"),
    LV("t_rx_n_discounts"),
)
FIRST_PERSON_COMP_AR = (
    LV("t_rx_n_my_salary"), LV("t_rx_n_my_wage"), LV("t_rx_n_my_pay"), LV("t_rx_n_my_comp"),
)
FIRST_PERSON_PROFILE_AR = (
    LV("t_رقم_الموظف"),
    LV("t_rx_n_my_data"),
    LV("t_rx_n_my_dept"),
    LV("t_rx_n_my_mgr"),
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
