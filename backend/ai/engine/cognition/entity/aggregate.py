"""ECF-6 — Canonical metric aggregation.

aggregate(descriptor, metric, *, count_fn) → AggregateResult

The algorithm is domain-neutral. Metric definitions (filters + descriptions)
come from EntityDescriptor.metrics (ADR-0032). The injectable ``count_fn``
keeps the engine database-free (RULE_20) — the host executor resolves the
model path and applies RULE_12 org scope.

Canonical examples (HRMS employee descriptor):
  headcount → filter {is_active: True}
  kuwaiti   → filter {nationality_code: "KW"}  (NOT the kuwaitization boolean)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ai.engine.cognition.entity.registry import EntityDescriptor

# Inject: callable(model_path, filters) → int
CountFn = Callable[[str, dict], int]


@dataclass(frozen=True)
class AggregateResult:
    """Result of a named canonical metric count."""

    metric: str
    value: int
    filter: dict
    description: str
    entity_type: str
    cited_fields: tuple[str, ...]  # fields the filter uses — for honest citation


class UnknownMetricError(ValueError):
    """Raised when ``metric`` is not declared on the descriptor."""

    def __init__(self, metric: str, available: list[str]):
        self.metric = metric
        self.available = available
        super().__init__(
            f"Unknown metric '{metric}'. Available: {', '.join(available) or '(none)'}"
        )


def aggregate(
    descriptor: EntityDescriptor,
    metric: str,
    *,
    count_fn: CountFn,
) -> AggregateResult:
    """Count records matching a named canonical metric from the descriptor.

    Always uses the descriptor's declared filter — never lets the caller
    invent filter kwargs. That is what kills the 55-vs-5 Kuwaiti inconsistency.
    """
    name = (metric or "").strip()
    metrics = descriptor.metrics or {}
    if name not in metrics:
        raise UnknownMetricError(name, sorted(metrics.keys()))

    mdef = metrics[name]
    filters = dict(mdef.filter or {})
    value = int(count_fn(descriptor.model, filters))
    cited = tuple(sorted(filters.keys()))
    return AggregateResult(
        metric=name,
        value=value,
        filter=filters,
        description=mdef.description or "",
        entity_type=descriptor.name,
        cited_fields=cited,
    )
