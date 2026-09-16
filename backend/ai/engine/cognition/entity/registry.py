"""Entity Capability Framework — descriptor registry.

This is the single source of truth for per-entity knowledge used by the
generic resolve/search/get/aggregate verbs. The engine module contains
only the algorithm; all domain-specific knowledge arrives here as pure data
loaded from instance_config (ADR-0017) or ai/domain/* plugins (ADR-0016).

RULE_20: this file NEVER imports Django models or people/mdm/accounts apps.
Model paths are strings; resolution happens in the host layer (host_executor).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Descriptor schema ───────────────────────────────────────────────

@dataclass(frozen=True)
class SearchField:
    field: str
    lang: str              # "en" | "ar" | "any"
    weight: float = 1.0
    normalize: str | None = None   # "arabic" | None


@dataclass(frozen=True)
class LabelSource:
    model: str    # dotted Django model path e.g. "people.models.Position"
    field: str    # field name on the related model e.g. "title"


@dataclass(frozen=True)
class MaskPolicy:
    capability: str   # CBAC capability key; "hidden" returned when caller lacks it


@dataclass(frozen=True)
class MetricDef:
    filter: dict       # ORM kwargs for a count() query e.g. {"is_active": True}
    description: str = ""


@dataclass
class EntityDescriptor:
    name: str                                # "employee"
    model: str                               # "people.models.Employee"
    identifiers: list[str] = field(default_factory=list)    # ["id","employee_no","civil_id"]
    search_fields: list[SearchField] = field(default_factory=list)
    label_map: dict[str, LabelSource] = field(default_factory=dict)
    masking: dict[str, MaskPolicy] = field(default_factory=dict)
    metrics: dict[str, MetricDef] = field(default_factory=dict)
    scope_lookup: str | None = None          # e.g. "org_unit_id__in" for RULE_12 scoping


# ── Loader ────────────────────────────────────────────────────────────────────────

def _parse_search_field(raw: dict) -> SearchField:
    return SearchField(
        field=raw["field"],
        lang=raw.get("lang", "any"),
        weight=float(raw.get("weight", 1.0)),
        normalize=raw.get("normalize"),
    )


def _parse_label_source(raw: dict) -> LabelSource:
    return LabelSource(model=raw["model"], field=raw["field"])


def _parse_mask_policy(raw: dict) -> MaskPolicy:
    return MaskPolicy(capability=raw["capability"])


def _parse_metric_def(raw: dict) -> MetricDef:
    return MetricDef(
        filter=raw.get("filter", {}),
        description=raw.get("description", ""),
    )


def load_descriptors(instance_config: dict) -> dict[str, EntityDescriptor]:
    """Load all entity descriptors from instance_config['entities'] list.

    Returns a mapping of entity name → EntityDescriptor. Returns {} if no
    entities block is declared (graceful degradation).
    """
    raw_list = (instance_config or {}).get("entities") or []
    result: dict[str, EntityDescriptor] = {}
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        model = raw.get("model")
        if not name or not model:
            continue

        search_fields = [
            _parse_search_field(sf) for sf in (raw.get("search_fields") or [])
            if isinstance(sf, dict) and sf.get("field")
        ]
        label_map = {
            k: _parse_label_source(v)
            for k, v in (raw.get("label_map") or {}).items()
            if isinstance(v, dict)
        }
        masking = {
            k: _parse_mask_policy(v)
            for k, v in (raw.get("masking") or {}).items()
            if isinstance(v, dict)
        }
        metrics = {
            k: _parse_metric_def(v)
            for k, v in (raw.get("metrics") or {}).items()
            if isinstance(v, dict)
        }

        result[name] = EntityDescriptor(
            name=name,
            model=model,
            identifiers=list(raw.get("identifiers") or []),
            search_fields=search_fields,
            label_map=label_map,
            masking=masking,
            metrics=metrics,
            scope_lookup=raw.get("scope_lookup"),
        )
    return result


def get_descriptor(instance_config: dict, entity_type: str) -> EntityDescriptor | None:
    """Return the descriptor for a named entity, or None if not registered."""
    return load_descriptors(instance_config).get(entity_type)
