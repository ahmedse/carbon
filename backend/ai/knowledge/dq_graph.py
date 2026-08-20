"""
DQ knowledge-graph read projection (Phase 24 Phase B).

A **read-only projection** over the existing foreign keys — no new database
tables, no new Django apps (ADR-0008). It models the DQ subgraph as:

    DataTable → DataField → DQRule (via RuleFieldAssignment)
    DataTable → Module → OrgUnit
    DataTable → AssetProfile → DataDomain
    DataTable ↔ DataTable (via TableRelation lineage)

This answers the "what relates to what" questions the DQ coworker needs:

* **rule reuse**  — ``rules_for_field`` / ``fields_for_rule``
* **gap analysis** — ``field_gaps`` (delegates to ``dq.services``)
* **lineage**      — ``table_lineage``
* **similarity**   — ``similar_fields`` (deterministic same-type baseline;
  richer retrieval is Phase C)
* **graph view**   — ``build_dq_graph`` node/edge envelope

Imports are downward-only (``dq``, ``dataschema``, ``catalog``, ``core``,
``mdm``) — this module must never be imported by those domain apps (RULE_20).
"""

from __future__ import annotations

from django.db.models import Q

from catalog.models import AssetProfile
from dataschema.models import DataField, DataTable, TableRelation
from dq.models import RuleFieldAssignment

# ── Summaries ───────────────────────────────────────────────────────────────


def _table_summary(table: DataTable) -> dict:
    return {
        "table_id": table.id,
        "title": table.title,
        "name": table.name,
        "module_id": table.module_id,
        "version": table.version,
        "is_archived": table.is_archived,
    }


def _field_summary(field: DataField) -> dict:
    return {
        "field_id": field.id,
        "name": field.name,
        "label": field.label,
        "type": field.type,
        "data_table_id": field.data_table_id,
    }


def _rule_summary(rule) -> dict:
    d = rule.definition or {}
    return {
        "rule_id": rule.id,
        "name": rule.name or d.get("name"),
        "rule_type": rule.rule_type or d.get("type"),
        "dimension": rule.dimension,
        "severity": rule.severity,
        "is_active": rule.is_active,
    }


# ── Rule ↔ field queries ────────────────────────────────────────────────────


def rules_for_field(field_id: int) -> list[dict]:
    """Active (non-archived) rules bound to ``field_id``."""
    assignments = (
        RuleFieldAssignment.objects
        .filter(data_field_id=field_id, rule__archived=False)
        .select_related("rule")
    )
    return [_rule_summary(a.rule) for a in assignments]


def fields_for_rule(rule_id: int) -> list[dict]:
    """Fields bound to ``rule_id`` (field-level assignments only)."""
    assignments = (
        RuleFieldAssignment.objects
        .filter(rule_id=rule_id, data_field__isnull=False)
        .select_related("data_field")
    )
    return [_field_summary(a.data_field) for a in assignments]


# ── Gap analysis ────────────────────────────────────────────────────────────


def field_gaps(table_id: int) -> list[dict]:
    """Active fields on ``table_id`` with zero active rules."""
    fields = DataField.objects.filter(
        data_table_id=table_id, is_active=True, is_archived=False
    )
    covered = set(
        RuleFieldAssignment.objects.filter(
            data_table_id=table_id,
            data_field__isnull=False,
            rule__archived=False,
            rule__is_active=True,
        ).values_list("data_field_id", flat=True)
    )
    return [_field_summary(f) for f in fields if f.id not in covered]


# ── Lineage ─────────────────────────────────────────────────────────────────


def table_lineage(table_id: int) -> dict:
    """Upstream/downstream lineage for ``table_id`` via ``TableRelation``.

    Returns ``{"upstream": [...], "downstream": [...]}``. A self-relation
    (from == to) appears in both lists, which is correct.
    """
    relations = (
        TableRelation.objects
        .filter(Q(from_table_id=table_id) | Q(to_table_id=table_id))
        .select_related("from_table", "to_table", "from_field", "to_field")
    )
    upstream: list[dict] = []
    downstream: list[dict] = []
    for r in relations:
        entry = {
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
        if r.to_table_id == table_id:
            upstream.append(entry)
        if r.from_table_id == table_id:
            downstream.append(entry)
    return {"upstream": upstream, "downstream": downstream}


# ── Context (module / org_unit / domain) ────────────────────────────────────


def table_context(table_id: int) -> dict:
    """Module, org-unit and domain context for ``table_id``."""
    table = DataTable.objects.select_related("module__org_unit").filter(
        pk=table_id
    ).first()
    if table is None:
        return {}

    module = table.module
    org_unit = module.org_unit if module else None

    domain = None
    profile = (
        AssetProfile.objects.filter(data_table_id=table_id)
        .select_related("domain")
        .first()
    )
    if profile and profile.domain_id:
        domain = profile.domain

    return {
        "table_id": table_id,
        "module": {"id": module.id, "name": module.name} if module else None,
        "org_unit": (
            {"id": org_unit.id, "name": org_unit.name, "code": org_unit.code}
            if org_unit else None
        ),
        "domain": (
            {"id": domain.id, "name": domain.name, "slug": domain.slug}
            if domain else None
        ),
    }


# ── Similarity (deterministic baseline) ─────────────────────────────────────


def similar_fields(field_id: int, limit: int = 10) -> list[dict]:
    """Fields "like" ``field_id`` — same type, excluding self.

    Deterministic baseline for Phase C retrieval: same ``type`` ranks first,
    then shared name token, then name order.
    """
    source = DataField.objects.filter(pk=field_id).first()
    if source is None:
        return []

    candidates = DataField.objects.filter(
        type=source.type, is_active=True, is_archived=False
    ).exclude(pk=field_id)

    source_tokens = set(source.name.lower().split("_"))

    def score(field: DataField) -> tuple:
        shared = len(source_tokens & set(field.name.lower().split("_")))
        return (-shared, field.name.lower())

    ordered = sorted(candidates, key=score)
    results = []
    for f in ordered[:limit]:
        s = _field_summary(f)
        s["shared_name_tokens"] = len(
            source_tokens & set(f.name.lower().split("_"))
        )
        results.append(s)
    return results


# ── Graph envelope ──────────────────────────────────────────────────────────

_MAX_NODES = 1000
_MAX_EDGES = 2000


def build_dq_graph(table_id: int | None = None, *, include_lineage: bool = True) -> dict:
    """Node/edge envelope for the DQ subgraph.

    Scoped to a single table when ``table_id`` is given; otherwise projects
    every non-archived table (bounded by ``_MAX_NODES`` / ``_MAX_EDGES``).
    """
    if table_id is not None:
        return _table_subgraph(table_id, include_lineage=include_lineage)
    return _full_projection()


def _table_subgraph(table_id: int, *, include_lineage: bool) -> dict:
    tables = DataTable.objects.filter(pk=table_id)
    if not tables.exists():
        return {"nodes": [], "edges": []}

    fields = DataField.objects.filter(
        data_table_id=table_id, is_active=True, is_archived=False
    )
    assignments = (
        RuleFieldAssignment.objects
        .filter(data_table_id=table_id, rule__archived=False)
        .select_related("rule")
    )

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_rules: set[int] = set()

    for table in tables:
        nodes.append({
            "id": f"table:{table.id}",
            "label": table.title,
            "type": "table",
            "properties": _table_summary(table),
        })

    for field in fields:
        nodes.append({
            "id": f"field:{field.id}",
            "label": field.label or field.name,
            "type": "field",
            "properties": _field_summary(field),
        })
        edges.append({
            "source": f"table:{table_id}",
            "target": f"field:{field.id}",
            "relationship": "contains",
        })

    for a in assignments:
        if a.rule_id in seen_rules:
            continue
        seen_rules.add(a.rule_id)
        nodes.append({
            "id": f"rule:{a.rule_id}",
            "label": a.rule.name,
            "type": "rule",
            "properties": _rule_summary(a.rule),
        })
        target = (
            f"field:{a.data_field_id}"
            if a.data_field_id else f"table:{a.data_table_id}"
        )
        edges.append({
            "source": target,
            "target": f"rule:{a.rule_id}",
            "relationship": "enforced_by",
        })

    if include_lineage:
        lineage = table_lineage(table_id)
        neighbor_ids: set[int] = set()
        for entry in lineage["upstream"] + lineage["downstream"]:
            nid = entry["from_table_id"]
            if nid != table_id:
                neighbor_ids.add(nid)
            nid2 = entry["to_table_id"]
            if nid2 != table_id:
                neighbor_ids.add(nid2)
        neighbors = DataTable.objects.filter(pk__in=neighbor_ids)
        for neighbor in neighbors:
            nodes.append({
                "id": f"table:{neighbor.id}",
                "label": neighbor.title,
                "type": "table",
                "properties": _table_summary(neighbor),
            })
        for entry in lineage["upstream"] + lineage["downstream"]:
            edges.append({
                "source": f"table:{entry['from_table_id']}",
                "target": f"table:{entry['to_table_id']}",
                "relationship": entry["relation_type"],
                "properties": {"label": entry["label"]},
            })

    return {"nodes": nodes, "edges": edges}


def _full_projection() -> dict:
    tables = DataTable.objects.filter(is_archived=False)[:_MAX_NODES]
    table_ids = [t.id for t in tables]

    nodes: list[dict] = []
    edges: list[dict] = []

    for table in tables:
        nodes.append({
            "id": f"table:{table.id}",
            "label": table.title,
            "type": "table",
            "properties": _table_summary(table),
        })

    field_qs = DataField.objects.filter(
        data_table_id__in=table_ids, is_active=True, is_archived=False
    )
    for field in field_qs:
        nodes.append({
            "id": f"field:{field.id}",
            "label": field.label or field.name,
            "type": "field",
            "properties": _field_summary(field),
        })
        edges.append({
            "source": f"table:{field.data_table_id}",
            "target": f"field:{field.id}",
            "relationship": "contains",
        })
        if len(nodes) >= _MAX_NODES:
            break

    assignment_qs = (
        RuleFieldAssignment.objects
        .filter(data_table_id__in=table_ids, rule__archived=False)
        .select_related("rule")
    )
    seen_rules: set[int] = set()
    for a in assignment_qs:
        if a.rule_id in seen_rules:
            continue
        seen_rules.add(a.rule_id)
        nodes.append({
            "id": f"rule:{a.rule_id}",
            "label": a.rule.name,
            "type": "rule",
            "properties": _rule_summary(a.rule),
        })
        target = (
            f"field:{a.data_field_id}"
            if a.data_field_id else f"table:{a.data_table_id}"
        )
        edges.append({
            "source": target,
            "target": f"rule:{a.rule_id}",
            "relationship": "enforced_by",
        })
        if len(nodes) >= _MAX_NODES:
            break

    return {"nodes": nodes[: _MAX_NODES], "edges": edges[: _MAX_EDGES]}
