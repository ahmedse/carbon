"""
AI Memory & learnt-facts API (Phase 23-A).

Read + forget ONLY.  Three views over one relationship model:

  GET    /carbon-api/ai/memory/facts/            → learnt facts (confidence + provenance)
  GET    /carbon-api/ai/memory/episodes/         → raw episodic memory
  GET    /carbon-api/ai/memory/relationship/     → computed-on-read summary (memory + usage + profile)
  DELETE /carbon-api/ai/memory/facts/{pk}/       → forget (hard delete + cascade + audit)

Design decisions (TASKS.md §Phase 23-A):
  * Every fact is inspectable + forgettable; each exposes its provenance
    (``source`` + ``created_at`` from the writing turn).
  * Relationship is COMPUTED on read from memory + usage + profile — never
    persisted as a second copy (RULE_21 no auto-mutation).
  * Privacy-first: forget = hard delete of the fact node + cascade to derived
    facts, audited.  Soft-delete leaves a GDPR hole — we never soft-delete
    here (Phase 19 delete-safety semantics).
  * ``memory_enabled=false`` (Phase 22-A) gates the *write* side of the
    engine (context_assembler T4).  Reads and forgets always work — GDPR
    right to erasure must never be gated by a preference flag.
  * Scope every query through ``accounts.ai_scoping.scope_ai_queryset``
    (app + visibility + org-subtree expansion at the query boundary) —
    mirrors ``_apply_tenancy_filter`` semantics.

DO NOT TOUCH: the KG/memory write path internals (engine/memory,
engine/knowledge_graph) — this module is read + forget only.
"""

import logging

from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.ai_scoping import scope_ai_queryset
from accounts.rbac_utils import user_is_global_admin
from ai.models import AIUserProfile, AuditLog, MemoryEpisodic, MemoryLongTerm
from ai.usage_service import AIUsage

logger = logging.getLogger("carbon.ai.memory_api")

# Hard cap on rows returned per list view (the frontend paginates client-side).
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500


def _limit(request, default: int = _DEFAULT_LIMIT) -> int:
    """Parse ``?limit=`` with a hard cap."""
    try:
        value = int(request.query_params.get("limit", default))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, _MAX_LIMIT))


def _can_forget(user, fact) -> bool:
    """A requester may forget a fact iff they own it (or are global-scoped)."""
    if user.is_superuser or user_is_global_admin(user):
        return True
    return fact.host_user_id is not None and str(fact.host_user_id) == str(user.pk)


def _cascade_fact_qs(fact_id: str):
    """Derived-fact lineage for a forget: the node + its supersede references.

    The long-term memory writer keeps two directional links:
      * ``superseded_by`` — old fact pointing at the fact that replaced it;
      * ``source="superseded:{fact_id}"`` — a replacement recording the fact
        it superseded.

    Forgetting a fact removes both directions so no dangling reference to a
    deleted row survives.  Episodic rows are NOT linked to facts by any key
    (episodes store ``causal_chain`` between episodes only), so the episodic
    "source, where derivable" cascade is a no-op by design here — the
    hard-deleted lineage above is the complete derived set.
    """
    from django.db.models import Q

    return MemoryLongTerm.objects.filter(
        Q(pk=fact_id)
        | Q(superseded_by=fact_id)
        | Q(source=f"superseded:{fact_id}")
    )


class _MemoryBaseView(APIView):
    """Common auth + scoping for the memory read surface."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _scoped(qs, request):
        """App + visibility + org-subtree scoping at the query boundary."""
        return scope_ai_queryset(qs, request.user)


class MemoryFactsView(_MemoryBaseView):
    """GET /facts/ — learnt facts with confidence + provenance."""

    def get(self, request):
        qs = self._scoped(
            MemoryLongTerm.objects.filter(
                archived=False,
                superseded_by__isnull=True,
            ),
            request,
        )
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        qs = qs.order_by("-created_at")[:_limit(request)]

        results = []
        for fact in qs:
            results.append(
                {
                    "id": fact.pk,
                    "category": fact.category,
                    "content": fact.content,
                    "confidence": fact.confidence,
                    # Provenance: which writing turn produced this fact.
                    "provenance": {
                        "source": fact.source,
                        "created_at": fact.created_at.isoformat(),
                        "last_used": (
                            fact.last_used.isoformat() if fact.last_used else None
                        ),
                    },
                    "use_count": fact.use_count,
                    "visibility": fact.visibility,
                    "valid_from": (
                        fact.valid_from.isoformat() if fact.valid_from else None
                    ),
                    "valid_to": fact.valid_to.isoformat() if fact.valid_to else None,
                }
            )
        return Response({"count": len(results), "results": results})


class MemoryEpisodesView(_MemoryBaseView):
    """GET /episodes/ — raw episodic memory."""

    def get(self, request):
        qs = self._scoped(
            MemoryEpisodic.objects.filter(archived=False),
            request,
        )
        event_type = request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        qs = qs.order_by("-occurred_at")[:_limit(request)]

        results = []
        for episode in qs:
            results.append(
                {
                    "id": episode.pk,
                    "event_type": episode.event_type,
                    "summary": episode.summary,
                    "details": episode.details,
                    "caused_by_episode_id": episode.caused_by_episode_id,
                    "relevance_score": episode.relevance_score,
                    "occurred_at": episode.occurred_at.isoformat(),
                    "learned_at": episode.learned_at.isoformat(),
                    "visibility": episode.visibility,
                }
            )
        return Response({"count": len(results), "results": results})


class MemoryRelationshipView(_MemoryBaseView):
    """GET /relationship/ — computed on read from memory + usage + profile.

    Never persisted (RULE_21): this is a projection assembled per request,
    so the "You & AI" tab always reflects live data.
    """

    def get(self, request):
        user = request.user

        facts_qs = self._scoped(
            MemoryLongTerm.objects.filter(
                archived=False,
                superseded_by__isnull=True,
            ),
            request,
        )
        episodes_qs = self._scoped(
            MemoryEpisodic.objects.filter(archived=False),
            request,
        )

        fact_count = facts_qs.count()
        episode_count = episodes_qs.count()

        # Top fact categories + average confidence (single DB aggregation).
        top_categories = list(
            facts_qs.values("category")
            .annotate(count=Count("pk"))
            .order_by("-count", "category")
        )
        avg = facts_qs.aggregate(
            avg_confidence=Avg("confidence"),
            total_uses=Sum("use_count"),
        )
        avg_confidence = (
            round(float(avg["avg_confidence"]), 3)
            if avg["avg_confidence"] is not None
            else None
        )

        # Profile prefs (Phase 22-A) — memory_enabled gates the engine WRITE
        # side (T4 injection); it never blocks reads or forgets.
        profile, _created = AIUserProfile.objects.get_or_create(user=user)
        memory_enabled = bool(profile.memory_enabled)

        usage = AIUsage(user).summary()

        return Response(
            {
                "memory_enabled": memory_enabled,
                "memory": {
                    "fact_count": fact_count,
                    "episode_count": episode_count,
                    "top_categories": top_categories,
                    "avg_confidence": avg_confidence,
                    "total_uses": int(avg["total_uses"] or 0),
                },
                "usage": {
                    "period_days": usage["period_days"],
                    "total_tokens": usage["total_tokens"],
                    "total_generations": usage["total_generations"],
                    "total_cost": usage["total_cost"],
                    "by_model": usage["by_model"],
                    "quota": usage["quota"],
                },
                "profile": {
                    "memory_enabled": memory_enabled,
                    "temperature": profile.temperature,
                    "auto_title": profile.auto_title,
                    "usage_alert_threshold": profile.usage_alert_threshold,
                    "default_model_id": (
                        profile.default_model_id.model_id
                        if profile.default_model_id_id is not None
                        else None
                    ),
                    "monthly_token_limit": profile.monthly_token_limit,
                    "quota_reset_day": profile.quota_reset_day,
                },
                "computed_at": timezone.now().isoformat(),
            }
        )


class MemoryFactDeleteView(_MemoryBaseView):
    """DELETE /facts/{pk}/ — forget: hard delete + cascade + audit.

    GDPR right to erasure: always allowed for the owner (never gated by
    ``memory_enabled``).  Scope-filtered — other users' private facts are
    invisible (404); shared/global facts visible but not owned are refused
    (403) unless the requester is a superuser/global admin.
    """

    def delete(self, request, pk):
        qs = self._scoped(
            MemoryLongTerm.objects.filter(
                archived=False,
                superseded_by__isnull=True,
            ),
            request,
        )
        fact = qs.filter(pk=pk).first()
        if fact is None:
            return Response({"detail": "Fact not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_forget(request.user, fact):
            return Response(
                {"detail": "You can only forget facts you own."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lineage = _cascade_fact_qs(fact.pk)
        cascade_ids = list(lineage.values_list("pk", flat=True))

        with transaction.atomic():
            # Hard delete (never soft-delete — soft delete leaves a GDPR hole).
            deleted, _by_model = lineage.delete()
            # Audit every forget (who/when/what) — legal requirement.
            AuditLog.objects.create(
                instance_id="carbon",
                actor=str(request.user.pk),
                actor_type="user",
                action="memory.forget",
                target=str(fact.pk),
                detail={
                    "model": "MemoryLongTerm",
                    "category": fact.category,
                    "content": fact.content[:200],
                    "confidence": fact.confidence,
                    "cascade": cascade_ids,
                    "rows_deleted": deleted,
                },
                host_user_id=str(request.user.pk),
                visibility="private",
            )
            logger.info(
                "memory.forget user=%s fact=%s cascade=%s deleted=%s",
                request.user.pk, fact.pk, cascade_ids, deleted,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
