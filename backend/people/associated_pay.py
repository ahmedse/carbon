"""Price associated-pay lines from authoritative rules that name a payslip line.

Numbers stay in the rule JSON. This module reads facts the People plane
already stores and asks the calculation engine to price them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .calculation_engine import MissingPolicyFactError, calculate, calculate_classified
from .models import AttendanceRecord, ComplianceRule, LeaveEntitlement, LeaveRecord


def _params(rule) -> dict:
    return ((rule.inputs_schema or {}).get("formula") or {}).get("params") or {}


def _applies(params: dict, employee) -> bool:
    who = params.get("applies_to") or "all"
    flagged = bool(getattr(employee, "kuwaitization", False))
    if who == "all":
        return True
    if who == "kuwaitization":
        return flagged
    if who == "direct":
        return not flagged
    return False


def posting_rules(employee, as_of=None) -> list:
    """Latest authoritative rule per payslip line code that applies to this employee.

    ``as_of`` drops versions that are not yet effective. The latest remaining
    effective date wins, then applicability.
    """
    chosen: dict[str, ComplianceRule] = {}
    qs = ComplianceRule.objects.filter(is_authoritative=True)
    if as_of is not None:
        qs = qs.filter(effective_date__lte=as_of)
    qs = qs.order_by("-effective_date", "-updated_at", "-pk")
    for rule in qs:
        params = _params(rule)
        code = params.get("payslip_line")
        if not code or code in chosen:
            continue
        if not _applies(params, employee):
            continue
        chosen[str(code)] = rule
    return list(chosen.values())


def completed_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


class ServiceGateError(Exception):
    """The published service minimum is not met. The figure is refused."""


def _gate(rule, employee, as_of: date, quantity: Decimal) -> None:
    raw = _params(rule).get("min_service_months")
    if raw is None or quantity <= 0:
        return
    start = getattr(employee, "join_date", None)
    if start is None:
        raise MissingPolicyFactError("join_date")
    if completed_months(start, as_of) < int(raw):
        code = _params(rule).get("payslip_line")
        raise ServiceGateError(
            f"Employee {employee.employee_no} has not completed the published "
            f"service minimum ({raw} months) for {code}."
        )


def _leave_days(employee, start, end, type_codes) -> Decimal | None:
    qs = LeaveRecord.objects.filter(
        employee=employee,
        status="approved",
        start_date__gte=start,
        end_date__lte=end,
    )
    if type_codes:
        qs = qs.filter(leave_type__code__in=list(type_codes))
    total = sum((record.days for record in qs), Decimal("0"))
    return total if total > 0 else None


def _entitlement_remaining(employee, end: date, type_codes) -> Decimal | None:
    qs = LeaveEntitlement.objects.filter(employee=employee, year=end.year)
    if type_codes:
        qs = qs.filter(leave_type__code__in=list(type_codes))
    total = Decimal("0")
    found = False
    for row in qs:
        found = True
        total += Decimal(row.entitled_days) + Decimal(row.carried_forward) - Decimal(row.used_days)
    if not found or total <= 0:
        return None
    return total


def _absence_days(employee, start, end, params) -> Decimal | None:
    records = list(AttendanceRecord.objects.filter(
        employee=employee,
        date__range=(start, end),
        status="absent",
    ))
    if not records:
        return None
    billable = set(params.get("billable_classes") or [])
    count = 0
    for record in records:
        if not (record.absence_class or "").strip():
            raise MissingPolicyFactError(params.get("class_input") or "absence_class")
        if record.absence_class in billable:
            count += 1
    return Decimal(count) if count else None


def _day_matches(day: date, params) -> bool:
    weekdays = params.get("weekdays")
    holidays = {str(item) for item in (params.get("holiday_dates") or [])}
    if weekdays is None and not holidays:
        return True
    if weekdays is not None and day.weekday() in {int(item) for item in weekdays}:
        return True
    return day.isoformat() in holidays


def _overtime(employee, start, end, params):
    records = [
        record for record in AttendanceRecord.objects.filter(
            employee=employee,
            date__range=(start, end),
        )
        if Decimal(record.overtime_hours or 0) > 0 and _day_matches(record.date, params)
    ]
    if not records:
        return None, {}
    hours = sum((Decimal(record.overtime_hours) for record in records), Decimal("0"))
    extras = {}
    per_day = params.get("compensatory_days")
    if per_day not in (None, "", 0, "0"):
        extras["compensatory_days"] = (Decimal(str(per_day)) * Decimal(len(records)))
    return hours, extras


def fact_for(rule, employee, start: date, end: date):
    """Return (quantity, extras). Quantity None means there is nothing to post."""
    params = _params(rule)
    source = params.get("fact_source")
    extras: dict = {}
    if source == "leave_days":
        quantity = _leave_days(employee, start, end, params.get("leave_type_codes") or [])
    elif source == "entitlement_balance":
        if params.get("require_separation") and not (getattr(employee, "separation_reason", "") or "").strip():
            return None, {}
        quantity = _entitlement_remaining(employee, end, params.get("leave_type_codes") or [])
    elif source == "attendance_absence":
        quantity = _absence_days(employee, start, end, params)
    elif source == "attendance_overtime":
        quantity, extras = _overtime(employee, start, end, params)
    else:
        return None, {}
    if quantity is None or quantity <= 0:
        return None, {}
    _gate(rule, employee, end, quantity)
    return quantity, extras


def _fill_bases(params, inputs, package, basic) -> None:
    for name in params.get("base_inputs") or []:
        if name in ("basic_salary", "basic"):
            inputs[name] = basic
        else:
            inputs[name] = package


def price(rule, quantity: Decimal, extras: dict, package, basic) -> dict:
    params = _params(rule)
    inputs: dict = {}
    _fill_bases(params, inputs, package, basic)
    quantity_name = params.get("quantity_input") or params.get("days_input") or "quantity"
    inputs[quantity_name] = quantity
    if params.get("class_input"):
        classes = params.get("billable_classes") or []
        inputs[params["class_input"]] = classes[0] if classes else ""
        result = calculate_classified(rule, inputs)
    else:
        result = calculate(rule, inputs)
    lineage = result["lineage"]
    merged = dict(lineage.get("inputs") or {})
    for key, value in extras.items():
        merged[key] = value
        lineage[key] = value
    lineage["inputs"] = merged
    result["effect"] = params.get("payslip_effect") or "earning"
    result["line_code"] = params["payslip_line"]
    return result


def priced_lines(employee, start: date, end: date, package, basic, *, rule_as_of=None, holds=None) -> list:
    """Price posting rules. ``holds`` collects per-rule refusals instead of aborting.

    The six-month gate and a missing join date still refuse that line. Other
    rules for the same employee continue. Omit ``holds`` and the refusal
    still raises.
    """
    rows = []
    for rule in posting_rules(employee, as_of=rule_as_of):
        try:
            quantity, extras = fact_for(rule, employee, start, end)
        except MissingPolicyFactError as exc:
            if holds is not None and exc.fact == "join_date":
                holds.append({
                    "reason": "missing join date",
                    "detail": "leave not priced",
                })
                continue
            raise
        except ServiceGateError as exc:
            if holds is not None:
                holds.append({
                    "reason": "leave not priced",
                    "detail": str(exc),
                })
                continue
            raise
        if quantity is None:
            continue
        rows.append(price(rule, quantity, extras, package, basic))
    return rows
