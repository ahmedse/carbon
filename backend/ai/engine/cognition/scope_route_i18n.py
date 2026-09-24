"""Arabic needles for ``scope_route`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


LEAVE_WANT_AR = T("scope_route_i18n.py::LEAVE_WANT_AR")
LEAVE_WORD_AR = T("scope_route_i18n.py::LEAVE_WORD_AR")
LEAVE_PLEASE_AR = T("scope_route_i18n.py::LEAVE_PLEASE_AR")
ABSENCE_REPORT_AR = T("scope_route_i18n.py::ABSENCE_REPORT_AR")
LEAVE_COMPLIANCE_TERM_AR = T("scope_route_i18n.py::LEAVE_COMPLIANCE_TERM_AR")
BARE_LEAVE_AR = T("scope_route_i18n.py::BARE_LEAVE_AR")
ADVISORY_AR = T("scope_route_i18n.py::ADVISORY_AR")
PLAN_SIGNAL_AR = T("scope_route_i18n.py::PLAN_SIGNAL_AR")


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)


def leave_personal_ar(text: str) -> bool:
    raw = text or ""
    if any_needle(raw, ABSENCE_REPORT_AR):
        return True
    if any(w in raw for w in LEAVE_WANT_AR) and any(l in raw for l in LEAVE_WORD_AR):
        return True
    for word in LEAVE_WORD_AR:
        if word not in raw:
            continue
        tail = raw[raw.index(word) + len(word) :].lstrip()
        if not tail or any(tail.startswith(p) for p in LEAVE_PLEASE_AR):
            return True
    return False


def leave_compliance_ar(text: str) -> bool:
    raw = text or ""
    if not any(t in raw for t in LEAVE_COMPLIANCE_TERM_AR):
        return False
    return any(w in raw for w in LEAVE_WORD_AR)


def bare_leave_ar(text: str) -> bool:
    stripped = (text or "").strip().strip(".!?؟")
    return stripped in BARE_LEAVE_AR


def advisory_ar(text: str) -> bool:
    return any_needle(text, ADVISORY_AR)


def plan_signal_ar(text: str) -> bool:
    return any_needle(text, PLAN_SIGNAL_AR)
