from __future__ import annotations
from ai.engine.pack_vocab import V
V("t_ecf_6_canonical_metric_aggregation_aggregate")


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
