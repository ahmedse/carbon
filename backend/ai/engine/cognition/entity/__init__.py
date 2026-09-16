"""Entity Capability Framework — public surface."""
from .aggregate import AggregateResult, UnknownMetricError, aggregate
from .registry import (
    EntityDescriptor,
    LabelSource,
    MaskPolicy,
    MetricDef,
    SearchField,
    get_descriptor,
    load_descriptors,
)

__all__ = [
    "AggregateResult",
    "EntityDescriptor",
    "LabelSource",
    "MaskPolicy",
    "MetricDef",
    "SearchField",
    "UnknownMetricError",
    "aggregate",
    "get_descriptor",
    "load_descriptors",
]
