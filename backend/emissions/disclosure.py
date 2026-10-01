"""P2 disclosure export shape. Maps existing ledger fields. No new kilogram.

CR-DIS-01. Status of benchmark P2 stays closed until a real filing consumes
this payload. evaluate_o1 stays the only O1 checklist.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from emissions.inventory_math import (
    LOCATION_BASED,
    display_scope2_method,
    market_based_absent,
    market_based_present,
)

FRAMEWORKS = frozenset({"esrs_e1", "ifrs_s2", "cdp"})
METHOD = "GHG Protocol Corporate Standard 2004; Scope 2 Guidance 2015"


def _kg(value: Any) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)), "f")


def build_disclosure(
    *,
    framework: str,
    period: Mapping[str, Any] | None,
    boundary: Mapping[str, Any] | None,
    scope1_kg: Any,
    scope2_location_kg: Any,
    scope2_market_kg: Any,
    market_present: bool,
    market_count: int = 0,
) -> dict[str, Any]:
    """Project existing Calculation aggregates onto named disclosure columns."""
    key = str(framework or "").strip().lower().replace("-", "_")
    if key not in FRAMEWORKS:
        raise ValueError("framework must be esrs_e1, ifrs_s2, or cdp")

    market = (
        market_based_present(market_count, scope2_market_kg)
        if market_present
        else market_based_absent()
    )
    market_kg = _kg(scope2_market_kg) if market_present else None
    location_kg = _kg(scope2_location_kg)
    scope1 = _kg(scope1_kg)

    shared = {
        "framework": key,
        "product": "Carbon on AASTMT",
        "status": "shape_only",
        "method": METHOD,
        "period": dict(period) if period else None,
        "boundary": dict(boundary) if boundary else None,
        "assurance": {"state": "not_assured", "met": False},
        "scope2_method_label": display_scope2_method(LOCATION_BASED),
        "market_based": market,
        "scope3": {"status": "closed_O5", "kg": None},
        "new_kilogram": False,
        "source": "Calculation rows for this reporting period. No new kilogram.",
        "limit": "Not an ESRS, IFRS, or CDP filing. Does not mark P2 passed.",
    }

    if key == "esrs_e1":
        shared["fields"] = {
            "E1-6_scope_1_kg": scope1,
            "E1-6_scope_2_location_based_kg": location_kg,
            "E1-6_scope_2_market_based_kg": market_kg,
            "E1-6_scope_2_market_based_status": "present" if market_present else "absent",
            "E1-6_scope_3_kg": None,
            "E1-6_assurance": "not_assured",
        }
    elif key == "ifrs_s2":
        shared["fields"] = {
            "S2_ghg_scope_1_kg": scope1,
            "S2_ghg_scope_2_location_based_kg": location_kg,
            "S2_ghg_scope_2_market_based_kg": market_kg,
            "S2_ghg_scope_3_kg": None,
            "S2_method": METHOD,
        }
    else:
        shared["fields"] = {
            "C6.1_scope_1_kg": scope1,
            "C6.3_scope_2_location_based_kg": location_kg,
            "C6.3_scope_2_market_based_kg": market_kg,
            "C6.5_scope_3_kg": None,
        }
    return shared
