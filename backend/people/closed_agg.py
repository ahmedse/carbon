"""Shared RULE_12 + employee labels for named closed People aggregates."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from people.permissions import is_global_admin

EMP_DIMENSIONS = ("org_unit", "nationality", "position", "is_active")
DAYS_Q = Decimal("0.01")
MONEY_Q = Decimal("0.001")


def org_ids(user) -> list[int] | None:
    if is_global_admin(user):
        return None
    from people.views import _visible_org_unit_ids

    return list(_visible_org_unit_ids(user))


def employee_label(employee, dimension: str) -> str:
    if dimension == "org_unit":
        unit = getattr(employee, "org_unit", None)
        return (getattr(unit, "name", None) or "").strip() or "(blank)"
    if dimension == "nationality":
        ref = getattr(employee, "nationality", None)
        return (getattr(ref, "code", None) or "").strip() or "(blank)"
    if dimension == "position":
        pos = getattr(employee, "position", None)
        return (getattr(pos, "title", None) or "").strip() or "(blank)"
    if dimension == "is_active":
        return "active" if getattr(employee, "is_active", False) else "inactive"
    if dimension == "leave_type":
        ref = getattr(employee, "_leave_type", None) or getattr(employee, "leave_type", None)
        return (getattr(ref, "code", None) or "").strip() or "(blank)"
    if dimension == "loan_type":
        ref = getattr(employee, "_loan_type", None)
        return (getattr(ref, "code", None) or "").strip() or "(blank)"
    if dimension == "cert_type":
        ref = getattr(employee, "_cert_type", None)
        return (getattr(ref, "code", None) or "").strip() or "(blank)"
    if dimension == "status":
        return (getattr(employee, "_status", None) or "").strip() or "(blank)"
    return "(blank)"


def days(value: Decimal) -> str:
    return str(value.quantize(DAYS_Q, rounding=ROUND_HALF_UP))


def money(value: Decimal) -> str:
    return str(value.quantize(MONEY_Q, rounding=ROUND_HALF_UP))


def pct(num: Decimal, den: Decimal) -> float:
    if den <= 0:
        return 0.0
    return float((num / den * 100).quantize(DAYS_Q, rounding=ROUND_HALF_UP))
