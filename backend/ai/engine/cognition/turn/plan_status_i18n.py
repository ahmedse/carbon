"""Arabic needles for ``plan_status`` (ADR-0049 L7). No compiled regex."""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


# Status ask = a status HEAD followed (within a short window) by a plan OBJECT.
# Mirrors the retired regex ``(?:حالة|وضع).{0,24}(?:طلب||...)`` without compiling.
STATUS_HEAD_AR = T("turn/plan_status_i18n.py::STATUS_HEAD_AR")
STATUS_OBJECT_AR = T("turn/plan_status_i18n.py::STATUS_OBJECT_AR")
STATUS_ASK_AR = STATUS_HEAD_AR  # kept for import compatibility; use ``is_status_ask_ar``
WRITE_ASK_AR = T("turn/plan_status_i18n.py::WRITE_ASK_AR")


STATUS_LABEL = {
    "handoff_ready": {
        "en": "ready to submit in Agent — not under review until you submit",
        "ar": "جاهز للتقديم في الوكيل — ليس قيد المراجعة حتى تُرسله",
    },
    "discovering": {
        "en": "still gathering details",
        "ar": "ما زال يجمع التفاصيل",
    },
    "pending_approval": {
        "en": "pending your approval in Tasks, then review",
        "ar": "بانتظار موافقتك في المهام ثم المراجعة",
    },
    "approved": {
        "en": "approved and waiting to run",
        "ar": "مُعتمد وبانتظار التشغيل",
    },
    "running": {
        "en": "running now",
        "ar": "قيد التشغيل الآن",
    },
    "paused": {
        "en": "paused — waiting for a confirmation",
        "ar": "متوقف — بانتظار تأكيد",
    },
    "completed": {
        "en": "completed",
        "ar": "مكتمل",
    },
    "completed_with_gaps": {
        "en": "completed with gaps",
        "ar": "مكتمل مع نواقص",
    },
    "failed": {
        "en": "failed",
        "ar": "فشل",
    },
    "cancelled": {
        "en": "cancelled",
        "ar": "ملغى",
    },
}


def any_needle(text: str, needles: tuple[str, ...]) -> bool:
    raw = text or ""
    return any(n in raw for n in needles)


def is_status_ask_ar(text: str, *, window: int = 24) -> bool:
    """True when an Arabic status head is followed by a plan object within ``window`` chars."""
    raw = text or ""
    for head in STATUS_HEAD_AR:
        start = raw.find(head)
        while start >= 0:
            tail = raw[start + len(head): start + len(head) + window]
            if any(obj in tail for obj in STATUS_OBJECT_AR):
                return True
            start = raw.find(head, start + 1)
    return False
