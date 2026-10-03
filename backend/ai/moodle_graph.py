"""Staff-tool read-only queries over the committed aast-med knowledge graph.

L-G G1 (``docs/pulse/aast-med/TEACHING-WAVE-SPEC.md`` §1.4): *"A read-only
staff tool answers 'which lectures teach X' over the graph, each result
returning its passage id; not on a Chat turn; no golden moves."*

This module is the staff surface for that rung. It only *reads* the committed
``domain_packs/aast-med/graph/<shortname>.jsonl`` artifact through
:class:`ai.content_engine.graph.Graph`; it writes nothing, calls no host, and
creates no store (no Neo4j, no second Postgres, no Carbon table).

Boundaries (frozen):

* Never imported by ``ai/engine/**`` or by a Chat turn — the graph stays
  additive and NOT required for teaching (CONTENT-ENGINE-SPEC §S6). A test
  locks that boundary.
* Read-only: there is no approve/apply/write path here (ADR-0046).
* Grounding: every returned row carries a real ``passage_id`` from edge
  provenance. A row without one raises instead of being surfaced; an unknown
  query or an unresolved node returns an honest empty result, never an
  invented edge.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from ai.content_engine.graph import Graph

_PACK = Path(__file__).resolve().parents[2] / "domain_packs" / "aast-med"
_GRAPH_ROOT = _PACK / "graph"

#: The frozen G1 query set (TEACHING-WAVE-SPEC §1.4: passage explain /
#: lectures-teaching / precedes / related). These are graph *operation* names
#: on :class:`~ai.content_engine.graph.Graph`, not host-domain vocabulary and
#: not a phrase table; it is the read-only dispatch allowlist for the staff
#: surface (a write method name can never be reached).
QUERY_SET = (
    "lectures_teaching",
    "explain_passage",
    "precedes",
    "related",
)


def graph_root() -> Path:
    """The committed graph root (caller-overridable in tests)."""
    return _GRAPH_ROOT


def graph_path(shortname: str, *, root: str | os.PathLike[str] | None = None) -> Path:
    base = Path(root) if root is not None else _GRAPH_ROOT
    return base / f"{str(shortname or '').strip()}.jsonl"


def load_graph(shortname: str, *, root: str | os.PathLike[str] | None = None) -> Graph:
    """Load the committed graph for one course (empty graph if absent)."""
    return Graph.load(graph_path(shortname, root=root))


def _grounded(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return *rows*, refusing to surface any row without a real passage id."""
    out: list[dict[str, Any]] = []
    for row in rows:
        passage_id = str(row.get("passage_id") or "").strip()
        if not passage_id:
            raise ValueError(f"graph result is not passage-grounded: {row.get('node_id')!r}")
        out.append(row)
    return out


def lectures_teaching(
    shortname: str, concept: str, *, root: str | os.PathLike[str] | None = None
) -> list[dict[str, Any]]:
    """Q(a): which lectures teach *concept*, each returning a passage id."""
    return _grounded(load_graph(shortname, root=root).lectures_teaching(concept))


def explain_passage(
    shortname: str, passage_ref: str, *, root: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    """Q(b): explain one passage (its concepts + containers), passage-grounded."""
    result = load_graph(shortname, root=root).explain_passage(passage_ref)
    if not result:
        return {}
    _grounded(result.get("concepts") or [])
    _grounded(result.get("containers") or [])
    if not str(result.get("passage_id") or "").strip():
        raise ValueError("passage explanation is not passage-grounded")
    return result


def precedes(
    shortname: str, node_id: str, *, root: str | os.PathLike[str] | None = None
) -> list[dict[str, Any]]:
    """Q(c): nodes that follow *node_id* along PRECEDES, each with a passage id."""
    return _grounded(load_graph(shortname, root=root).precedes(node_id))


def related(
    shortname: str, node_id: str, *, root: str | os.PathLike[str] | None = None
) -> list[dict[str, Any]]:
    """Q(d): RELATED_TO nodes for *node_id*, each with a passage id."""
    return _grounded(load_graph(shortname, root=root).related(node_id))


def run_query(
    shortname: str,
    query_name: str,
    value: str,
    *,
    root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Dispatch one G1 query. Read-only; an unknown query is refused honestly."""
    name = str(query_name or "").strip()
    name_in = str(shortname or "").strip()
    if name not in QUERY_SET:
        return {
            "ok": False,
            "error": "unknown_query",
            "shortname": name_in,
            "query": name,
            "value": str(value or ""),
            "count": 0,
            "results": [],
        }
    if name == "explain_passage":
        explained = explain_passage(name_in, str(value or ""), root=root)
        results: list[dict[str, Any]] = [explained] if explained else []
    elif name == "lectures_teaching":
        results = lectures_teaching(name_in, str(value or ""), root=root)
    elif name == "precedes":
        results = precedes(name_in, str(value or ""), root=root)
    else:
        results = related(name_in, str(value or ""), root=root)
    return {
        "ok": True,
        "shortname": name_in,
        "query": name,
        "value": str(value or ""),
        "count": len(results),
        "results": results,
    }


__all__ = [
    "QUERY_SET",
    "graph_root",
    "graph_path",
    "load_graph",
    "lectures_teaching",
    "explain_passage",
    "precedes",
    "related",
    "run_query",
]
