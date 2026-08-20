"""
DQ retrieval + context assembly (Phase 24 Phase C).

The **retrieval layer** that turns ``dq.suggest`` / ``nl_check`` from a
hardcoded prompt into a *data-driven* one.  It is a read-only projection over
the existing relational state (no new DB tables, no new Django apps — ADR-0008)
and reuses the Phase B graph projection (:mod:`ai.knowledge.dq_graph`).

Retrieval inputs (per the design doc §5 Phase C):

* **schema** — the table's active fields.
* **field profiles** — latest ``FieldProfile`` stats (null %, distinct, range,
  top values) — the structured "what is this field like" memory.
* **canonical examples** — representative rule ``definition`` payloads per rule
  type, derived from existing active rules (knowledge-as-data).
* **similar rules** — the N most-similar existing rules, for reuse/dedup.
* **similar fields** — same-type / name-token neighbours (Phase B baseline).

All retrieval is **partitioned by ``org_unit_id``** (contract §3): where
scoped candidates exist they win; otherwise we fall back to the global pool so
a fresh org is never starved of examples.

Imports are downward-only (``dq``, ``dataschema``, ``catalog``, ``core``) —
RULE_20.  This module must never be imported by those domain apps.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from dataschema.models import DataField, DataTable
from dq.models import DQRule, FieldProfile, RuleFieldAssignment

from ai.knowledge.dq_graph import similar_fields

logger = logging.getLogger(__name__)

# Rule types whose canonical examples are useful to show the LLM (the
# deterministic v1 vocabulary, matching engine_runtime._DETERMINISTIC_RULE_TYPES).
_EXAMPLE_RULE_TYPES = (
    "not_null", "unique", "allowed_values", "range", "regex",
    "reference_integrity", "threshold",
)


def _field_profile_summary(fp: FieldProfile) -> dict:
    summary: dict = {
        "field": fp.data_field.name,
        "type": fp.data_field.type,
        "null_count": fp.null_count,
        "distinct_count": fp.distinct_count,
        "completeness_pct": round(fp.completeness_pct or 0, 1),
        "uniqueness_pct": round(fp.uniqueness_pct or 0, 1),
    }
    if fp.min_value:
        summary["min"] = fp.min_value
    if fp.max_value:
        summary["max"] = fp.max_value
    if fp.mean_value is not None:
        summary["mean"] = round(fp.mean_value, 2)
    if fp.top_values:
        summary["top_values"] = fp.top_values[:3]
    return summary


def _rule_spec(rule: DQRule) -> dict:
    """A compact, serializable rule spec (definition is source of truth)."""
    definition = rule.definition or {}
    return {
        "rule_id": rule.id,
        "name": rule.name or definition.get("name"),
        "rule_type": rule.rule_type or definition.get("type"),
        "dimension": rule.dimension or definition.get("dimension"),
        "severity": rule.severity or definition.get("severity"),
        "params": definition.get("params") or rule.params or {},
    }


def _scoped_rule_assignments(org_unit_id: int | None):
    """Active (non-archived) rule assignments, optionally scoped to an org unit.

    Scoping walks the existing FK chain: rule → data_table → module → org_unit.
    """
    qs = RuleFieldAssignment.objects.filter(
        rule__archived=False, rule__is_active=True
    ).select_related("rule", "data_table__module", "data_field")
    if org_unit_id is not None:
        qs = qs.filter(data_table__module__org_unit_id=org_unit_id)
    return qs


def _latest_field_profiles(table: DataTable) -> list[dict]:
    """Latest profile per active field (most recent ``profiled_at`` wins)."""
    fields = DataField.objects.filter(
        data_table=table, is_active=True, is_archived=False
    )
    profiles = (
        FieldProfile.objects.filter(data_field__data_table=table)
        .select_related("data_field")
        .order_by("data_field_id", "-profiled_at")
    )
    latest: dict[int, FieldProfile] = {}
    for fp in profiles:
        if fp.data_field_id not in latest:
            latest[fp.data_field_id] = fp
    ordered = [latest.get(f.id) for f in fields]
    return [_field_profile_summary(fp) for fp in ordered if fp is not None]


def _similar_field_ids(table: DataTable, limit: int) -> set[int]:
    """Union of same-type / name-token neighbours for the table's fields."""
    field_ids = list(
        DataField.objects.filter(
            data_table=table, is_active=True, is_archived=False
        ).values_list("id", flat=True)
    )
    neighbours: set[int] = set()
    for fid in field_ids:
        for sf in similar_fields(fid, limit=limit):
            neighbours.add(sf["field_id"])
    return neighbours - set(field_ids)


def _similar_rules(
    table: DataTable,
    org_unit_id: int | None,
    similar_field_ids: set[int],
    limit: int,
) -> list[dict]:
    """Existing rules most relevant to ``table``: rules bound to similar
    fields first, then any in-scope rules that share a dimension."""
    out: list[dict] = []
    seen: set[int] = set()

    if similar_field_ids:
        qs = RuleFieldAssignment.objects.filter(
            rule__archived=False,
            rule__is_active=True,
            data_field_id__in=similar_field_ids,
        )
        # Partition by org unit (contract §3): similar fields in other orgs do
        # not become reuse candidates for this org's tables.
        if org_unit_id is not None:
            qs = qs.filter(data_table__module__org_unit_id=org_unit_id)
        qs = qs.select_related("rule", "data_field").order_by("-rule__updated_at")
        for a in qs[:limit]:
            if a.rule_id in seen:
                continue
            seen.add(a.rule_id)
            spec = _rule_spec(a.rule)
            spec["bound_field"] = a.data_field.name if a.data_field_id else None
            spec["bound_table_id"] = a.data_table_id
            out.append(spec)

    if len(out) < limit:
        # Fill with in-scope rules sharing any dimension of the table's fields.
        qs = _scoped_rule_assignments(org_unit_id).exclude(
            rule_id__in=seen
        ).order_by("-rule__updated_at")
        for a in qs[: limit - len(out)]:
            if a.rule_id in seen:
                continue
            seen.add(a.rule_id)
            spec = _rule_spec(a.rule)
            spec["bound_field"] = a.data_field.name if a.data_field_id else None
            spec["bound_table_id"] = a.data_table_id
            out.append(spec)

    return out


def _canonical_examples(
    org_unit_id: int | None, examples_per_type: int
) -> dict[str, list[dict]]:
    """One representative rule definition per type, grouped by ``rule_type``.

    Scoped candidates win; if a type has none in scope, fall back to global.
    """
    by_type: dict[str, list[dict]] = defaultdict(list)

    def collect(qs):
        seen: set[tuple] = set()
        for a in qs:
            spec = _rule_spec(a.rule)
            rt = spec["rule_type"]
            if rt not in _EXAMPLE_RULE_TYPES:
                continue
            if len(by_type[rt]) >= examples_per_type:
                continue
            # Dedup by (type, normalized params) so identical rules don't repeat.
            key = (rt, json_key(spec["params"]))
            if key in seen:
                continue
            seen.add(key)
            by_type[rt].append(spec)

    collect(_scoped_rule_assignments(org_unit_id).order_by("-rule__updated_at"))

    # Fall back to global for any type still lacking examples.
    missing = [t for t in _EXAMPLE_RULE_TYPES if not by_type[t]]
    if missing:
        global_qs = (
            RuleFieldAssignment.objects.filter(
                rule__archived=False, rule__is_active=True,
                rule__rule_type__in=missing,
            )
            .select_related("rule")
            .order_by("-rule__updated_at")
        )
        seen: set[tuple] = set()
        for a in global_qs:
            spec = _rule_spec(a.rule)
            rt = spec["rule_type"]
            if len(by_type[rt]) >= examples_per_type:
                continue
            key = (rt, json_key(spec["params"]))
            if key in seen:
                continue
            seen.add(key)
            by_type[rt].append(spec)

    return {k: v for k, v in by_type.items() if v}


def json_key(value) -> str:
    """Stable string key for dedup (sorted, str-coerced)."""
    import json

    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _table_scope(table: DataTable) -> tuple[int | None, str | None]:
    """Return ``(org_unit_id, app_identifier)`` for a table."""
    org_unit_id = None
    if table.module_id:
        org_unit_id = table.module.org_unit_id if table.module else None
    return org_unit_id, "carbon"


def retrieve_suggest_context(
    table_id: int, *, limit: int = 8, examples_per_type: int = 2
) -> dict:
    """Assemble the retrieval context for a ``dq.suggest`` call.

    Returns a serializable dict (all fields are JSON-safe).  Raises
    ``DataTable.DoesNotExist`` for a bad id — callers decide how to degrade.
    """
    table = DataTable.objects.select_related("module__org_unit").get(pk=table_id)
    org_unit_id, app_identifier = _table_scope(table)

    field_profiles = _latest_field_profiles(table)
    similar_ids = _similar_field_ids(table, limit)
    similar_rules = _similar_rules(table, org_unit_id, similar_ids, limit)
    canonical_examples = _canonical_examples(org_unit_id, examples_per_type)

    # Similar-field summaries (name/type) for the prompt's "find fields like this".
    similar_field_summaries = []
    if similar_ids:
        for f in DataField.objects.filter(
            id__in=similar_ids, is_active=True, is_archived=False
        )[:limit]:
            similar_field_summaries.append(
                {"name": f.name, "type": f.type, "table_id": f.data_table_id}
            )

    return {
        "table": {
            "table_id": table.id,
            "name": table.name,
            "title": table.title,
            "module_id": table.module_id,
        },
        "scope": {"org_unit_id": org_unit_id, "app_identifier": app_identifier},
        "field_profiles": field_profiles,
        "similar_fields": similar_field_summaries,
        "similar_rules": similar_rules,
        "canonical_examples": canonical_examples,
    }


def retrieve_nl_check_context(table_id: int, *, field_name: str | None = None) -> dict:
    """Assemble retrieval context for an ``nl_check`` / ``nl_rule_test`` call.

    Returns the field profile (when ``field_name`` resolves) plus similar rules
    for reuse.  Same scoping rules as ``retrieve_suggest_context``.
    """
    table = DataTable.objects.select_related("module__org_unit").get(pk=table_id)
    org_unit_id, app_identifier = _table_scope(table)

    field_profile = None
    if field_name:
        fp = (
            FieldProfile.objects.filter(
                data_field__data_table=table,
                data_field__name=field_name,
            )
            .select_related("data_field")
            .order_by("-profiled_at")
            .first()
        )
        if fp is not None:
            field_profile = _field_profile_summary(fp)

    similar_ids = _similar_field_ids(table, limit=6)
    similar_rules = _similar_rules(table, org_unit_id, similar_ids, limit=6)

    return {
        "table": {
            "table_id": table.id,
            "name": table.name,
            "title": table.title,
        },
        "scope": {"org_unit_id": org_unit_id, "app_identifier": app_identifier},
        "field_profile": field_profile,
        "similar_rules": similar_rules,
    }
