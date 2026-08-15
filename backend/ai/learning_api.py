"""Sprint 11 — learning-flywheel status + manual sweep API.

GET  /carbon-api/ai/pulse/learning-status/        — flywheel status (read-only)
POST /carbon-api/ai/pulse/learning-status/run/    — run the sweep on demand

Surfaces the operational state of the Sprint 10→11 feedback flywheel: how many
judged ``AIMessage`` rows are still unconsumed (``learned_at IS NULL``), how
many have been learned, the outcome breakdown, the durable long-term-memory
facts the bridge wrote, and the ``KgFeedbackRecord`` ledger.

Read is gated on ``ai:view_console``; the manual sweep (a write) is gated on
``ai:manage_console`` — mirroring the rest of the Pulse console.
"""

import logging

from django.conf import settings as django_settings
from django.db.models import Count
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.permissions import AdminOrSuperuserOnly
from ai.learning import LEARNABLE_OUTCOMES, learn_all_pending
from ai.models import AIMessage
from ai.models.core import MemoryLongTerm
from ai.models.knowledge_graph import KgFeedbackRecord

logger = logging.getLogger("carbon.ai.learning_api")

_RECENT_LIMIT = 10


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _build_status(request) -> dict:
    """Assemble the flywheel status payload (read-only, no writes)."""
    backend = getattr(django_settings, "AI_STORE_BACKEND", "inmemory")

    pending = AIMessage.objects.filter(
        outcome__in=LEARNABLE_OUTCOMES, learned_at__isnull=True
    ).count()
    processed = AIMessage.objects.filter(learned_at__isnull=False).count()

    by_outcome = {
        row["outcome"]: row["c"]
        for row in AIMessage.objects.filter(learned_at__isnull=False)
        .values("outcome")
        .annotate(c=Count("id"))
        .order_by("outcome")
    }

    facts_qs = scope_ai_queryset(MemoryLongTerm.objects, request.user).filter(
        category__in=["learned", "correction"]
    )
    fact_counts = {
        row["category"]: row["c"]
        for row in facts_qs.values("category").annotate(c=Count("id"))
    }
    recent_facts = [
        {
            "id": f.id,
            "category": f.category,
            "content": (f.content or "")[:200],
            "confidence": f.confidence,
            "created_at": _iso(f.created_at),
        }
        for f in facts_qs.order_by("-created_at")[:_RECENT_LIMIT]
    ]

    fb_qs = scope_ai_queryset(KgFeedbackRecord.objects, request.user)
    feedback_records = fb_qs.count()
    recent_feedback = [
        {
            "id": r.id,
            "signal_type": r.signal_type,
            "message_id": r.message_id,
            "user_comment": r.user_comment,
            "quality_score": r.quality_score,
            "created_at": _iso(r.created_at),
        }
        for r in fb_qs.order_by("-created_at")[:_RECENT_LIMIT]
    ]

    return {
        "backend": backend,
        "durable": backend == "django",
        "pending": pending,
        "processed": processed,
        "by_outcome": by_outcome,
        "facts": {
            "counts": fact_counts,
            "recent": recent_facts,
        },
        "feedback_records": {
            "count": feedback_records,
            "recent": recent_feedback,
        },
    }


class LearningStatusView(APIView):
    """GET learning-status/ — flywheel status (no writes)."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        try:
            return Response(_build_status(request))
        except Exception as exc:  # noqa: BLE001 — never 500 the console
            logger.warning("learning status unavailable: %s", exc)
            return Response(
                {"error": "learning status unavailable"},
                status=503,
            )


class LearningRunView(APIView):
    """POST learning-status/run/ — run the sweep on demand."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:manage_console"

    def post(self, request):
        try:
            sweep = learn_all_pending()
        except Exception as exc:  # noqa: BLE001 — report, don't 500
            logger.exception("manual learning sweep failed")
            return Response({"error": str(exc)}, status=500)

        return Response({"sweep": sweep, "status": _build_status(request)})
