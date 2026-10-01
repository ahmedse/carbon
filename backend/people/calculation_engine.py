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
#                 "divisor": "<rule data>",
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


class MissingVerifiedBasicError(Exception):
    """Raised when a regulated figure would otherwise read Employee.basic_salary.

    ADR-0029: payroll and indemnity share one authority — the verified
    monthly ``basic`` compensation-ledger line.
    """


class MissingNationalityError(Exception):
    """Raised when a Kuwaiti-scoped rule exists and nationality is blank.

    Seed/import use nationality code ``KWT`` for Kuwaiti nationals. Do not
    invent a code when the FK is empty — refuse the figure instead.
    """


class MissingPolicyFactError(Exception):
    """Raised when a formula names a fact the caller did not supply.

    The fact name comes from the rule. The engine does not invent a value.
    """

    def __init__(self, fact):
        self.fact = fact
        super().__init__(f"Missing required fact '{fact}'.")


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


def _require_facts(params: dict, inputs: dict) -> None:
    for fact in params.get("requires_facts") or []:
        if fact not in inputs or inputs.get(fact) in (None, ""):
            raise MissingPolicyFactError(fact)


def _base_amount(params: dict, inputs: dict) -> Decimal:
    names = params.get("base_inputs") or []
    return sum((_to_decimal(_require(inputs, name)) for name in names), Decimal("0"))


def _apply_excess(base: Decimal, params: dict, inputs: dict) -> Decimal:
    threshold = params.get("excess_over")
    if threshold is None:
        return base
    gate = params.get("excess_when_fact")
    if gate is not None:
        if inputs.get(gate) in (None, ""):
            raise MissingPolicyFactError(gate)
        if inputs.get(gate) is not True:
            return base
    return max(Decimal("0"), base - _to_decimal(threshold))


def _resolve_years(params: dict, inputs: dict) -> Decimal:
    proration = params.get("proration") or {}
    days_input = proration.get("days_input")
    if days_input and inputs.get(days_input) not in (None, ""):
        basis = _to_decimal(proration.get("basis", 1))
        if basis == 0:
            raise ValueError("proration basis must not be zero")
        return _to_decimal(inputs[days_input]) / basis
    return _to_decimal(_require(inputs, params["years_input"]))


def _eval_scaled_rate(params: dict, inputs: dict) -> Decimal:
    _require_facts(params, inputs)
    if "divisor" not in params:
        raise ValueError("scaled_rate requires a divisor")
    divisor = _to_decimal(params["divisor"])
    if divisor == 0:
        raise ValueError("scaled_rate divisor must not be zero")
    value = _base_amount(params, inputs) / divisor
    hours = params.get("hours_per_day")
    if hours not in (None, "", 0, "0"):
        hours_dec = _to_decimal(hours)
        if hours_dec == 0:
            raise ValueError("hours_per_day must not be zero")
        value = value / hours_dec
    value = value * _to_decimal(params.get("multiplier", 1))
    if params.get("quantity_input"):
        quantity = _to_decimal(_require(inputs, params["quantity_input"]))
    else:
        quantity = _to_decimal(params.get("quantity", 1))
    if params.get("max_quantity") is not None:
        quantity = min(quantity, _to_decimal(params["max_quantity"]))
    return (value * quantity).quantize(_QUANT, rounding=ROUND_HALF_UP)


def _eval_cumulative_accrual(params: dict, inputs: dict) -> Decimal:
    _require_facts(params, inputs)
    if "divisor" not in params:
        raise ValueError("cumulative_accrual requires a divisor")
    divisor = _to_decimal(params["divisor"])
    if divisor == 0:
        raise ValueError("cumulative_accrual divisor must not be zero")
    base = _apply_excess(_base_amount(params, inputs), params, inputs)
    years = _resolve_years(params, inputs)
    total = Decimal("0")
    for tier in params.get("tiers") or []:
        start = _to_decimal(tier.get("from_year", 0))
        until = tier.get("until_year")
        upper = years if until is None else min(years, _to_decimal(until))
        span = upper - start
        if span <= 0:
            continue
        if "days_per_year" in tier:
            total += (base / divisor) * _to_decimal(tier["days_per_year"]) * span
        elif "months_per_year" in tier:
            total += base * _to_decimal(tier["months_per_year"]) * span
        else:
            raise ValueError("tier needs days_per_year or months_per_year")
    return total.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _match_band(bands, reason: str, years: Decimal):
    for band in bands or []:
        if str(band.get("reason")) != reason:
            continue
        start = _to_decimal(band.get("from_years", 0))
        until = band.get("until_years")
        if years < start:
            continue
        if until is not None and years >= _to_decimal(until):
            continue
        return band
    return None


def _eval_banded_fraction(params: dict, inputs: dict) -> Decimal:
    _require_facts(params, inputs)
    reason_input = params.get("reason_input")
    if reason_input and inputs.get(reason_input) in (None, ""):
        raise MissingPolicyFactError(reason_input)
    inner = _eval_cumulative_accrual(params, inputs)
    amount = inner
    if reason_input:
        years = _resolve_years(params, inputs)
        band = _match_band(params.get("bands") or [], str(inputs[reason_input]), years)
        if band is None:
            raise ValueError("No fraction band matched the supplied reason and years.")
        denominator = _to_decimal(band.get("denominator", 1))
        if denominator == 0:
            raise ValueError("fraction denominator must not be zero")
        amount = inner * _to_decimal(band.get("numerator", 1)) / denominator
    if params.get("cap_months") is not None:
        base = _apply_excess(_base_amount(params, inputs), params, inputs)
        amount = min(amount, base * _to_decimal(params["cap_months"]))
    return amount.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _fund_basis(salary: Decimal, fund: dict) -> Decimal:
    mode = fund.get("slice") or "capped"
    if mode == "capped":
        ceiling = fund.get("ceiling")
        if ceiling is None:
            return salary
        return min(salary, _to_decimal(ceiling))
    if mode == "band":
        floor = _to_decimal(fund.get("floor", 0))
        width = _to_decimal(fund["width"])
        return min(max(Decimal("0"), salary - floor), width)
    raise ValueError(f"Unknown fund slice '{mode}'.")


def _eval_fund_table(params: dict, inputs: dict) -> dict:
    _require_facts(params, inputs)
    salary = _to_decimal(_require(inputs, params.get("salary_input", "insured_salary")))
    employee_total = Decimal("0")
    employer_total = Decimal("0")
    parts = []
    for fund in params.get("funds") or []:
        basis = _fund_basis(salary, fund)
        employee_share = (basis * _to_decimal(fund.get("employee_rate", 0))).quantize(
            _QUANT, rounding=ROUND_HALF_UP,
        )
        employer_share = (basis * _to_decimal(fund.get("employer_rate", 0))).quantize(
            _QUANT, rounding=ROUND_HALF_UP,
        )
        employee_total += employee_share
        employer_total += employer_share
        parts.append({
            "code": fund.get("code"),
            "basis": str(basis.quantize(_QUANT, rounding=ROUND_HALF_UP)),
            "employee_share": str(employee_share),
            "employer_share": str(employer_share),
        })
    return {
        "value": (employee_total + employer_total).quantize(_QUANT, rounding=ROUND_HALF_UP),
        "employee_share": employee_total.quantize(_QUANT, rounding=ROUND_HALF_UP),
        "employer_share": employer_total.quantize(_QUANT, rounding=ROUND_HALF_UP),
        "funds": parts,
    }


def _eval_day_ladder(params: dict, inputs: dict) -> Decimal:
    _require_facts(params, inputs)
    if "divisor" not in params:
        raise ValueError("day_ladder requires a divisor")
    divisor = _to_decimal(params["divisor"])
    if divisor == 0:
        raise ValueError("day_ladder divisor must not be zero")
    daily = _base_amount(params, inputs) / divisor
    remaining = _to_decimal(_require(inputs, params.get("days_input", "days")))
    total = Decimal("0")
    for band in params.get("bands") or []:
        if remaining <= 0:
            break
        take = min(remaining, _to_decimal(band["up_to_days"]))
        denominator = _to_decimal(band.get("denominator", 1))
        if denominator == 0:
            raise ValueError("ladder denominator must not be zero")
        total += daily * take * _to_decimal(band.get("numerator", 1)) / denominator
        remaining -= take
    return total.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _evaluate_formula(rule, inputs: dict):
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
    if kind == "scaled_rate":
        return _eval_scaled_rate(params, inputs)
    if kind == "cumulative_accrual":
        return _eval_cumulative_accrual(params, inputs)
    if kind == "banded_fraction":
        return _eval_banded_fraction(params, inputs)
    if kind == "day_ladder":
        return _eval_day_ladder(params, inputs)
    if kind == "fund_table":
        detail = _eval_fund_table(params, inputs)
        return detail
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


def _regulation_lineage(rule) -> dict:
    """Copy a cited regulation identity onto lineage. Empty when the rule cites none."""
    ref = (rule.inputs_schema or {}).get("regulation_ref") or {}
    out = {}
    if ref.get("pack") and ref.get("version"):
        out["regulation_pack"] = ref["pack"]
        out["regulation_version"] = str(ref["version"])
    if ref.get("rule_id") and ref.get("version"):
        out["regulation_rule_id"] = ref["rule_id"]
        out["regulation_version"] = str(ref["version"])
    return out


def calculate(rule, inputs: dict, *, allow_non_authoritative: bool = False) -> dict:
    """Generic, deterministic executor.

    Returns ``{"value": Decimal, "lineage": {"rule_id", "rule_version", "inputs"}}``.

    Guard: raises :class:`NonAuthoritativeRuleError` when the rule is missing or
    ``is_authoritative is False`` unless ``allow_non_authoritative=True``.
    """
    _guard(rule, allow_non_authoritative)
    evaluated = _evaluate_formula(rule, inputs)
    if isinstance(evaluated, dict):
        value = evaluated["value"]
        extra = {
            key: evaluated[key]
            for key in ("employee_share", "employer_share", "funds")
            if key in evaluated
        }
    else:
        value = evaluated
        extra = {}
    params = ((rule.inputs_schema or {}).get("formula") or {}).get("params") or {}
    if "compensatory_days" in params:
        extra["compensatory_days"] = params["compensatory_days"]
    return {
        "value": value,
        "lineage": {
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "inputs": inputs,
            **extra,
            **_regulation_lineage(rule),
        },
    }


def _formula_type(rule) -> str:
    return str(((getattr(rule, "inputs_schema", None) or {}).get("formula") or {}).get("type") or "")


def _select_matching(rules, category: str, *, as_of=None, formula_type=None) -> list:
    """Rules in ``category`` that are already effective on ``as_of``.

    When ``formula_type`` is set and at least one row has that type, the
    others stay out of the pick. An empty typed set falls back so a caller
    that only has one formula still resolves.
    """
    matching = _rules_for_category(rules, category)
    if as_of is not None:
        matching = [
            rule for rule in matching
            if getattr(rule, "effective_date", None) is not None and rule.effective_date <= as_of
        ]
    if formula_type:
        typed = [rule for rule in matching if _formula_type(rule) == formula_type]
        if typed:
            matching = typed
    return matching


def _find_rule(rules, category: str, *, as_of=None, formula_type=None):
    """Return the active rule for a category from a manager/queryset/list.

    "Active" = latest ``effective_date`` on or before ``as_of`` when a date
    is supplied (ties broken by ``updated_at``). Omitting ``as_of`` keeps
    the previous latest-row pick.
    """
    return _latest_rule(_select_matching(rules, category, as_of=as_of, formula_type=formula_type))


def _rules_for_category(rules, category: str) -> list:
    if rules is None:
        return []
    if hasattr(rules, "filter"):
        return list(rules.filter(category__code=category))
    out = []
    for rule in rules:
        cat = getattr(rule, "category", None)
        code = getattr(cat, "code", cat)
        if code == category:
            out.append(rule)
    return out


def _latest_rule(matching):
    if not matching:
        return None
    matching = list(matching)
    matching.sort(key=lambda r: (r.effective_date, r.updated_at), reverse=True)
    return matching[0]


def _nationality_code(employee) -> str:
    nat = _get_field(employee, "nationality")
    if nat is None:
        return ""
    if isinstance(nat, dict):
        return str(nat.get("code") or "").strip()
    return str(getattr(nat, "code", "") or "").strip()


def _is_kuwaiti_scoped_rule(rule) -> bool:
    rid = (getattr(rule, "rule_id", "") or "").lower()
    name = (getattr(rule, "name", "") or "").lower()
    return "kuwaiti" in rid or "kuwaiti national" in name


def _find_nationality_scoped_rule(rules, category: str, employee, *, as_of=None, formula_type=None):
    """Pick a category rule, fail-closed when Kuwaiti-only rules exist.

    Observed seed rule ids use a ``-kuwaiti`` suffix (``KWT`` nationality).
    If any such rule is in the set and the employee has no nationality, refuse
    rather than defaulting to the latest row (which can be the Kuwaiti divisor).
    ``as_of`` keeps a later effective date from applying to an earlier day.
    """
    matching = _select_matching(rules, category, as_of=as_of, formula_type=formula_type)
    if not matching:
        return None
    kuwaiti = [rule for rule in matching if _is_kuwaiti_scoped_rule(rule)]
    generic = [rule for rule in matching if not _is_kuwaiti_scoped_rule(rule)]
    if not kuwaiti:
        return _latest_rule(matching)
    code = _nationality_code(employee)
    if not code:
        raise MissingNationalityError(
            f"Employee has no nationality; refusing Kuwaiti-scoped {category} "
            "rule selection."
        )
    if code == "KWT":
        return _latest_rule(kuwaiti)
    if generic:
        return _latest_rule(generic)
    raise MissingNationalityError(
        f"Employee nationality {code} does not match a Kuwaiti-scoped "
        f"{category} rule and no general {category} rule exists."
    )


def _service_years(employee, as_of: date) -> Decimal:
    if not employee.join_date:
        return Decimal("0")
    days = (as_of - employee.join_date).days
    return (Decimal(days) / Decimal(365)).quantize(_YEARS_QUANT, rounding=ROUND_HALF_UP)


def _require_verified_basic(employee, as_of: date):
    """Return the verified ledger basic or refuse (ADR-0029 / NR-EOSI-01)."""
    from people.compensation_service import CompensationService

    amount = CompensationService.verified_basic_amount(employee, as_of=as_of)
    if amount is None:
        emp_no = getattr(employee, "employee_no", "?")
        raise MissingVerifiedBasicError(
            f"Employee {emp_no} has no verified monthly 'basic' compensation "
            "ledger line; refusing to compute from Employee.basic_salary."
        )
    return amount


def calculate_eosi(employee, rules, *, allow_non_authoritative: bool = False, as_of: date = None) -> dict:
    """Compute the EOSI (end-of-service indemnity) accrual for an employee."""
    rule = _find_nationality_scoped_rule(
        rules, "eosi", employee, formula_type="tiered_accrual",
    )
    as_of = as_of or timezone.now().date()
    if rule is None:
        return calculate(None, {}, allow_non_authoritative=allow_non_authoritative)
    params = _formula_params(rule)
    if params.get("base_kind") == "eosi_components":
        from people.compensation_service import CompensationService
        total = CompensationService.verified_eosi_base_amount(employee, as_of=as_of)
        if total is None:
            emp_no = getattr(employee, "employee_no", "?")
            raise MissingVerifiedBasicError(
                f"Employee {emp_no} has no verified earning lines flagged for "
                "the indemnity base; refusing to compute from Employee.basic_salary."
            )
        base_name = (params.get("base_inputs") or ["total_salary"])[0]
        inputs = {base_name: total, "service_years": _service_years(employee, as_of)}
        basic_source = "verified_eosi_components"
    else:
        basic = _require_verified_basic(employee, as_of)
        inputs = {
            "basic_salary": basic,
            "service_years": _service_years(employee, as_of),
        }
        basic_source = "verified_ledger"
    for fact in params.get("requires_facts") or []:
        inputs[fact] = getattr(employee, fact, None)
    reason_input = params.get("reason_input")
    if reason_input and reason_input not in inputs:
        inputs[reason_input] = getattr(employee, reason_input, None)
    result = calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)
    lineage = dict(result.get("lineage") or {})
    lineage["basic_source"] = basic_source
    result["lineage"] = lineage
    return result


def calculate_leave_accrual(employee, rules, *, allow_non_authoritative: bool = False, as_of: date = None) -> dict:
    """Compute annual leave accrual for an employee."""
    rule = _find_nationality_scoped_rule(
        rules, "leave", employee, formula_type="tiered_accrual",
    )
    as_of = as_of or timezone.now().date()
    if rule is None:
        return calculate(None, {}, allow_non_authoritative=allow_non_authoritative)
    basic = _require_verified_basic(employee, as_of)
    inputs = {
        "basic_salary": basic,
        "service_years": _service_years(employee, as_of),
    }
    result = calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)
    lineage = dict(result.get("lineage") or {})
    lineage["basic_source"] = "verified_ledger"
    result["lineage"] = lineage
    return result


def calculate_classified(rule, inputs: dict, *, allow_non_authoritative: bool = False) -> dict:
    """Price a formula only when the supplied class is one the rule bills.

    A missing class refuses. A class the rule does not bill returns zero.
    Class names and the billable list are rule data.
    """
    _guard(rule, allow_non_authoritative)
    params = _formula_params(rule)
    class_input = params.get("class_input")
    if class_input:
        if inputs.get(class_input) in (None, ""):
            raise MissingPolicyFactError(class_input)
        billable = [str(item) for item in (params.get("billable_classes") or [])]
        if str(inputs[class_input]) not in billable:
            return {
                "value": Decimal("0.000"),
                "lineage": {
                    "rule_id": rule.rule_id,
                    "rule_version": rule.version,
                    "inputs": inputs,
                    "billed": False,
                },
            }
    return calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)


def calculate_overtime(employee, inputs: dict, rules, *, allow_non_authoritative: bool = False) -> dict:
    """Compute overtime pay. ``inputs`` carries e.g. hours + overtime rate."""
    rule = _find_rule(rules, "overtime", formula_type="multiply")
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


def calculate_gross_pay(employee, inputs: dict, rules, *, allow_non_authoritative: bool = False, as_of: date = None) -> dict:
    """Compose gross pay (base + allowances + overtime) from a ``ComplianceRule``.

    The rule's ``sum`` formula names the components and ``inputs`` supplies their
    values. If the rule declares ``base_input`` in its params and ``inputs`` omits
    it, the employee's ``basic_salary`` fills that component so base salary always
    enters gross.
    """
    rule = _find_rule(rules, "payroll", as_of=as_of, formula_type="sum")
    if rule is not None and inputs is not None:
        base_input = _formula_params(rule).get("base_input")
        if base_input and base_input not in inputs:
            inputs = dict(inputs)
            inputs[base_input] = _require_verified_basic(
                employee, timezone.now().date(),
            )
    return calculate(rule, inputs, allow_non_authoritative=allow_non_authoritative)


def calculate_gosi(rule, gross_salary, employee_age=None, inputs=None, *, allow_non_authoritative: bool = False) -> dict:
    """Compute GOSI/KIFSS/PIFSS contribution (employee + employer shares).

    ``value`` is the total monthly contribution (employee + employer). Age-banded
    share rates and the optional salary cap come from the rule's params — never
    hardcoded.
    """
    _guard(rule, allow_non_authoritative)
    formula = (rule.inputs_schema or {}).get("formula") or {}
    if formula.get("type") == "fund_table":
        combined = dict(inputs) if inputs else {}
        salary_input = (formula.get("params") or {}).get("salary_input", "gross_salary")
        if gross_salary is not None:
            combined.setdefault(salary_input, gross_salary)
        if employee_age is not None:
            age_input = (formula.get("params") or {}).get("age_input", "employee_age")
            combined.setdefault(age_input, employee_age)
        return calculate(rule, combined, allow_non_authoritative=allow_non_authoritative)
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
            **_regulation_lineage(rule),
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
            **_regulation_lineage(rule),
        },
        "negative_net_pay": net < 0,
    }
