"""Arabic needles for ``intent`` leave mutation (ADR-0049 L7). No compiled regex."""
from __future__ import annotations

LEAVE_WANT_AR = ("أريد", "اريد", "أبغى", "ابغى", "عايز", "عاوز", "اطلب", "أطلب", "تقديم", "قدّم", "قدm")
LEAVE_WORD_AR = ("إجازة", "اجازة", "اجازه")
LEAVE_TYPE_AR = ("عارضة", "عارضه", "طارئة", "طارئه", "سنوية", "سنويه", "مرضية")


def leave_mutation_ar(text: str) -> bool:
    raw = text or ""
    if any(w in raw for w in LEAVE_WANT_AR) and any(l in raw for l in LEAVE_WORD_AR):
        return True
    if any(w in raw for w in ("تقديم", "قدّم", "قدm")) and any(l in raw for l in LEAVE_WORD_AR):
        return True
    return any(l in raw for l in LEAVE_WORD_AR) and any(t in raw for t in LEAVE_TYPE_AR)
