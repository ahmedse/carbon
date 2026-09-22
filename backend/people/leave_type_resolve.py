"""Resolve leave_type user/LLM labels → governed ReferenceValue codes.

SSOT: ``mdm.ReferenceValue`` for ``reference_set=leave_type``. Synonyms live in
``metadata.aliases`` (and the value's ``label`` / ``code``). Callers must not
hardcode Arabic/English maps in Chat — matching itself lives in
``mdm.reference_resolve`` so every governed set (leave, loan, permission …)
and every surface (HTTP ESS, Agent confirm, Chat tool) shares one seam. This
module only carries the leave seed aliases for pre-seed databases.
"""
from __future__ import annotations

from mdm.models import ReferenceValue
from mdm.reference_resolve import resolve_reference

# Built-in fallbacks applied when metadata.aliases is empty (pre-seed DBs).
# Still keyed by governed codes — not a Chat-only alias table.
_DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "emergency": (
        "عارضة",
        "عارضي",
        "اجازة عارضة",
        "إجازة عارضة",
        "casual",
        "casual leave",
        "emergency leave",
        "طارئة",
        "اجازة طارئة",
        "إجازة طارئة",
    ),
    "annual": (
        "سنوية",
        "اجازة سنوية",
        "إجازة سنوية",
        # Nibras HR wording: staff say "عادية" / bare "عادي" (ordinary/regular)
        # for annual — live Agent QA failed when only feminine forms were seeded.
        "عادي",
        "عادية",
        "عاديه",
        "اعتيادي",
        "اعتيادية",
        "اجازة عادي",
        "اجازة عادية",
        "إجازة عادي",
        "إجازة عادية",
        "annual leave",
        "regular leave",
        "ordinary leave",
        "vacation",
    ),
    "sick": (
        "مرضية",
        "اجازة مرضية",
        "إجازة مرضية",
        "sick leave",
    ),
    "unpaid": (
        "بدون راتب",
        "unpaid leave",
    ),
    "maternity": (
        "أمومة",
        "maternity leave",
    ),
    "paternity": (
        "أبوة",
        "paternity leave",
    ),
}


def _norm(text: str) -> str:
    return " ".join(str(text or "").strip().casefold().split())


def ensure_leave_type_aliases() -> int:
    """Idempotently merge default aliases into ReferenceValue.metadata.

    Safe to call from seed / ensure commands. Returns number of rows updated.
    """
    updated = 0
    qs = ReferenceValue.objects.filter(reference_set__name="leave_type", is_active=True)
    for rv in qs:
        defaults = list(_DEFAULT_ALIASES.get(rv.code, ()))
        if not defaults:
            continue
        meta = dict(rv.metadata or {})
        existing = meta.get("aliases") or []
        if not isinstance(existing, list):
            existing = []
        merged = list(existing)
        for alias in defaults:
            if alias not in merged:
                merged.append(alias)
        if merged != existing:
            meta["aliases"] = merged
            rv.metadata = meta
            rv.save(update_fields=["metadata", "updated_at"])
            updated += 1
    return updated


def resolve_leave_type(raw: str | None) -> ReferenceValue | None:
    """Map a free-text leave type to an active governed ReferenceValue.

    Governed matching (code → label → ``metadata.aliases``) lives in
    ``mdm.reference_resolve``; the seed table below covers databases whose
    aliases were never merged.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    resolved = resolve_reference("leave_type", raw)
    if resolved is not None:
        return resolved
    needle = _norm(raw)
    qs = ReferenceValue.objects.filter(reference_set__name="leave_type", is_active=True)
    for rv in qs:
        for alias in _DEFAULT_ALIASES.get(rv.code, ()):
            if _norm(alias) == needle:
                return rv
    return None


def allowed_leave_type_payload() -> list[dict]:
    """Compact catalog for error hints / recovery synthesis (RULE_23)."""
    rows = []
    for rv in ReferenceValue.objects.filter(
        reference_set__name="leave_type", is_active=True
    ).order_by("sort_order", "code"):
        aliases = (rv.metadata or {}).get("aliases") or list(
            _DEFAULT_ALIASES.get(rv.code, ())
        )
        rows.append({
            "code": rv.code,
            "label": rv.label,
            "aliases": aliases if isinstance(aliases, list) else [],
        })
    return rows
