"""Inventory arithmetic that must stay labelled and offset-free.

Domain-app rules CR-S2-01 and CR-OFF-01. This module does not read the
database. evaluate_o1 stays the only O1 checklist.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

LOCATION_BASED = "location_based"
MARKET_BASED = "market_based"
SCOPE2_METHODS = frozenset({LOCATION_BASED, MARKET_BASED})

_OFFSET_KEYS = frozenset({
    "offset",
    "offsets",
    "offset_kg",
    "offset_tco2e",
    "offset_t",
    "credit",
    "credits",
    "carbon_credit",
    "carbon_credits",
    "rec",
    "recs",
    "eac",
    "eacs",
    "i_rec",
    "irec",
    "i-rec",
    "renewable_energy_certificate",
    "energy_attribute_certificate",
})


def normalize_scope2_method(value: Any, *, default: str | None = None) -> str | None:
    """Return location_based or market_based, else default (None if unlabelled)."""
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in SCOPE2_METHODS:
        return raw
    if default in SCOPE2_METHODS:
        return default
    return None


def display_scope2_method(value: Any, *, default: str | None = None) -> str | None:
    """Hyphenated label for UI and Pulse payloads."""
    method = normalize_scope2_method(value, default=default)
    if method is None:
        return None
    return method.replace("_", "-")


def is_offset_field(name: Any) -> bool:
    key = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    return key in _OFFSET_KEYS


def offset_keys_in(values: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(values, Mapping):
        return ()
    return tuple(key for key in values if is_offset_field(key))


def inventory_kg(
    activity_value: Any,
    factor_value: Any,
    values: Mapping[str, Any] | None = None,
) -> Decimal:
    """Activity × factor. Offset / credit / REC / EAC keys are ignored, never subtracted."""
    del values  # present so callers pass the row; keys must not enter the product
    activity = Decimal(str(activity_value))
    factor = Decimal(str(factor_value))
    return activity * factor


def activity_or_none(raw_value: Any) -> Decimal | None:
    if raw_value is None or raw_value == "":
        return None
    try:
        return Decimal(str(raw_value))
    except (InvalidOperation, ValueError, TypeError):
        return None


ABSENT_REASON = "no_distinct_contractual_factor"


def market_based_absent() -> dict[str, Any]:
    """Market-based is missing. Not zero. Not a copy of the grid."""
    return {
        "present": False,
        "reason": ABSENT_REASON,
        "scope2_method": display_scope2_method(MARKET_BASED),
    }


def market_based_present(count: int, total_co2e_kg: Any) -> dict[str, Any]:
    return {
        "present": True,
        "count": int(count),
        "total_co2e_kg": total_co2e_kg,
        "scope2_method": display_scope2_method(MARKET_BASED),
    }


def is_market_based_row(scope: Any, method: Any) -> bool:
    return int(scope or 0) == 2 and normalize_scope2_method(method) == MARKET_BASED


def labelled_scope2_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Drop unlabelled Scope 2 totals. Do not invent market-based."""
    out: list[dict[str, Any]] = []
    for row in rows:
        scope = int(row.get("scope") or 0)
        method = normalize_scope2_method(row.get("scope2_method"))
        if scope == 2 and method is None:
            continue
        item = dict(row)
        if scope == 2:
            item["scope2_method"] = method
        out.append(item)
    return out
