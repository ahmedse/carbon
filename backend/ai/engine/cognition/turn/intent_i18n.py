from __future__ import annotations
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
V("t_arabic_needles_for_intent_leave_mutation")


LEAVE_WANT_AR = T("turn/intent_i18n.py::LEAVE_WANT_AR")
LEAVE_WORD_AR = T("turn/intent_i18n.py::LEAVE_WORD_AR")
LEAVE_TYPE_AR = T("turn/intent_i18n.py::LEAVE_TYPE_AR")


def leave_mutation_ar(text: str) -> bool:
    raw = text or ""
    if any(w in raw for w in LEAVE_WANT_AR) and any(l in raw for l in LEAVE_WORD_AR):
        return True
    if any(w in raw for w in ("تقديم", "قدّم", "قدm")) and any(l in raw for l in LEAVE_WORD_AR):
        return True
    return any(l in raw for l in LEAVE_WORD_AR) and any(t in raw for t in LEAVE_TYPE_AR)
