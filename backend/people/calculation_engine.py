# File: people/calculation_engine.py
# Rule-agnostic, deterministic Calculation Engine for the People app.
#
# This module COMPUTES regulated figures; it does NOT validate them (that is the
# DQ engine's job — docs/NIBRAS-MASTER-STRATEGY.md §6.2). Every numeric
# parameter comes from ``ComplianceRule`` rows — there are NO law constants in
# this file. The engine only knows how to interpret a small set of generic,
# parameterized formula shapes; the values (tiers, rates, divisors) are DATA.
#
# Formulas are declared in ``ComplianceRule.inputs_schema`` under a ``"formula"``
# key, e.g.::
#
#     {
#         "inputs": ["basic_salary", "service_years"],
#         "formula": {
#             "type": "tiered_accrual",
#             "params": {
#                 "base_inputs": ["basic_salary"],
#                 "years_input": "service_years",
#                 "divisor": 26,
#                 "tiers": [
#                     {"up_to": 5, "days_per_year": 15},
#                     {"up_to": None, "days_per_year": 30},
#                 ],
#             },
#         },
#     }
#
# Supported generic formula types (all parameterized, none carry law values):
#   * "tiered_accrual" — piecewise days/yr accrual over a base (EOSI, leave)
#   * "sum"            — sum of named input components (gross pay)
#   * "multiply"       — product of two named inputs (overtime)

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone


class NonAuthoritativeRuleError(Exception):
    """Raised when the engine is asked to compute a regulated figure from a
    missing or non-authoritative rule (without an explicit opt-in)."""


_QUANT = Decimal("0.001")
_YEARS_QUANT = Decimal("0.0001")


def _to_decimal(value) -> Decimal:
    return Decimal(str(value))


def _require(inputs: dict, name: str):
    if name not in inputs:
        raise KeyError(f"Missing required input '{name}'")
    return inputs[name]


def _select_tier(tiers, years: Decimal) -> Decimal:
    """Select the matching tier's ``days_per_year`` for a given service length."""
    for tier in tiers:
        up_to = tier.get("up_to")
        if up_to is None or years <= _to_decimal(up_to):
            return _to_decimal(tier["days_per_year"])
    raise ValueError(f"No tier matched for years={years}")


def _eval_tiered_accrual(params: dict, inputs: dict) -> Decimal:
    base = sum(_to_decimal(_require(inputs, name)) for name in params.get("base_inputs", []))
    years = _to_decimal(_require(inputs, params["years_input"]))
    divisor = _to_decimal(params.get("divisor", 1))
    if divisor == 0:
        raise ValueError("tiered_accrual divisor must not be zero")
    days_per_year = _select_tier(params.get("tiers", []), years)
    value = (base / divisor) * days_per_year * years
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _eval_sum(params: dict, inputs: dict) -> Decimal:
    total = sum(_to_decimal(_require(inputs, name)) for name in params.get("components", []))
    return total.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _eval_multiply(params: dict, inputs: dict) -> Decimal:
    a = _to_decimal(_require(inputs, params["a"]))
    b = _to_decimal(_require(inputs, params["b"]))
    return (a * b).quantize(_QUANT, rounding=ROUND_HALF_UP)


def _evaluate_formula(rule, inputs: dict) -> Decimal:
    schema = rule.inputs_schema or {}
    formula = schema.get("formula")
    if not formula:
        raise ValueError(
            f"Rule '{rule.rule_id} v{rule.version}' has no formula declared in inputs_schema."
        )
    kind = formula.get("type")
    params = formula.get("params") or {}

    if kind == "tiered_accrual":
        return _eval_tiered_accrual(params, inputs)
    if kind == "sum":
        return _eval_sum(params, inputs)
    if kind == "multiply":
        return _eval_multiply(params, inputs)
    raise ValueError(
        f"Rule '{rule.rule_id} v{rule.version}' declares unknown formula type '{kind}'."
    )


def _guard(rule, allow_non_authoritative: bool) -> None:
    """Enforce the authoritative-rule guard shared by every engine entry point."""
    if rule is None:
        raise NonAuthoritativeRuleError(
            "No ComplianceRule is available for this calculation."
        )
    if not rule.is_authoritative and not allow_non_authoritative:
        raise NonAuthoritativeRuleError(
            f"Rule '{rule.rule_id} v{rule.version}' is non-authoritative; "
            "refusing to compute a regulated figure. "
            "Pass allow_non_authoritative=True to opt in."
        )


def calculate(rule, inputs: dict, *, allow_non_authoritative: bool = False) -> dict:
    """Generic, deterministic executor.

    Returns ``{"value": Decimal, "lineage": {"rule_id", "rule_version", "inputs"}}``.

    Guard: raises :class:`NonAuthoritativeRuleError` when the rule is missing or
    ``is_authoritative is False`` unless ``allow_non_authoritative=True``.
    """
    _guard(rule, allow_non_authoritative)
    value = _evaluate_formula(rule, inputs)
    return {
        "value": value,
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": inputs,
        },
    }


def _find_rule(rules, category: str):
    """Return the active rule for a category from a manager/queryset/list.

    "Active" = latest ``effective_date`` (ties broken by ``updated_at``).
    """
    if rules is None:
        return None
    if hasattr(rules, "filter"):
        return rules.filter(category=category).order_by("-effective_date", "-updated_at").first()
    matching = [r for r in rules if getattr(r, "category", None) == category]
    if not matching:
        return None
    matching.sort(key=lambda r: (r.effective_date, r.updated_at), reverse=True)
    return matching[0]


def _service_years(employee, as_of: date) -> Decimal:
    if not employee.join_date:
        return Decimal("0")
    days = (as_of - employee.join_date).days
    return (Decimal(days) / Decimal(365)).quantize(_YEARS_QUANT, rounding=ROUND_HALF_UP)


def calculate_eosi(employee, rules, *, allow_non_authoritative: bool = False, as_of: date = None) -> dict:
    """Compute the EOSI (end-of-service indemnity) accrual for an employee."""
    rule = _find_rule(rules, "eosi")
    as_of = as_of or timezone.now().date()
    inputs = {
        "basic_salary": employee.basic_salary,
        "service_years": _service_years(employee, as_of),
    }
    return calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)


def calculate_leave_accrual(employee, rules, *, allow_non_authoritative: bool = False, as_of: date = None) -> dict:
    """Compute annual leave accrual for an employee."""
    rule = _find_rule(rules, "leave")
    as_of = as_of or timezone.now().date()
    inputs = {
        "basic_salary": employee.basic_salary,
        "service_years": _service_years(employee, as_of),
    }
    return calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)


def calculate_overtime(employee, inputs: dict, rules, *, allow_non_authoritative: bool = False) -> dict:
    """Compute overtime pay. ``inputs`` carries e.g. hours + overtime rate."""
    rule = _find_rule(rules, "overtime")
    return calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)


def _formula_params(rule) -> dict:
    """Return the ``formula.params`` dict from a rule's ``inputs_schema`` (empty if absent)."""
    schema = rule.inputs_schema or {}
    formula = schema.get("formula") or {}
    return formula.get("params") or {}


def _get_field(obj, name, default=None):
    """Read a field from a model instance or a plain mapping (duck-typed)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _select_band_rate(bands, age: Decimal) -> Decimal:
    """Select the matching band's ``rate`` for a given age."""
    for band in bands:
        max_age = band.get("max_age")
        if max_age is None or age <= _to_decimal(max_age):
            return _to_decimal(band["rate"])
    raise ValueError(f"No band matched for age={age}")


def calculate_gross_pay(employee, inputs: dict, rules, *, allow_non_authoritative: bool = False) -> dict:
    """Compose gross pay (base + allowances + overtime) from a ``ComplianceRule``.

    The rule's ``sum`` formula names the components and ``inputs`` supplies their
    values. If the rule declares ``base_input`` in its params and ``inputs`` omits
    it, the employee's ``basic_salary`` fills that component so base salary always
    enters gross.
    """
    rule = _find_rule(rules, "payroll")
    if rule is not None and inputs is not None:
        base_input = _formula_params(rule).get("base_input")
        if base_input and base_input not in inputs:
            inputs = dict(inputs)
            inputs[base_input] = employee.basic_salary
    return calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)


def calculate_gosi(rule, gross_salary, employee_age=None, inputs=None, *, allow_non_authoritative: bool = False) -> dict:
    """Compute GOSI/KIFSS/PIFSS contribution (employee + employer shares).

    ``value`` is the total monthly contribution (employee + employer). Age-banded
    share rates and the optional salary cap come from the rule's params — never
    hardcoded.
    """
    _guard(rule, allow_non_authoritative)
    params = _formula_params(rule)
    salary_input = params.get("salary_input", "gross_salary")
    age_input = params.get("age_input", "employee_age")

    combined = dict(inputs) if inputs else {}
    if gross_salary is not None:
        combined.setdefault(salary_input, gross_salary)
    if employee_age is not None:
        combined.setdefault(age_input, employee_age)

    salary = _to_decimal(_require(combined, salary_input))
    cap = params.get("cap")
    if cap is not None:
        salary = min(salary, _to_decimal(cap))

    age = _to_decimal(combined.get(age_input, 0))
    employee_rate = _select_band_rate(params.get("employee_bands") or [], age)
    employer_rate = _select_band_rate(params.get("employer_bands") or [], age)

    employee_share = (salary * employee_rate).quantize(_QUANT, rounding=ROUND_HALF_UP)
    employer_share = (salary * employer_rate).quantize(_QUANT, rounding=ROUND_HALF_UP)
    total = (employee_share + employer_share).quantize(_QUANT, rounding=ROUND_HALF_UP)

    return {
        "value": total,
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": combined,
            "employee_share": employee_share,
            "employer_share": employer_share,
            "employee_rate": employee_rate,
            "employer_rate": employer_rate,
        },
    }


def format_wps_record(rule, payslip, inputs=None, *, allow_non_authoritative: bool = False) -> dict:
    """Build the WPS record payload dict from rule params + payslip fields.

    ``value`` is the total payable amount (sum of the rule's ``amount_components``).
    The full payload is returned under ``record``; no file I/O happens here.
    """
    _guard(rule, allow_non_authoritative)
    params = _formula_params(rule)
    field_map = params.get("field_map") or {}
    amount_components = params.get("amount_components") or []

    record = {record_key: _get_field(payslip, source) for record_key, source in field_map.items()}
    for key, value in (params.get("static_fields") or {}).items():
        record[key] = value

    amounts = [_to_decimal(_get_field(payslip, name, 0)) for name in amount_components]
    total = sum(amounts, Decimal("0")).quantize(_QUANT, rounding=ROUND_HALF_UP)
    record["amount"] = total

    lineage_inputs = dict(inputs) if inputs else {}
    for name in amount_components:
        lineage_inputs.setdefault(name, _get_field(payslip, name, 0))
    for source in field_map.values():
        lineage_inputs.setdefault(source, _get_field(payslip, source))

    return {
        "value": total,
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": lineage_inputs,
        },
        "record": record,
    }


def calculate_leave_split(rule, leave_record, inputs=None, *, allow_non_authoritative: bool = False) -> dict:
    """Calendar-split a leave record across KLL calendar years.

    ``value`` is the total leave days; ``calendar_split`` maps each calendar year
    to the days falling in it. The counting convention (inclusive end date) is
    read from rule params, not hardcoded.
    """
    _guard(rule, allow_non_authoritative)
    params = _formula_params(rule)
    start_input = params.get("start_input", "start_date")
    end_input = params.get("end_input", "end_date")
    inclusive = bool(params.get("inclusive", True))

    start_date = _get_field(leave_record, start_input)
    end_date = _get_field(leave_record, end_input)
    if start_date is None or end_date is None:
        raise KeyError("Leave record is missing its start/end date.")
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("Leave split requires date start/end values.")

    split = {}
    current = start_date
    last = end_date if inclusive else end_date - timedelta(days=1)
    while current <= last:
        split[current.year] = split.get(current.year, 0) + 1
        current = current + timedelta(days=1)

    calendar_split = {str(year): Decimal(days) for year, days in split.items()}
    total = sum((Decimal(days) for days in split.values()), Decimal("0"))

    lineage_inputs = dict(inputs) if inputs else {}
    lineage_inputs.setdefault(start_input, str(start_date))
    lineage_inputs.setdefault(end_input, str(end_date))

    return {
        "value": total.quantize(_QUANT, rounding=ROUND_HALF_UP),
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": lineage_inputs,
        },
        "calendar_split": calendar_split,
    }


def _balance_last(installments: list, principal_total: Decimal, interest_total: Decimal) -> None:
    """Absorb rounding drift into the final installment so column sums are exact."""
    if not installments:
        return
    principal_sum = sum((i["principal_portion"] for i in installments[:-1]), Decimal("0"))
    interest_sum = sum((i["interest_portion"] for i in installments[:-1]), Decimal("0"))
    last = installments[-1]
    last["principal_portion"] = (principal_total - principal_sum).quantize(_QUANT, rounding=ROUND_HALF_UP)
    last["interest_portion"] = (interest_total - interest_sum).quantize(_QUANT, rounding=ROUND_HALF_UP)
    last["amount"] = (last["principal_portion"] + last["interest_portion"]).quantize(_QUANT, rounding=ROUND_HALF_UP)


def _flat_schedule(principal: Decimal, period_rate: Decimal, term: int) -> list:
    """Flat-rate amortization: equal principal + equal interest every installment."""
    total_interest = (principal * period_rate * Decimal(term)).quantize(_QUANT, rounding=ROUND_HALF_UP)
    principal_each = (principal / Decimal(term)).quantize(_QUANT, rounding=ROUND_HALF_UP)
    interest_each = (total_interest / Decimal(term)).quantize(_QUANT, rounding=ROUND_HALF_UP)
    installments = []
    for i in range(1, term + 1):
        installments.append({
            "installment_no": i,
            "principal_portion": principal_each,
            "interest_portion": interest_each,
            "amount": (principal_each + interest_each).quantize(_QUANT, rounding=ROUND_HALF_UP),
        })
    _balance_last(installments, principal, total_interest)
    return installments


def _reducing_schedule(principal: Decimal, period_rate: Decimal, term: int) -> list:
    """Reducing-balance amortization: interest accrues on the outstanding balance."""
    installments = []
    remaining = principal
    if period_rate == 0:
        principal_each = (principal / Decimal(term)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        for i in range(1, term + 1):
            installments.append({
                "installment_no": i,
                "principal_portion": principal_each,
                "interest_portion": Decimal("0"),
                "amount": principal_each,
            })
        _balance_last(installments, principal, Decimal("0"))
        return installments

    one = Decimal("1")
    factor = (one + period_rate) ** term
    emi = (principal * period_rate * factor) / (factor - one)
    emi = emi.quantize(_QUANT, rounding=ROUND_HALF_UP)
    for i in range(1, term + 1):
        interest_i = (remaining * period_rate).quantize(_QUANT, rounding=ROUND_HALF_UP)
        principal_i = remaining if i == term else (emi - interest_i).quantize(_QUANT, rounding=ROUND_HALF_UP)
        remaining -= principal_i
        installments.append({
            "installment_no": i,
            "principal_portion": principal_i,
            "interest_portion": interest_i,
            "amount": (principal_i + interest_i).quantize(_QUANT, rounding=ROUND_HALF_UP),
        })
    return installments


def calculate_loan_schedule(rule, loan, inputs=None, *, allow_non_authoritative: bool = False) -> dict:
    """Amortize a loan into installments (flat vs reducing, per rule params).

    ``value`` is total repayable (principal + interest); the installment list is
    returned under ``installments``.
    """
    _guard(rule, allow_non_authoritative)
    params = _formula_params(rule)
    principal_input = params.get("principal_input", "principal")
    rate_input = params.get("rate_input", "interest_rate")
    term_input = params.get("term_input", "term_months")
    method = params.get("method", "flat")
    rate_is_annual = bool(params.get("rate_is_annual", True))
    rate_is_percent = bool(params.get("rate_is_percent", False))
    periods_per_year = _to_decimal(params.get("periods_per_year", 12))

    principal = _to_decimal(_get_field(loan, principal_input))
    raw_rate = _to_decimal(_get_field(loan, rate_input, 0))
    term = int(_get_field(loan, term_input))

    rate = raw_rate / Decimal(100) if rate_is_percent else raw_rate
    period_rate = rate / periods_per_year if rate_is_annual else rate

    if method == "flat":
        installments = _flat_schedule(principal, period_rate, term)
    elif method == "reducing":
        installments = _reducing_schedule(principal, period_rate, term)
    else:
        raise ValueError(
            f"Rule '{rule.rule_id} v{rule.version}' declares unknown loan method '{method}'."
        )

    total_interest = sum((i["interest_portion"] for i in installments), Decimal("0"))
    total_repayable = (principal + total_interest).quantize(_QUANT, rounding=ROUND_HALF_UP)

    lineage_inputs = dict(inputs) if inputs else {}
    lineage_inputs.setdefault(principal_input, principal)
    lineage_inputs.setdefault(rate_input, raw_rate)
    lineage_inputs.setdefault(term_input, term)

    return {
        "value": total_repayable,
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": lineage_inputs,
        },
        "installments": installments,
    }


def calculate_net_pay(rule, gross, deductions, inputs=None, *, allow_non_authoritative: bool = False) -> dict:
    """Compute net pay = gross − Σdeductions.

    A negative net is *flagged* in the output (``negative_net_pay``), never raised —
    validation is the DQ engine's job.
    """
    _guard(rule, allow_non_authoritative)
    params = _formula_params(rule)
    gross_input = params.get("gross_input", "gross")
    deductions_input = params.get("deductions_input", "deductions")

    gross_d = _to_decimal(gross)
    deduction_values = [_to_decimal(d) for d in (deductions or [])]
    total_deductions = sum(deduction_values, Decimal("0"))
    net = (gross_d - total_deductions).quantize(_QUANT, rounding=ROUND_HALF_UP)

    lineage_inputs = dict(inputs) if inputs else {}
    lineage_inputs.setdefault(gross_input, gross_d)
    lineage_inputs.setdefault(deductions_input, deduction_values)

    return {
        "value": net,
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": lineage_inputs,
        },
        "negative_net_pay": net < 0,
    }
