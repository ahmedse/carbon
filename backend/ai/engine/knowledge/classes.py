"""Knowledge-class conflict resolution (domain-agnostic).

The engine consumes plain :class:`KnowledgeItemProjection` values — never host
objects — and resolves a knowledge corpus deterministically through three rules,
applied in order:

  1. **Effective-period filter** — an item outside its validity window is
     dropped, unless it is mandatory (a mandatory constraint still holds).
  2. **Supersession** — a later revision supersedes the revision it points at
     (same class); a superseding item pointing at a missing predecessor is kept.
  3. **Mandatory-always-holds** — mandatory items are never dropped by the first
     two rules and are returned first (stable order), followed by the remaining
     items in input order.

Knowledge *informs* an answer; it never *authorizes* an action.  Documents and
memories never grant permission: :func:`grant_capability` is the constant seam
every authorization path must call to assert that rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# The closed set of knowledge kinds.  The host persists these same slugs; the
# engine holds only the value set and imports nothing host-side to obtain them.
KNOWLEDGE_CLASSES = frozenset(
    {
        "policy",
        "process_definition",
        "business_fact",
        "procedural_heuristic",
        "episodic_observation",
        "user_preference",
    }
)


@dataclass(frozen=True)
class KnowledgeItemProjection:
    """A plain, immutable projection of a knowledge item for the engine.

    Mirrors the host model's semantics without any host coupling: the engine
    sees only primitives.  ``effective_start`` / ``effective_end`` /
    ``ingested_at`` are optional ``datetime`` values; ``scope`` is a mapping.
    """

    id: str
    knowledge_class: str
    source: str
    content: str
    owner_id: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    version: str = "1"
    effective_start: datetime | None = None
    effective_end: datetime | None = None
    ingested_at: datetime | None = None
    review_status: str = "draft"
    sensitivity: str = "internal"
    supersedes_id: str = ""
    is_mandatory: bool = False


def resolve_conflicts(
    items: list[KnowledgeItemProjection], now: datetime
) -> list[KnowledgeItemProjection]:
    """Resolve ``items`` into the effective knowledge set.

    Applies the three conflict rules in order and returns a **new** list; the
    input list and its projections are never mutated, and the result is
    deterministic for a given input order.

    Rule 1 — effective-period filter
        A non-mandatory item whose ``effective_start`` is in the future or whose
        ``effective_end`` is in the past is dropped.  Mandatory items always
        survive this filter.

    Rule 2 — supersession
        When an item ``B`` has ``B.supersedes_id == A.id`` and both share the
        same ``knowledge_class``, ``A`` is superseded and dropped (unless ``A``
        is mandatory).  ``B`` is always kept — including when ``A`` is missing,
        in which case ``B`` stands on its own.

    Rule 3 — mandatory-always-holds ordering
        Mandatory items come first (preserving their relative input order),
        followed by non-mandatory items (also in input order).
    """
    # ── Rule 1: effective-period filter (mandatory always survives) ─────────
    active: list[KnowledgeItemProjection] = []
    for item in items:
        if not item.is_mandatory:
            if item.effective_start is not None and item.effective_start > now:
                continue  # not yet in effect
            if item.effective_end is not None and item.effective_end < now:
                continue  # already expired
        active.append(item)

    # ── Rule 2: supersession (a superseded mandatory item still holds) ──────
    superseded_ids: set[str] = set()
    for successor in active:
        if not successor.supersedes_id:
            continue
        for predecessor in active:
            if (
                predecessor.id == successor.supersedes_id
                and predecessor.knowledge_class == successor.knowledge_class
            ):
                superseded_ids.add(predecessor.id)

    survivors = [
        item
        for item in active
        if not (item.id in superseded_ids and not item.is_mandatory)
    ]

    # ── Rule 3: mandatory first, then non-mandatory, both stable ────────────
    return [
        item for item in survivors if item.is_mandatory
    ] + [item for item in survivors if not item.is_mandatory]


def grant_capability(items: list[KnowledgeItemProjection]) -> bool:
    """Return whether a knowledge corpus confers a capability — always ``False``.

    Knowledge items can *inform* a decision but can never *authorize* one:
    documents and memories never grant permission.  This function is the single
    seam callers use to assert that rule, and it is intentionally constant for
    every input.
    """
    return False
