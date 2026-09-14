"""Applicability-first curated-knowledge selection (domain-agnostic).

This module is the *selection* half of the curated-knowledge layer.  The host
resolves durable :class:`~ai.engine.knowledge.classes.KnowledgeItemProjection`
values (through its own loader) and hands them to the engine, which then applies
a deterministic, dependency-free pipeline that surfaces the knowledge that
actually applies to the current request — *before* ranking or truncation can
hide it.

Pipeline (applied in order):

  1. **Scope filter** — keep an item whose ``scope`` mapping is empty (globally
     applicable) or that matches the requested scope/context;
  2. **Conflict resolution** —
     :func:`~ai.engine.knowledge.classes.resolve_conflicts` prunes
     out-of-window items and superseded revisions (mandatory items always
     survive);
  3. **Mandatory-never-cut** — mandatory items are returned first, in stable
     input order, and are never subject to ``top_k`` truncation or ranking;
  4. **Rank + truncate** — the remaining (non-mandatory) items are optionally
     scored by a caller-supplied ``rank_fn`` and truncated to ``top_k``;
  5. **Freshness preserved** — projections are returned unmodified, keeping
     ``effective_start`` / ``effective_end`` / ``ingested_at`` / ``version``.

This module is pure: it performs no I/O and imports only the standard library
and sibling engine modules.  It never imports Django or any host module
(RULE_20 / ADR-0007).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from ai.engine.knowledge.classes import KnowledgeItemProjection, resolve_conflicts

__all__ = ["applicability_first"]


def _requested_context(
    scope: dict | None,
    objects: dict | None,
    process_state: dict | None,
) -> dict[str, Any]:
    """Merge the three request-context sources into one lookup mapping.

    Precedence (highest wins): ``scope`` > ``objects`` > ``process_state``.
    All three are optional and may be ``None``; an empty result means the
    request carries no scoping constraints, so only the org/module constraints
    below can narrow a non-global item.
    """
    merged: dict[str, Any] = {}
    for source in (process_state, objects, scope):
        if isinstance(source, dict):
            merged.update(source)
    return merged


def _scope_matches(item_scope: dict[str, Any], requested: dict[str, Any]) -> bool:
    """Return whether an item's ``scope`` mapping satisfies ``requested``.

    An empty ``item_scope`` means the item is globally applicable → always
    kept.  Otherwise exactly two *exclusionary* constraints apply (every other
    scope key is a generic tag and never excludes an item):

      * ``org_unit_id`` — when the item declares it and the request declares a
        scalar ``org_unit_id`` or a list ``org_unit_ids``, they must agree.
        The scalar ``org_unit_id`` wins when both are present (it names the
        user's *active* scope).
      * ``module_id`` — when BOTH the item and the request declare it, they
        must agree.
    """
    if not item_scope:
        return True

    if "org_unit_id" in item_scope:
        if "org_unit_id" in requested:
            if item_scope["org_unit_id"] != requested["org_unit_id"]:
                return False
        elif "org_unit_ids" in requested:
            ids = requested["org_unit_ids"]
            if isinstance(ids, (list, tuple, set, frozenset)):
                if item_scope["org_unit_id"] not in ids:
                    return False
            elif item_scope["org_unit_id"] != ids:
                return False

    if "module_id" in item_scope and "module_id" in requested:
        if item_scope["module_id"] != requested["module_id"]:
            return False

    return True


def _rank_descending(
    items: list[KnowledgeItemProjection],
    rank_fn: Callable[[KnowledgeItemProjection], float],
) -> list[KnowledgeItemProjection]:
    """Sort ``items`` by ``rank_fn`` score, descending, stably.

    ``rank_fn`` is called once per item as ``rank_fn(item)`` and must return a
    numeric relevance score (higher = more relevant).  A ``None`` score — or a
    ``rank_fn`` that raises — is treated as ``-inf`` (least relevant), so a
    misbehaving scorer can never crash retrieval or reorder items arbitrarily.
    Python's sort is stable, so equal scores preserve input order and the
    result stays deterministic.
    """
    scored: list[tuple[float, KnowledgeItemProjection]] = []
    for item in items:
        try:
            score = rank_fn(item)
        except Exception:  # noqa: BLE001 — a scorer must never fail a turn
            score = float("-inf")
        if score is None:
            score = float("-inf")
        scored.append((float(score), item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def applicability_first(
    items: list[KnowledgeItemProjection],
    *,
    scope: dict | None = None,
    objects: dict | None = None,
    process_state: dict | None = None,
    now: datetime,
    top_k: int | None = None,
    rank_fn: Callable[[KnowledgeItemProjection], float] | None = None,
) -> list[KnowledgeItemProjection]:
    """Select the knowledge items that apply to a request, applicability first.

    A curated knowledge item can *inform* an answer but never *authorize* an
    action; this function is pure selection, and it never grants capability.

    The contract this function enforces is that a **mandatory** item (an
    always-holds constraint) MUST appear in the result even when a ranking
    function scores it last and ``top_k`` would otherwise truncate it away.
    Mandatory items are therefore exempt from both ranking and truncation.

    Parameters
    ----------
    items:
        The candidate projections (already tenant-filtered by the host).
    scope, objects, process_state:
        Request context.  Merged into one lookup mapping (precedence: ``scope``
        > ``objects`` > ``process_state``).  See :func:`_scope_matches` for the
        exact org-unit/module matching semantics.
    now:
        The "current" time for the effective-window check (naive vs. aware must
        be consistent with the projections' datetimes).
    top_k:
        Maximum number of *non-mandatory* items to return.  ``None`` means no
        truncation; mandatory items are never counted against this limit.
    rank_fn:
        Optional per-item scorer ``rank_fn(item) -> float`` (higher = more
        relevant).  Called once per non-mandatory item; results sorted
        descending with a stable sort (ties preserve input order).  If
        omitted, non-mandatory items keep their post-conflict order.

    Returns
    -------
    list[KnowledgeItemProjection]
        Mandatory items first (stable input order), then the ranked/truncated
        non-mandatory items.  The returned projections are the *original*
        objects, so ``effective_start`` / ``effective_end`` / ``ingested_at`` /
        ``version`` are preserved intact.  The input list is never mutated.
    """
    # ── 1. Scope filter (globally-applicable items always survive) ─────────
    requested = _requested_context(scope, objects, process_state)
    filtered = [
        item for item in items if _scope_matches(item.scope or {}, requested)
    ]

    # ── 2. Resolve applicable versions (window + supersession + mandatory) ─
    resolved = resolve_conflicts(filtered, now)

    # ── 3. Mandatory-never-cut: first, stable, exempt from rank/truncate ───
    mandatory = [item for item in resolved if item.is_mandatory]
    optional = [item for item in resolved if not item.is_mandatory]

    # ── 4. Rank + truncate the non-mandatory items only ────────────────────
    if rank_fn is not None and optional:
        optional = _rank_descending(optional, rank_fn)
    if top_k is not None and top_k >= 0:
        optional = optional[:top_k]

    # ── 5. Freshness metadata is preserved: we return the original frozen
    #       projections, so effective_start/end/ingested_at/version are intact.
    return mandatory + optional
