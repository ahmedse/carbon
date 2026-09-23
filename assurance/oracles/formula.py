"""Hand-implemented regulated-figure shapes.

This is a test oracle. It must stay independent of
``people.calculation_engine``. Expected values in pack fixtures are
hand-computed, not copied from that module.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

_QUANT = Decimal("0.001")


def _d(value) -> Decimal:
    return Decimal(str(value))


def eval_sum(params: dict, inputs: dict) -> Decimal:
    total = sum(_d(inputs[name]) for name in params["components"])
    return total.quantize(_QUANT, rounding=ROUND_HALF_UP)


def eval_multiply(params: dict, inputs: dict) -> Decimal:
    return (_d(inputs[params["a"]]) * _d(inputs[params["b"]])).quantize(
        _QUANT, rounding=ROUND_HALF_UP
    )


def eval_tiered_accrual(params: dict, inputs: dict) -> Decimal:
    base = sum(_d(inputs[name]) for name in params["base_inputs"])
    years = _d(inputs[params["years_input"]])
    divisor = _d(params["divisor"])
    if divisor == 0:
        raise ValueError("divisor must not be zero")
    days = None
    for tier in params["tiers"]:
        up_to = tier.get("up_to")
        if up_to is None or years <= _d(up_to):
            days = _d(tier["days_per_year"])
            break
    if days is None:
        raise ValueError(f"no tier for years={years}")
    return ((base / divisor) * days * years).quantize(_QUANT, rounding=ROUND_HALF_UP)


def evaluate(kind: str, params: dict, inputs: dict) -> Decimal:
    if kind == "sum":
        return eval_sum(params, inputs)
    if kind == "multiply":
        return eval_multiply(params, inputs)
    if kind == "tiered_accrual":
        return eval_tiered_accrual(params, inputs)
    raise ValueError(f"unknown formula type {kind!r}")
