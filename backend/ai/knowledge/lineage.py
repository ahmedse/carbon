"""Lineage & impact read projection (Phase 24 Phase I).

DESIGN-ADAPTIVE-LEARNING-DQ-CORE.md §5B Phase I: trace "where does this
field/table flow from/to?" and "if I change X, what breaks?" — a read-only
projection over ``dataschema`` lineage + FKs, surfaced via the knowledge
graph (extends Phase B ``ai/knowledge/dq_graph.py``).

Answers:
  * ``table_lineage``   — transitive upstream/downstream over TableRelation
  * ``field_lineage``   — field-level flow (relations + implicit references)
  * ``impact_analysis`` — what breaks if I change/delete a table or field:
                          downstream consumers, inbound references, bound DQ
                          rules (field + table level), lock state.

Imports are downward-only (``dataschema``, ``dq``, ``core``) — never imported
by those domain apps (RULE_20). No models, no writes (RULE_21).
"""

from __future__ import annotations

from collections import deque
from typing import Any

from dataschema.models import DataField, DataTable, TableRelation
from dq.models import DQRule, RuleFieldAssignment

# ── Summaries ───────────────────────────────────────────────────────────────


def _table_summary(table: DataTable) -> dict:
    return {
        "table_id": table.id,
        "title": table.title,
        "name": table.name,
        "module_id": table.module_id,
        "version": table.version,
        "is_archived": table.is_archived,
        "is_locked": table.is_locked,
    }


def _field_summary(field: DataField) -> dict:
    return {
        "field_id": field.id,
        "name": field.name,
        "label": field.label,
        "type": field.type,
        "data_table_id": field.data_table_id,
        "is_active": field.is_active,
        "is_archived": field.is_archived,
    }


def _relation_entry(r: TableRelation) -> dict:
    return {
        "relation_id": r.id,
        "relation_type": r.relation_type,
        "label": r.label,
        "from_table_id": r.from_table_id,
        "from_table_name": r.from_table.name,
        "from_field_name": r.from_field.name if r.from_field_id else None,
        "to_table_id": r.to_table_id,
        "to_table_name": r.to_table.name,
        "to_field_name": r.to_field.name if r.to_field_id else None,
    }


def _rule_impact_summary(rule: DQRule) -> dict:
    d = rule.definition or {}
    return {
        "rule_id": rule.id,
        "name": rule.name or d.get("name"),
        "rule_type": rule.rule_type or d.get("type"),
        "rule_level": rule.rule_level,
        "dimension": rule.dimension,
        "severity": rule.severity,
        "is_active": rule.is_active,
    }


def _relations_from(table_id: int) -> list[TableRelation]:
    return list(
        TableRelation.objects
        .filter(from_table_id=table_id)
        .select_related("from_table", "to_table", "from_field", "to_field")
    )


def _relations_to(table_id: int) -> list[TableRelation]:
    return list(
        TableRelation.objects
        .filter(to_table_id=table_id)
        .select_related("from_table", "to_table", "from_field", "to_field")
    )


# ── Transitive lineage ──────────────────────────────────────────────────────


def _transitive_edges(start_table_id: int, direction: str) -> list[dict]:
    """Breadth-first transitive closure from ``start_table_id``.

    ``direction="downstream"`` walks from → to (tables that consume X);
    ``direction="upstream"`` walks to → from (tables that feed X).
    Each result carries the table reached, its depth, and the relation path.
    Cycles are guarded by a visited set; self-relations are skipped.
    """
    edges: list[dict[str, Any]] = []
    visited = {start_table_id}

    def _neighbors(table_id: int):
        if direction == "downstream":
            return [
                (r.to_table_id, r) for r in _relations_from(table_id)
                if r.to_table_id != table_id
            ]
        return [
            (r.from_table_id, r) for r in _relations_to(table_id)
            if r.from_table_id != table_id
        ]

    queue: deque[tuple[int, int, list[dict]]] = deque()
    for next_id, relation in _neighbors(start_table_id):
        if next_id in visited:
            continue
        visited.add(next_id)
        entry = _relation_entry(relation)
        edges.append({
            "table_id": next_id,
            "table_name": relation.to_table.name if direction == "downstream"
                          else relation.from_table.name,
            "depth": 1,
            "path": [entry],
        })
        queue.append((next_id, 2, [entry]))

    while queue:
        cur_id, depth, path = queue.popleft()
        for next_id, relation in _neighbors(cur_id):
            if next_id in visited:
                continue
            visited.add(next_id)
            entry = _relation_entry(relation)
            new_path = path + [entry]
            edges.append({
                "table_id": next_id,
                "table_name": relation.to_table.name if direction == "downstream"
                              else relation.from_table.name,
                "depth": depth,
                "path": new_path,
            })
            queue.append((next_id, depth + 1, new_path))

    edges.sort(key=lambda e: (e["depth"], e["table_name"]))
    return edges


def table_lineage(table_id: int, max_depth: int = 3) -> dict:
    """Transitive upstream/downstream lineage for ``table_id``.

    Extends Phase B ``dq_graph.table_lineage`` (direct edges only): the
    ``direct`` envelope keeps the Phase B shape while ``upstream``/
    ``downstream`` are depth-annotated transitive closures (bounded by
    ``max_depth``).
    """
    from ai.knowledge.dq_graph import table_lineage as direct_lineage

    table = DataTable.objects.filter(pk=table_id).first()
    if table is None:
        return {"error": {"code": "not_found", "detail": f"Table {table_id} not found."}}

    upstream = [e for e in _transitive_edges(table_id, "upstream") if e["depth"] <= max_depth]
    downstream = [e for e in _transitive_edges(table_id, "downstream") if e["depth"] <= max_depth]
    return {
        "table": _table_summary(table),
        "upstream": upstream,
        "downstream": downstream,
        "direct": direct_lineage(table_id),
    }


def field_lineage(field_id: int) -> dict:
    """Field-level flow: what this field feeds, is fed by, and references.

    Explicit edges come from TableRelation (from_field/to_field). Implicit
    edges come from ``DataField.reference_table`` / ``reference_set``.
    """
    field = (
        DataField.objects.select_related("data_table")
        .filter(pk=field_id).first()
    )
    if field is None:
        return {"error": {"code": "not_found", "detail": f"Field {field_id} not found."}}

    feeds: list[dict] = []
    fed_by: list[dict] = []
    for r in _relations_from(field.data_table_id):
        if r.from_field_id == field_id:
            feeds.append(_relation_entry(r))
    for r in _relations_to(field.data_table_id):
        if r.to_field_id == field_id:
            fed_by.append(_relation_entry(r))

    references: dict[str, Any] | None = None
    if field.reference_table_id:
        ref_table = DataTable.objects.filter(pk=field.reference_table_id).first()
        references = {
            "kind": "reference_table",
            "table": _table_summary(ref_table) if ref_table else None,
        }
    elif field.reference_set_id:
        references = {"kind": "reference_set", "reference_set_id": field.reference_set_id}

    return {
        "field": _field_summary(field),
        "table": _table_summary(field.data_table),
        "feeds": feeds,
        "fed_by": fed_by,
        "references": references,
    }


# ── Impact analysis (what breaks?) ──────────────────────────────────────────


def impact_analysis_table(table_id: int) -> dict:
    """What breaks if ``table_id`` is changed or deleted.

    * downstream_tables  — transitive consumers via TableRelation
    * incoming_references — DataFields on OTHER tables whose
                            ``reference_table`` points here (implicit FK)
    * rules              — active DQ rules bound to this table: field-level
                            (via its fields) and table-level assignments
    * blocked            — ``is_locked`` (change is administratively blocked)
    """
    table = DataTable.objects.select_related("module").filter(pk=table_id).first()
    if table is None:
        return {"error": {"code": "not_found", "detail": f"Table {table_id} not found."}}

    downstream = _transitive_edges(table_id, "downstream")

    incoming_refs = [
        _field_summary(f)
        for f in DataField.objects.filter(
            reference_table_id=table_id, is_archived=False
        ).select_related("data_table")
    ]

    assignments = (
        RuleFieldAssignment.objects
        .filter(data_table_id=table_id, rule__archived=False)
        .select_related("rule", "data_field")
    )
    field_rules: list[dict] = []
    table_rules: list[dict] = []
    for a in assignments:
        summary = _rule_impact_summary(a.rule)
        if a.data_field_id:
            summary["field"] = _field_summary(a.data_field)
            field_rules.append(summary)
        else:
            table_rules.append(summary)

    return {
        "kind": "table",
        "table": {
            **_table_summary(table),
            "module": {"id": table.module_id, "name": table.module.name}
            if table.module_id else None,
        },
        "blocked": table.is_locked,
        "downstream_tables": downstream,
        "incoming_references": incoming_refs,
        "rules": {"field_rules": field_rules, "table_rules": table_rules},
        "rule_count": len(field_rules) + len(table_rules),
    }


def impact_analysis_field(field_id: int) -> dict:
    """What breaks if ``field_id`` is changed or deleted.

    * rules              — DQ rules bound to this field (field-level)
    * table_rules        — table-level rules on the parent table (their
                           definitions may reference this field)
    * outgoing_relations — relations that carry this field as from_field
    * incoming_relations — relations that carry this field as to_field
    """
    field = (
        DataField.objects.select_related("data_table__module")
        .filter(pk=field_id).first()
    )
    if field is None:
        return {"error": {"code": "not_found", "detail": f"Field {field_id} not found."}}

    rules: list[dict] = []
    for a in (
        RuleFieldAssignment.objects
        .filter(data_field_id=field_id, rule__archived=False)
        .select_related("rule")
    ):
        rules.append(_rule_impact_summary(a.rule))

    table_rules: list[dict] = []
    for a in (
        RuleFieldAssignment.objects
        .filter(data_table_id=field.data_table_id, data_field__isnull=True,
                rule__archived=False)
        .select_related("rule")
    ):
        table_rules.append(_rule_impact_summary(a.rule))

    outgoing = [
        _relation_entry(r) for r in _relations_from(field.data_table_id)
        if r.from_field_id == field_id
    ]
    incoming = [
        _relation_entry(r) for r in _relations_to(field.data_table_id)
        if r.to_field_id == field_id
    ]

    return {
        "kind": "field",
        "field": _field_summary(field),
        "table": _table_summary(field.data_table),
        "rules": rules,
        "table_rules": table_rules,
        "rule_count": len(rules) + len(table_rules),
        "outgoing_relations": outgoing,
        "incoming_relations": incoming,
    }


def impact_analysis(target_id: int, kind: str = "table") -> dict:
    """Dispatcher for ``impact_analysis_table`` / ``impact_analysis_field``."""
    if kind == "field":
        return impact_analysis_field(target_id)
    return impact_analysis_table(target_id)
