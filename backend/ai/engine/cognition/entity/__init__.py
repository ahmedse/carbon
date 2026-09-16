"""Entity Capability Framework — public surface."""
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
    "EntityDescriptor",
    "LabelSource",
    "MaskPolicy",
    "MetricDef",
    "SearchField",
    "get_descriptor",
    "load_descriptors",
]
