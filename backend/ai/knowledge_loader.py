"""Host-side loader for curated knowledge items (P4-02).

Turns durable :class:`~ai.models.knowledge.KnowledgeItem` rows into the engine's
:class:`~ai.engine.knowledge.classes.KnowledgeItemProjection` values.

This module lives OUTSIDE ``ai/engine/`` and is therefore allowed to import
Django and ``ai.models``.  It is the *tenancy boundary* for curated knowledge:
it applies the CBAC partitioning (app identifier, org-unit subtree,
visibility/ownership) here, at the query boundary, and then hands the engine a
list of plain projections.  The engine subsequently selects the applicable
subset via
:func:`ai.engine.knowledge.retrieval.applicability_first`.

The loader deliberately does NOT pre-filter by the effective window: the
engine's ``resolve_conflicts`` already handles expiry/supersession, and dropping
an expired *mandatory* item here would violate the "mandatory always holds"
rule.  For the same reason it does not prune superseded rows here — the engine's
supersession rule owns that decision.
"""

from __future__ import annotations

from ai.engine.knowledge.classes import KnowledgeItemProjection
from ai.models.knowledge import KnowledgeItem

#: Visibility values whose rows are visible to every caller (AppScopeMixin).
_GLOBAL_VISIBILITIES = ("global", "shared")


def load_knowledge_items(
    *,
    db=None,
    app_identifier: str = "carbon",
    org_unit_ids: list[int] | None = None,
    host_user_id: str | None = None,
    now=None,
) -> list[KnowledgeItemProjection]:
    """Load the curated knowledge projections for a request.

    Only live/curated rows are returned (``review_status`` is ``approved`` or
    ``superseded``).  Tenancy is applied in two orthogonal dimensions:

      * **org-unit subtree** — ``org_unit_ids`` (when provided) selects rows
        whose ``org_unit_id`` is in that set OR is NULL (globally applicable).
        ``org_unit_ids=None`` applies no org filter; an explicit empty list
        selects global rows only.
      * **visibility/ownership** — ``host_user_id`` (when provided) additionally
        admits ``visibility="private"`` rows owned by that user, plus all
        ``global``/``shared`` rows.  Without a user, only ``global``/``shared``
        rows are returned.

    ``db`` is accepted for call-site symmetry with the engine store but is
    ignored: this loader uses the Django ORM (default database connection).
    ``now`` is accepted for interface symmetry but unused — the engine resolves
    the effective window via ``resolve_conflicts`` so expired *mandatory* items
    still survive.
    """
    from django.db.models import Q

    qs = KnowledgeItem.objects.filter(
        app_identifier=app_identifier,
        review_status__in=["approved", "superseded"],
    )

    # ── Org-unit tenancy ──────────────────────────────────────────────────
    if org_unit_ids:
        qs = qs.filter(
            Q(org_unit_id__in=org_unit_ids) | Q(org_unit_id__isnull=True)
        )
    elif org_unit_ids is not None:
        # Explicit empty list → global (unscoped) rows only.
        qs = qs.filter(org_unit_id__isnull=True)

    # ── Visibility / ownership ────────────────────────────────────────────
    if host_user_id:
        qs = qs.filter(
            Q(visibility__in=_GLOBAL_VISIBILITIES)
            | Q(visibility="private", host_user_id=host_user_id)
        )
    else:
        qs = qs.filter(visibility__in=_GLOBAL_VISIBILITIES)

    projections: list[KnowledgeItemProjection] = []
    for row in qs.iterator():
        projections.append(
            KnowledgeItemProjection(
                id=row.id,
                knowledge_class=row.knowledge_class,
                source=row.source,
                content=row.content,
                owner_id=row.owner_id,
                scope=row.scope or {},
                version=row.version,
                effective_start=row.effective_start,
                effective_end=row.effective_end,
                ingested_at=row.ingested_at,
                review_status=row.review_status,
                sensitivity=row.sensitivity,
                supersedes_id=row.supersedes_id,
                is_mandatory=row.is_mandatory,
            )
        )
    return projections
