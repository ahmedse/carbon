"""MDM & data product assistance (Phase 24 Phase K).

DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md §5B Phase K: entity resolution
assistance, dedup suggestions, "explain this entity's master record",
gold-record confidence.

  * ``explain_entity``       — explain an entity's master record: set context,
                              validity status, gold-record confidence,
                              near-duplicates
  * ``dedup_suggestions``    — entity-resolution dedup suggestions over a
                              seeded golden set (same normalized code or
                              near-dup labels); never auto-merges
  * ``propose_merge``        — DRAFT ONLY: requires_confirmation payload with
                              duplicate/gold state; never writes (RULE_21)
  * ``gold_record_confidence`` — deterministic confidence score (0..1)

Entities are master-data reference values (``mdm.ReferenceValue``) inside
``mdm.ReferenceSet``. Imports are downward-only (``mdm``) — never imported by
the mdm app (RULE_20). No writes.
"""

from __future__ import annotations

import difflib
import logging
import re
from collections import Counter
from typing import Any, Iterable

from django.utils import timezone
from mdm.models import ReferenceSet, ReferenceValue

logger = logging.getLogger("carbon.ai.mdm_advisor")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


# ── Normalization & similarity ─────────────────────────────────────────────


def _normalize(text: str) -> str:
    """Lowercase, strip non-alphanumerics, collapse whitespace."""
    return _NON_ALNUM.sub("", text.lower())


def _label_similarity(a: str, b: str) -> float:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return round(difflib.SequenceMatcher(None, na, nb).ratio(), 3)


def _is_currently_valid(value: ReferenceValue, target_date) -> bool:
    if not value.is_active:
        return False
    if value.valid_from is not None and value.valid_from > target_date:
        return False
    if value.valid_to is not None and value.valid_to < target_date:
        return False
    return True


def _value_summary(value: ReferenceValue) -> dict:
    return {
        "value_id": value.id,
        "code": value.code,
        "label": value.label,
        "description": value.description,
        "is_active": value.is_active,
        "sort_order": value.sort_order,
        "valid_from": value.valid_from.isoformat() if value.valid_from else None,
        "valid_to": value.valid_to.isoformat() if value.valid_to else None,
        "metadata": value.metadata or {},
    }


# ── Gold-record confidence (deterministic) ─────────────────────────────────


def gold_record_confidence(value_id: int) -> float:
    """Confidence (0..1) that ``value_id`` is THE gold master record.

    Components: active (+0.35), currently valid (+0.15), unique normalized
    label within its set (+0.25), metadata present (+0.05), active
    near-duplicates sharing the label (−0.20 each, capped −0.40), set
    lifecycle (active +0.20 / deprecated −0.10). Clamped to [0, 1].
    """
    value = ReferenceValue.objects.select_related("reference_set").filter(pk=value_id).first()
    if value is None:
        return 0.0
    return _confidence_for(value)


def _confidence_for(value: ReferenceValue) -> float:
    rs = value.reference_set
    today = timezone.now().date()
    active_values = list(rs.get_active_values())
    label_counts = Counter(_normalize(v.label) for v in active_values)
    norm_label = _normalize(value.label)

    score = 0.0
    if value.is_active:
        score += 0.35
    if _is_currently_valid(value, today):
        score += 0.15
    if label_counts.get(norm_label, 0) == 1:
        score += 0.25
    if value.metadata:
        score += 0.05
    if value.is_active:
        near_dups = label_counts.get(norm_label, 0) - 1
        score -= min(near_dups, 2) * 0.20

    lifecycle = rs.lifecycle_state
    if lifecycle == ReferenceSet.LIFECYCLE_ACTIVE:
        score += 0.20
    elif lifecycle == ReferenceSet.LIFECYCLE_DEPRECATED:
        score -= 0.10

    return round(min(max(score, 0.0), 1.0), 2)


# ── Explain an entity's master record ──────────────────────────────────────


def explain_entity(value_id: int) -> dict:
    """Explain this entity's master record + gold-record confidence."""
    value = (
        ReferenceValue.objects.select_related(
            "reference_set__domain", "reference_set__steward"
        ).filter(pk=value_id).first()
    )
    if value is None:
        return {"error": {"code": "not_found", "detail": f"Reference value {value_id} not found."}}

    rs = value.reference_set
    today = timezone.now().date()
    currently_valid = _is_currently_valid(value, today)
    if currently_valid:
        status = "current"
    elif not value.is_active:
        status = "inactive"
    elif value.valid_to is not None and value.valid_to < today:
        status = "expired"
    else:
        status = "scheduled"

    active_values = [v for v in rs.get_active_values() if v.id != value.id]
    near = [
        v for v in active_values
        if _normalize(v.label) == _normalize(value.label)
        or _label_similarity(v.label, value.label) >= 0.6
    ]

    confidence = _confidence_for(value)
    steward_name = None
    if rs.steward_id:
        steward_name = rs.steward.get_full_name() or rs.steward.username
    return {
        "entity": _value_summary(value),
        "master_record": {
            "reference_set": {
                "set_id": rs.id,
                "name": rs.name,
                "slug": rs.slug,
                "description": rs.description,
                "domain": rs.domain.name if rs.domain_id else None,
                "steward": steward_name,
                "version": rs.version,
                "lifecycle_state": rs.lifecycle_state,
                "set_active": rs.is_active,
            },
            "status": status,
            "currently_valid": currently_valid,
            "active_value_count": rs.get_active_values().count(),
        },
        "gold_record_confidence": confidence,
        "near_duplicates": [_value_summary(v) for v in near],
        "explanation": (
            f"'{value.label}' ({value.code}) is the master record for this entity "
            f"in reference set '{rs.name}'. It is {status} and carries "
            f"{confidence:.0%} gold-record confidence."
        ),
    }


# ── Dedup suggestions ──────────────────────────────────────────────────────


def _group_duplicates(values: Iterable[ReferenceValue], threshold: float) -> list[list[ReferenceValue]]:
    values = sorted(values, key=lambda v: v.id)
    norm_codes = {v.id: _normalize(v.code) for v in values}
    norm_labels = {v.id: _normalize(v.label) for v in values}
    groups: list[list[ReferenceValue]] = []
    assigned: set[int] = set()

    for v in values:
        if v.id in assigned:
            continue
        members = [v]
        for w in values:
            if w.id == v.id or w.id in assigned:
                continue
            same_code = norm_codes[v.id] and norm_codes[v.id] == norm_codes[w.id]
            same_label = norm_labels[v.id] and norm_labels[v.id] == norm_labels[w.id]
            similar = _label_similarity(v.label, w.label) >= threshold
            if same_code or same_label or similar:
                members.append(w)
        if len(members) >= 2:
            assigned.update(m.id for m in members)
            groups.append(members)
    return groups


def dedup_suggestions(set_id: int | None = None, threshold: float = 0.85) -> dict:
    """Entity-resolution dedup suggestions (never auto-merges).

    Groups active values per reference set sharing a normalized code or a
    near-duplicate label; each group names a canonical gold record.
    """
    if set_id is not None:
        rs = ReferenceSet.objects.filter(pk=set_id).first()
        if rs is None:
            return {"error": {"code": "not_found", "detail": f"Reference set {set_id} not found."}}
        sets = [rs]
    else:
        sets = list(ReferenceSet.objects.order_by("name"))

    suggestions: list[dict[str, Any]] = []
    today = timezone.now().date()
    for rs in sets:
        active = list(rs.get_active_values())
        label_counts = Counter(_normalize(v.label) for v in active)
        for group in _group_duplicates(active, threshold):
            confidences = {v.id: _confidence_for(v) for v in group}
            canonical = min(group, key=lambda v: (-confidences[v.id], v.id))
            members = sorted(group, key=lambda v: v.id)
            suggestions.append({
                "reference_set": {"set_id": rs.id, "name": rs.name},
                "group": [_value_summary(v) for v in members],
                "canonical_value_id": canonical.id,
                "canonical_code": canonical.code,
                "canonical_confidence": confidences[canonical.id],
                "member_count": len(members),
                "reason": _dup_reason(members, threshold),
                "action": "review_merge",
            })

    suggestions.sort(key=lambda s: (-s["canonical_confidence"], s["reference_set"]["name"]))
    return {"suggestions": suggestions, "count": len(suggestions)}


def _dup_reason(members: list[ReferenceValue], threshold: float) -> str:
    first, second = members[0], members[1]
    if _normalize(first.code) and _normalize(first.code) == _normalize(second.code):
        return f"same normalized code '{first.code}'"
    if _normalize(first.label) == _normalize(second.label):
        return f"same normalized label '{first.label}'"
    return (
        f"label similarity {_label_similarity(first.label, second.label):.0%} "
        f"(>= {threshold:.0%})"
    )


# ── Propose merge (RULE_21 — draft only) ───────────────────────────────────


def propose_merge(set_id: int, duplicate_value_id: int, gold_value_id: int) -> dict:
    """DRAFT a merge: deprecate the duplicate, keep the gold record.

    Never writes — returns a ``requires_confirmation`` payload describing the
    current state of both records and the proposed action.
    """
    rs = ReferenceSet.objects.filter(pk=set_id).first()
    if rs is None:
        return {"error": {"code": "not_found", "detail": f"Reference set {set_id} not found."}}

    dup = ReferenceValue.objects.filter(pk=duplicate_value_id, reference_set=rs).first()
    gold = ReferenceValue.objects.filter(pk=gold_value_id, reference_set=rs).first()
    if dup is None or gold is None:
        return {
            "error": {
                "code": "not_found",
                "detail": "Both records must exist in the same reference set.",
            }
        }
    if dup.id == gold.id:
        return {
            "error": {
                "code": "same_record",
                "detail": "Duplicate and gold records must differ.",
            }
        }

    return {
        "type": "mdm_merge_draft",
        "requires_confirmation": True,
        "summary": (
            f"Draft merge in '{rs.name}': deprecate '{dup.label}' ({dup.code}) "
            f"in favor of gold record '{gold.label}' ({gold.code})."
        ),
        "proposal": {
            "reference_set": {"set_id": rs.id, "name": rs.name},
            "duplicate": _value_summary(dup),
            "gold": _value_summary(gold),
            "gold_confidence": _confidence_for(gold),
            "duplicate_confidence": _confidence_for(dup),
            "action": "deprecate_duplicate_keep_gold",
            "effects": [
                f"Deactivate '{dup.label}' ({dup.code}) — historical rows keep their value.",
                f"'{gold.label}' ({gold.code}) remains the canonical master record.",
            ],
        },
        "never_executes": True,
    }
