"""Arabic needles for ``chat_surface`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

from ai.engine.host_ids import (
    ID_LEAVE_TYPE,
    ID_LOAN_TYPE,
    ID_PERMISSION_TYPE,
)
from ai.engine.pack_vocab import LV, V, same_id


LEAVE_INTENT_AR = (
    LV("t_rx_n_leave_stem"), LV("t_rx_n_leave_stem_2"),
    LV("t_rx_n_casual"), LV("t_rx_n_casual_2"), LV("t_rx_n_annual_ar"),
)
LOAN_INTENT_AR = (LV("t_قرض"),)
ATTENDANCE_INTENT_AR = (LV("t_rx_n_excuse_ar"), LV("t_حضور"))
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
ESS_TOPIC_AR = (
    LV("t_rx_n_leave_stem"), LV("t_rx_n_leave_stem_2"), LV("t_قرض"),
    LV("t_rx_n_excuse_ar"), LV("t_rx_n_submit_ar"),
)
ESS_WRITE_VERB_AR = ("أريد", "اريد", "أبغى", "ابغى", "اطلب", "أطلب", "تقديم", "قدّم", "قدm")

_FIELD_ROWS = (
    (ID_LEAVE_TYPE, (LV("t_leave_type_2"), LV("t_rx_copy_field_leave_ar"))),
    ("start_date", ("Start date", "تاريخ البداية")),
    ("end_date", ("End date", "تاريخ النهاية")),
    ("days", ("Days", "الأيام")),
    ("reason", ("Reason", "السبب")),
    (ID_LOAN_TYPE, (LV("t_loan_type"), LV("t_rx_copy_field_loan_ar"))),
    ("principal", ("Principal", "المبلغ")),
    ("term_months", ("Term (months)", "المدة (أشهر)")),
    ("interest_rate", ("Interest rate", "الفائدة")),
    (ID_PERMISSION_TYPE, (LV("t_rx_copy_field_perm_en"), LV("t_rx_copy_field_perm_ar"))),
    ("hours", ("Hours", "الساعات")),
)


def field_labels_for(key: str) -> tuple[str, str]:
    """Label pair for a slot. An empty pack id does not match a field name."""
    for name, pair in _FIELD_ROWS:
        if same_id(key, name):
            return pair
    shown = str(key).replace("_", " ")
    return (shown, shown)


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    # Empty is not a match. A pack that lacks the needle must not hit every utterance.
    return any(n and str(n) in raw for n in needles)
