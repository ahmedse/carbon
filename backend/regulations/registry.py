# regulations/registry.py
# Pluggable evaluator registry. Domain apps (people, finance, …) register
# their evaluators in their AppConfig.ready(). The regulations engine
# never imports directly from domain apps — it only looks up by formula_type.
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Obligation, AuditRun

_REGISTRY: dict[str, type] = {}


def register(formula_type: str):
    """Class decorator — registers an evaluator class for a formula_type key."""
    def decorator(cls):
        _REGISTRY[formula_type] = cls
        return cls
    return decorator


def get_evaluator(formula_type: str) -> type | None:
    return _REGISTRY.get(formula_type)


def list_registered() -> dict[str, type]:
    return dict(_REGISTRY)


class BaseEvaluator:
    """
    Contract all evaluators must implement.

    get_scope_items(run) → list of (scope_type: str, scope_id: int, label: str)
    evaluate(scope_type, scope_id, run) → dict with keys:
        status:   'compliant' | 'non_compliant' | 'partial' | 'na' | 'error'
        actual:   the measured value (any serializable)
        expected: the required/target value
        delta:    actual - expected (negative = deficit)
        detail:   dict of extra context for the finding record
    """

    def __init__(self, obligation: "Obligation"):
        self.obligation = obligation
        self.params = obligation.formula_params

    def get_scope_items(self, run: "AuditRun") -> list[tuple[str, int, str]]:
        raise NotImplementedError

    def evaluate(self, scope_type: str, scope_id: int, run: "AuditRun") -> dict:
        raise NotImplementedError
