"""Loan-type alias seed (mirrors leave_type_resolve).

``mdm.reference_resolve`` is the only matcher. This module merges common
Arabic/English spellings into ``metadata.aliases`` so briefs like
``أريد قرض طوارئ`` ground ``loan_type=emergency`` without a regex in Pulse.
"""
from __future__ import annotations

# Defaults applied when metadata.aliases is empty or missing a common spelling.
LOAN_TYPE_ALIASES: dict[str, list[str]] = {
    "personal": ["personal", "personal loan", "سلفة شخصية", "قرض شخصي", "شخصي"],
    "vehicle": ["vehicle", "vehicle loan", "car", "car loan", "سلفة سيارة", "قرض سيارة", "سيارة"],
    "housing": ["housing", "housing loan", "mortgage", "سلفة سكن", "قرض سكن", "سكن"],
    "education": ["education", "education loan", "سلفة تعليم", "قرض تعليم", "تعليم"],
    "emergency": [
        "emergency",
        "emergency loan",
        "سلفة طارئة",
        "سلفة طوارئ",
        "قرض طوارئ",
        "قرض طارئ",
        "طوارئ",
        "طارئ",
    ],
}


def ensure_loan_type_aliases() -> int:
    """Idempotently merge default aliases (+ label_ar) into loan_type values."""
    from mdm.models import ReferenceValue

    updated = 0
    rows = ReferenceValue.objects.filter(
        reference_set__name="loan_type", is_active=True,
    )
    for rv in rows:
        meta = dict(rv.metadata or {})
        existing = meta.get("aliases") or []
        if not isinstance(existing, list):
            existing = []
        extras = list(LOAN_TYPE_ALIASES.get(rv.code, []))
        label_ar = meta.get("label_ar")
        if label_ar:
            extras.append(str(label_ar))
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*existing, *extras]:
            needle = " ".join(str(item or "").strip().casefold().split())
            if not needle or needle in seen:
                continue
            seen.add(needle)
            merged.append(str(item).strip())
        if merged != existing:
            meta["aliases"] = merged
            rv.metadata = meta
            rv.save(update_fields=["metadata"])
            updated += 1
    return updated
