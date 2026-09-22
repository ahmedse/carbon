"""Governed value resolution — one seam for every reference set (ADR-0027).

``mdm.ReferenceValue`` is the SSOT for governed slots (``leave_type``,
``loan_type``, ``permission_type``, …). Resolution matches, in order, the
value's ``code``, its ``label``, then ``metadata.aliases`` — so adding an
Arabic/English synonym is a **data** change in MDM, never a regex branch in
Chat, Agent or the frontend.

Callers: host ESS validation, Agent plan slot filling, consent forms. No
surface may keep its own synonym table.
"""
from __future__ import annotations

from mdm.models import ReferenceValue


def _norm(text: object) -> str:
    return " ".join(str(text or "").strip().casefold().split())


def _active(set_name: str) -> list[ReferenceValue]:
    if not str(set_name or "").strip():
        return []
    return list(
        ReferenceValue.objects.filter(
            reference_set__name=set_name, is_active=True,
        ).order_by("sort_order", "code"),
    )


def _needles(value: ReferenceValue) -> list[str]:
    """Every spelling that identifies this value, longest first."""
    aliases = (value.metadata or {}).get("aliases") or []
    raw = [value.code, value.label, *(aliases if isinstance(aliases, list) else [])]
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        needle = _norm(item)
        if needle and needle not in seen:
            seen.add(needle)
            out.append(needle)
    out.sort(key=len, reverse=True)
    return out


def resolve_reference(set_name: str, raw: object) -> ReferenceValue | None:
    """Map free text to an active governed value in ``set_name``."""
    needle = _norm(raw)
    if not needle:
        return None
    values = _active(set_name)
    for value in values:
        if _norm(value.code) == needle:
            return value
    for value in values:
        if _norm(value.label) == needle:
            return value
    for value in values:
        if needle in _needles(value):
            return value
    return None


def find_reference_in_text(set_name: str, text: object) -> ReferenceValue | None:
    """Pick the governed value a free-text utterance names, if any.

    Longest spelling wins, so "إجازة عارضة" never matches on a shorter
    alias of a different value that happens to be a substring.
    """
    haystack = _norm(text)
    if not haystack:
        return None
    best: tuple[int, ReferenceValue] | None = None
    for value in _active(set_name):
        for needle in _needles(value):
            if needle and needle in haystack:
                if best is None or len(needle) > best[0]:
                    best = (len(needle), value)
                break
    return best[1] if best else None


def reference_options(set_name: str) -> list[dict]:
    """``[{code, label}, …]`` for operator-facing pickers and error hints."""
    return [
        {"code": value.code, "label": value.label}
        for value in _active(set_name)
    ]


def is_reference_set(set_name: str) -> bool:
    """True when ``set_name`` is a governed set with active values."""
    return bool(_active(set_name))
