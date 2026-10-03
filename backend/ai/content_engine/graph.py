"""Content-engine knowledge graph (additive, default-OFF).

This module is a *content* artifact. Nothing under ``ai/engine/**`` may import
it, so a teaching turn never depends on it: the graph is a side index that
readers/builders populate, and queries read back.

Design constraints (frozen):

* Nodes and edges are plain dataclasses that serialize to the frozen dict
  shape. There is no shared types module.
* Every node and every edge must trace to at least one real passage_ref
  (``course:kind:cmid[:name]``). ``add_edge`` with empty provenance raises;
  it is never stored silently. ``validate`` re-checks the whole graph.
* Storage is a single JSONL file at a caller-supplied path. No Django model,
  no migration, no second Postgres, no Neo4j.
* Builders accept plain passage dicts (``id``/``kind``/``activity_id``/
  ``sectionnum``/``name``/``text``). ``build_from_repo`` reads the pack bank
  through ``ai.moodle_bank`` (read-only) but returns the same plain shape, so
  this module never depends on another worker's reader module.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

GRAPH_VERSION = 1

NODE_TYPES = frozenset(
    {
        "course",
        "section",
        "lecture",
        "activity",
        "passage",
        "concept",
        "ilo",
        "assessment",
    }
)
EDGE_TYPES = frozenset(
    {
        "CONTAINS",
        "PART_OF",
        "PRECEDES",
        "TAUGHT_IN",
        "DEFINED_IN",
        "RELATED_TO",
        "ASSESSES",
        "PREREQUISITE_OF",
        "CITES",
    }
)

#: Edge types that are already assertable from real structure (registration,
#: containment). Concept edges stay ``approved=False`` until a teacher flips
#: them.
_STRUCTURAL_EDGE_TYPES = frozenset({"CONTAINS", "PART_OF"})

#: A passage ref has the shape ``course:kind:cmid`` or
#: ``course:kind:cmid:name``. Two colons minimum, no empty segments.
_MIN_REF_PARTS = 3


class GraphError(ValueError):
    """Base class for graph validation failures."""


class ProvenanceError(GraphError):
    """A node or edge did not trace to a real passage_ref."""


def is_passage_ref(ref: Any) -> bool:
    """True when *ref* looks like ``course:kind:cmid[:...]``."""
    if not isinstance(ref, str):
        return False
    parts = ref.split(":")
    if len(parts) < _MIN_REF_PARTS:
        return False
    return all(part.strip() for part in parts)


def _require_provenance(kind: str, refs: Iterable[str]) -> tuple[str, ...]:
    cleaned = tuple(str(ref).strip() for ref in refs if str(ref).strip())
    if not cleaned:
        raise ProvenanceError(f"{kind} has no passage_ref provenance")
    bad = [ref for ref in cleaned if not is_passage_ref(ref)]
    if bad:
        raise ProvenanceError(f"{kind} provenance is not a passage_ref: {bad!r}")
    return cleaned


@dataclass(frozen=True)
class Node:
    """One graph node. ``sources`` is mandatory provenance."""

    node_id: str
    type: str
    label: str
    props: Mapping[str, Any] = field(default_factory=dict)
    sources: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "type": self.type,
            "label": self.label,
            "props": dict(self.props),
            "sources": list(self.sources),
        }

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Node":
        return cls(
            node_id=str(row["node_id"]),
            type=str(row["type"]),
            label=str(row.get("label") or ""),
            props=dict(row.get("props") or {}),
            sources=tuple(str(s) for s in (row.get("sources") or ())),
        )


@dataclass(frozen=True)
class Edge:
    """One directed graph edge. ``provenance`` is mandatory."""

    edge_id: str
    type: str
    from_id: str
    to_id: str
    confidence: float
    approved: bool
    provenance: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "type": self.type,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "confidence": float(self.confidence),
            "approved": bool(self.approved),
            "provenance": list(self.provenance),
        }

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "Edge":
        return cls(
            edge_id=str(row["edge_id"]),
            type=str(row["type"]),
            from_id=str(row["from_id"]),
            to_id=str(row["to_id"]),
            confidence=float(row.get("confidence", 1.0)),
            approved=bool(row.get("approved", False)),
            provenance=tuple(str(p) for p in (row.get("provenance") or ())),
        )


class Graph:
    """An in-memory node/edge set with JSONL persistence.

    ``path`` is caller-supplied. The graph is additive: re-adding a node or
    edge merges provenance instead of replacing it.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}

    # -- read -------------------------------------------------------------
    @property
    def nodes(self) -> Mapping[str, Node]:
        return dict(self._nodes)

    @property
    def edges(self) -> Mapping[str, Edge]:
        return dict(self._edges)

    def node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def edge(self, edge_id: str) -> Edge | None:
        return self._edges.get(edge_id)

    def stats(self) -> dict[str, int]:
        return {"nodes": len(self._nodes), "edges": len(self._edges)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": GRAPH_VERSION,
            "nodes": [self._nodes[k].to_dict() for k in sorted(self._nodes)],
            "edges": [self._edges[k].to_dict() for k in sorted(self._edges)],
        }

    # -- write ------------------------------------------------------------
    def add_node(
        self,
        node_id: str,
        type: str,
        label: str,
        props: Mapping[str, Any] | None = None,
        sources: Sequence[str] | None = None,
    ) -> Node:
        if type not in NODE_TYPES:
            raise GraphError(f"unknown node type {type!r}")
        prov = _require_provenance(f"node {node_id!r}", sources or ())
        new_props = dict(props or {})
        existing = self._nodes.get(node_id)
        if existing is not None:
            merged_sources = tuple(sorted(set(existing.sources) | set(prov)))
            merged_props = {**existing.props, **new_props}
            node = Node(node_id, type, label or existing.label, merged_props, merged_sources)
        else:
            node = Node(node_id, type, label, new_props, prov)
        self._nodes[node_id] = node
        return node

    def add_edge(
        self,
        type: str,
        from_id: str,
        to_id: str,
        provenance: Sequence[str],
        confidence: float = 1.0,
        approved: bool | None = None,
        edge_id: str | None = None,
    ) -> Edge:
        if type not in EDGE_TYPES:
            raise GraphError(f"unknown edge type {type!r}")
        if from_id not in self._nodes:
            raise GraphError(f"edge {type} has unknown from_id {from_id!r}")
        if to_id not in self._nodes:
            raise GraphError(f"edge {type} has unknown to_id {to_id!r}")
        prov = _require_provenance(f"edge {type} {from_id}->{to_id}", provenance)
        if approved is None:
            approved = type in _STRUCTURAL_EDGE_TYPES
        eid = edge_id or f"{type}:{from_id}->{to_id}"
        existing = self._edges.get(eid)
        if existing is not None:
            merged = tuple(sorted(set(existing.provenance) | set(prov)))
            edge = Edge(
                eid,
                type,
                from_id,
                to_id,
                max(float(existing.confidence), float(confidence)),
                bool(existing.approved or approved),
                merged,
            )
        else:
            edge = Edge(eid, type, from_id, to_id, float(confidence), bool(approved), prov)
        self._edges[eid] = edge
        return edge

    def approve_node(self, node_id: str) -> Node:
        """Teacher approval flips an inferred node to ``approved=True``."""
        node = self._nodes.get(node_id)
        if node is None:
            raise GraphError(f"unknown node {node_id!r}")
        approved = Node(
            node.node_id,
            node.type,
            node.label,
            {**node.props, "approved": True},
            node.sources,
        )
        self._nodes[node_id] = approved
        return approved

    def approve_edge(self, edge_id: str) -> Edge:
        edge = self._edges.get(edge_id)
        if edge is None:
            raise GraphError(f"unknown edge {edge_id!r}")
        approved = Edge(
            edge.edge_id,
            edge.type,
            edge.from_id,
            edge.to_id,
            edge.confidence,
            True,
            edge.provenance,
        )
        self._edges[edge_id] = approved
        return approved

    # -- validation -------------------------------------------------------
    def validate(self) -> None:
        """Raise when any node/edge breaks the provenance contract."""
        for node in self._nodes.values():
            if node.type not in NODE_TYPES:
                raise GraphError(f"node {node.node_id!r} has unknown type {node.type!r}")
            _require_provenance(f"node {node.node_id!r}", node.sources)
        for edge in self._edges.values():
            if edge.type not in EDGE_TYPES:
                raise GraphError(f"edge {edge.edge_id!r} has unknown type {edge.type!r}")
            if edge.from_id not in self._nodes or edge.to_id not in self._nodes:
                raise GraphError(f"edge {edge.edge_id!r} has a dangling endpoint")
            _require_provenance(f"edge {edge.edge_id!r}", edge.provenance)

    # -- storage ----------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        """Write one JSONL record per node then edge. Round-trips with load."""
        self.validate()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for node_id in sorted(self._nodes):
            lines.append(json.dumps({"record": "node", **self._nodes[node_id].to_dict()},
                                    ensure_ascii=False))
        for edge_id in sorted(self._edges):
            lines.append(json.dumps({"record": "edge", **self._edges[edge_id].to_dict()},
                                    ensure_ascii=False))
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return out

    @classmethod
    def load(cls, path: str | Path) -> "Graph":
        graph = cls()
        source = Path(path)
        if not source.is_file():
            return graph
        for line in source.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            record = row.get("record")
            if record == "node":
                node = Node.from_dict(row)
                graph._nodes[node.node_id] = node
            elif record == "edge":
                edge = Edge.from_dict(row)
                graph._edges[edge.edge_id] = edge
            else:
                raise GraphError(f"unknown record type {record!r}")
        graph.validate()
        return graph

    # -- queries ----------------------------------------------------------
    def _edge_ids_from(self, node_id: str, types: frozenset[str]) -> list[str]:
        return [
            eid
            for eid, edge in self._edges.items()
            if edge.from_id == node_id and edge.type in types
        ]

    def _reachable_passages(self, start_id: str, follow: frozenset[str]) -> list[Node]:
        seen = {start_id}
        stack = [start_id]
        found: dict[str, Node] = {}
        while stack:
            current = stack.pop()
            for edge in self._edges.values():
                if edge.from_id != current or edge.type not in follow:
                    continue
                nxt = edge.to_id
                if nxt in seen:
                    continue
                seen.add(nxt)
                node = self._nodes[nxt]
                if node.type == "passage":
                    found[node.node_id] = node
                elif node.type in {"section", "lecture", "activity", "course", "concept"}:
                    stack.append(nxt)
        return [found[key] for key in sorted(found)]

    def passages_explaining(self, concept_id: str) -> list[dict[str, Any]]:
        """Q(a): passages that explain a concept, as citable dicts."""
        # CONTAINS is traversed downward only; PART_OF is not followed because
        # it would climb to a broader container and leak sibling sections.
        return [
            node.to_dict()
            for node in self._reachable_passages(
                concept_id, frozenset({"DEFINED_IN", "TAUGHT_IN", "CONTAINS"})
            )
        ]

    def prerequisites(self, concept_id: str) -> list[dict[str, Any]]:
        """Q(b): concepts that are a prerequisite of *concept_id*.

        Each row keeps the node shape and adds ``passage_id`` /
        ``provenance`` so a staff tool can cite the graph answer.
        """
        out: dict[str, dict[str, Any]] = {}
        for edge in self._edges.values():
            if edge.type != "PREREQUISITE_OF" or edge.to_id != concept_id:
                continue
            node = self._nodes.get(edge.from_id)
            if node is not None:
                row = node.to_dict()
                row["passage_id"] = edge.provenance[0] if edge.provenance else ""
                row["provenance"] = list(edge.provenance)
                out[node.node_id] = row
        return [out[key] for key in sorted(out)]

    def passages_under(self, node_id: str) -> list[dict[str, Any]]:
        """Q(c): all passages under a section/lecture/activity/course."""
        node = self._nodes.get(node_id)
        if node is not None and node.type == "passage":
            return [node.to_dict()]
        return [
            found.to_dict()
            for found in self._reachable_passages(node_id, frozenset({"CONTAINS"}))
        ]

    # -- staff-tool queries (L-G G1) --------------------------------------
    #: Additive read-only helpers for staff tools. No door/Chat path imports
    #: them, so the graph stays NOT required for teaching (CONTENT-ENGINE-SPEC
    #: §S6). Every row carries a real ``passage_id`` from edge provenance.

    def _find_node(self, value: Any, node_type: str | None = None) -> Node | None:
        """Resolve a node by exact id, then by slug of its label."""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        node = self._nodes.get(text)
        if node is not None and (node_type is None or node.type == node_type):
            return node
        wanted = slugify(text)
        for candidate in self._nodes.values():
            if node_type is not None and candidate.type != node_type:
                continue
            if slugify(candidate.label) == wanted:
                return candidate
        return None

    @staticmethod
    def _staff_row(node: Node, provenance: Sequence[str]) -> dict[str, Any]:
        cleaned = [str(p) for p in provenance if str(p).strip()]
        return {
            "node_id": node.node_id,
            "type": node.type,
            "label": node.label,
            "passage_id": cleaned[0] if cleaned else "",
            "provenance": cleaned,
        }

    def explain_passage(self, passage_ref: str) -> dict[str, Any]:
        """Q: explain one passage — the concepts it defines and its containers.

        Returns ``{}`` when the ref is not a passage node. Concepts and
        containers each carry the provenance (hence a real passage id) of the
        edge that grounds them.
        """
        node = self._find_node(passage_ref, "passage")
        if node is None:
            return {}
        concepts: dict[str, dict[str, Any]] = {}
        containers: dict[str, dict[str, Any]] = {}
        for edge in self._edges.values():
            if edge.type == "DEFINED_IN" and edge.to_id == node.node_id:
                other = self._nodes.get(edge.from_id)
                if other is not None:
                    concepts[other.node_id] = self._staff_row(other, edge.provenance)
            elif edge.type == "CONTAINS" and edge.to_id == node.node_id:
                other = self._nodes.get(edge.from_id)
                if other is not None:
                    containers[other.node_id] = self._staff_row(other, edge.provenance)
        return {
            "passage_id": node.node_id,
            "label": node.label,
            "provenance": list(node.sources),
            "concepts": [concepts[key] for key in sorted(concepts)],
            "containers": [containers[key] for key in sorted(containers)],
        }

    def lectures_teaching(self, concept: str) -> list[dict[str, Any]]:
        """Q: which lectures teach *concept*, each result returning a passage id."""
        node = self._find_node(concept, "concept")
        if node is None:
            return []
        rows: dict[str, dict[str, Any]] = {}
        for edge in self._edges.values():
            if edge.type != "TAUGHT_IN" or edge.from_id != node.node_id:
                continue
            lecture = self._nodes.get(edge.to_id)
            if lecture is not None:
                rows[lecture.node_id] = self._staff_row(lecture, edge.provenance)
        return [rows[key] for key in sorted(rows)]

    def precedes(self, node_id: str) -> list[dict[str, Any]]:
        """Q: the nodes that follow *node_id* along PRECEDES (successors)."""
        rows: dict[str, dict[str, Any]] = {}
        for edge in self._edges.values():
            if edge.type != "PRECEDES" or edge.from_id != node_id:
                continue
            other = self._nodes.get(edge.to_id)
            if other is not None:
                rows[other.node_id] = self._staff_row(other, edge.provenance)
        return [rows[key] for key in sorted(rows)]

    def related(self, node_id: str) -> list[dict[str, Any]]:
        """Q: nodes RELATED_TO *node_id* (either direction), each with a passage id."""
        rows: dict[str, dict[str, Any]] = {}
        for edge in self._edges.values():
            if edge.type != "RELATED_TO":
                continue
            if edge.from_id == node_id:
                other = self._nodes.get(edge.to_id)
            elif edge.to_id == node_id:
                other = self._nodes.get(edge.from_id)
            else:
                continue
            if other is not None:
                rows[other.node_id] = self._staff_row(other, edge.provenance)
        return [rows[key] for key in sorted(rows)]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

_CONCEPT_RE = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3})\b")
_PREREQ_RE = re.compile(
    r"\b(?:prerequisite|pre-requisite|pre\s?requisite|required\s+before)\b",
    re.IGNORECASE,
)
_URLISH_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_HEAD_STOPWORDS = frozenset(
    {
        "section",
        "week",
        "part",
        "figure",
        "table",
        "video",
        "handout",
        "slide",
        "lecture",
        "chapter",
        "page",
        "unit",
        "module",
        "course",
        "clinical",
    }
)
_CONCEPT_KINDS = frozenset({"page", "label", "book", "file", "url", "google", "youtube", "extra"})

_CONFIDENCE = {
    "CONTAINS": 1.0,
    "PART_OF": 1.0,
    "PRECEDES": 0.6,
    "TAUGHT_IN": 0.4,
    "DEFINED_IN": 0.5,
    "RELATED_TO": 0.3,
    "PREREQUISITE_OF": 0.3,
}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _activity_from_row(row: Mapping[str, Any]) -> int | None:
    if row.get("cmid"):
        try:
            return int(row["cmid"])
        except (TypeError, ValueError):
            return None
    ref = str(row.get("ref") or "")
    _, _, tail = ref.partition(":")
    if tail.isdigit():
        return int(tail)
    return None


def passages_from_rows(shortname: str, rows: Iterable[Mapping[str, Any]]) -> dict[str, dict]:
    """Real meat rows -> passage dicts (moodle_bank shape), no fabrication.

    A row without a resolvable activity id or text is skipped. Duplicate
    refs merge their text so a passage node is never split.
    """
    out: dict[str, dict] = {}
    for row in rows:
        if str(row.get("course") or shortname) != shortname:
            continue
        kind = str(row.get("kind") or "")
        if kind not in _CONCEPT_KINDS:
            continue
        activity = _activity_from_row(row)
        text = str(row.get("text") or "").strip()
        if activity is None or not text:
            continue
        pid = f"{shortname}:{kind}:{activity}"
        existing = out.get(pid)
        if existing is not None:
            existing["text"] = f"{existing['text']}\n{text}"
            continue
        out[pid] = {
            "id": pid,
            "course": shortname,
            "kind": kind,
            "activity_id": activity,
            "sectionnum": int(row.get("sectionnum") or 0),
            "section": str(row.get("section") or ""),
            "name": str(row.get("name") or ""),
            "text": text,
        }
    return out


def extract_concepts(text: str, name: str = "") -> list[tuple[str, str]]:
    """Deterministic concept pass: capitalised multi-word / heading terms.

    Returns ``(label, slug)`` pairs, de-duplicated by slug, in first-seen
    order. Inferred only; the caller marks them ``approved=False``.
    """
    found: dict[str, str] = {}

    def _consider(term: str) -> None:
        label = " ".join(term.split())
        if not label or _URLISH_RE.search(label):
            return
        tokens = label.split()
        if tokens[0].lower() in _HEAD_STOPWORDS:
            return
        if len(tokens) == 1 and len(label) < 4:
            return
        slug = slugify(label)
        if slug and slug not in found:
            found[slug] = label

    clean_name = " ".join(str(name).split())
    if clean_name and not _URLISH_RE.search(clean_name) and len(clean_name.split()) <= 6:
        if not any(ch.isdigit() for ch in clean_name):
            _consider(clean_name)
    for match in _CONCEPT_RE.finditer(str(text)):
        _consider(match.group(1))
    return [(label, slug) for slug, label in found.items()]


def _choose_section_label(passages: Sequence[Mapping[str, Any]], sectionnum: int) -> str:
    for passage in passages:
        title = str(passage.get("section") or "").strip()
        if title:
            return title
    return f"Section {sectionnum}"


def _choose_lecture_label(passages: Sequence[Mapping[str, Any]], fallback: str) -> str:
    for passage in passages:
        name = " ".join(str(passage.get("name") or "").split())
        if name and not _URLISH_RE.search(name):
            return name
    return fallback


def build_course_graph(
    shortname: str,
    passages: Iterable[Mapping[str, Any]],
    *,
    prerequisite_links: Sequence[Mapping[str, Any]] | None = None,
    max_concepts_per_passage: int = 8,
) -> Graph:
    """Build ``course -> section -> lecture -> activity -> passage``.

    * ``passages`` are plain dicts with ``id``/``kind``/``activity_id``/
      ``sectionnum`` and optional ``name``/``text``/``section``.
    * Concept nodes/edges are inferred and ``approved=False``.
    * ``prerequisite_links`` are curated ``{from, to, provenance}`` dicts.
    """
    graph = Graph()
    rows = [dict(p) for p in passages]
    if not rows:
        return graph
    rows.sort(key=lambda p: (int(p.get("sectionnum") or 0), int(p.get("activity_id") or 0), str(p.get("id"))))
    first_ref = str(rows[0]["id"])

    graph.add_node(shortname, "course", shortname, {"course": shortname}, [first_ref])

    by_section: dict[int, list[dict]] = {}
    by_activity: dict[int, list[dict]] = {}
    for row in rows:
        by_section.setdefault(int(row.get("sectionnum") or 0), []).append(row)
        by_activity.setdefault(int(row.get("activity_id") or 0), []).append(row)

    # Passages ------------------------------------------------------------
    for row in rows:
        ref = str(row["id"])
        graph.add_node(
            ref,
            "passage",
            str(row.get("name") or row.get("kind") or ref),
            {
                "course": shortname,
                "kind": str(row.get("kind") or ""),
                "activity_id": int(row.get("activity_id") or 0),
                "sectionnum": int(row.get("sectionnum") or 0),
                "name": str(row.get("name") or ""),
                "text": str(row.get("text") or ""),
            },
            [ref],
        )

    # Activities ----------------------------------------------------------
    for activity_id, activity_rows in by_activity.items():
        refs = [str(r["id"]) for r in activity_rows]
        label = _choose_lecture_label(activity_rows, f"Activity {activity_id}")
        aid = f"{shortname}:activity:{activity_id}"
        graph.add_node(aid, "activity", label, {"course": shortname, "activity_id": activity_id}, refs)

    # Sections + lectures -------------------------------------------------
    for sectionnum, section_rows in by_section.items():
        refs = [str(r["id"]) for r in section_rows]
        section_label = _choose_section_label(section_rows, sectionnum)
        sid = f"{shortname}:section:{sectionnum}"
        graph.add_node(sid, "section", section_label, {"course": shortname, "sectionnum": sectionnum}, refs)
        graph.add_edge("CONTAINS", shortname, sid, [refs[0]], _CONFIDENCE["CONTAINS"])
        graph.add_edge("PART_OF", sid, shortname, [refs[0]], _CONFIDENCE["PART_OF"])

        lecture_label = _choose_lecture_label(section_rows, section_label)
        lid = f"{shortname}:lecture:{sectionnum}:{slugify(lecture_label) or 'lecture'}"
        graph.add_node(
            lid,
            "lecture",
            lecture_label,
            {"course": shortname, "sectionnum": sectionnum},
            refs,
        )
        graph.add_edge("CONTAINS", sid, lid, [refs[0]], _CONFIDENCE["CONTAINS"])
        graph.add_edge("PART_OF", lid, sid, [refs[0]], _CONFIDENCE["PART_OF"])

        for activity_id, activity_rows in (
            (aid_num, rows_) for aid_num, rows_ in by_activity.items()
            if int(rows_[0].get("sectionnum") or 0) == sectionnum
        ):
            aid = f"{shortname}:activity:{activity_id}"
            aref = str(activity_rows[0]["id"])
            graph.add_edge("CONTAINS", lid, aid, [aref], _CONFIDENCE["CONTAINS"])
            graph.add_edge("PART_OF", aid, lid, [aref], _CONFIDENCE["PART_OF"])

    # Activity -> passage, and PRECEDES along registration order ----------
    ordered_by_lecture: dict[str, list[str]] = {}
    for activity_id, activity_rows in by_activity.items():
        aid = f"{shortname}:activity:{activity_id}"
        for row in activity_rows:
            ref = str(row["id"])
            graph.add_edge("CONTAINS", aid, ref, [ref], _CONFIDENCE["CONTAINS"])
            graph.add_edge("PART_OF", ref, aid, [ref], _CONFIDENCE["PART_OF"])
            lecture_rows = by_section[int(row.get("sectionnum") or 0)]
            lecture_label = _choose_lecture_label(lecture_rows, _choose_section_label(lecture_rows, int(row.get("sectionnum") or 0)))
            lid = f"{shortname}:lecture:{int(row.get('sectionnum') or 0)}:{slugify(lecture_label) or 'lecture'}"
            ordered_by_lecture.setdefault(lid, []).append(ref)
    for refs in ordered_by_lecture.values():
        for earlier, later in zip(refs, refs[1:]):
            graph.add_edge("PRECEDES", earlier, later, [later], _CONFIDENCE["PRECEDES"], approved=False)

    # Concepts (inferred, approved=False) ---------------------------------
    concept_nodes: dict[str, str] = {}
    concepts_by_passage: dict[str, list[str]] = {}
    for row in rows:
        ref = str(row["id"])
        concepts = extract_concepts(str(row.get("text") or ""), str(row.get("name") or ""))
        concepts = concepts[:max_concepts_per_passage]
        lecture_rows = by_section[int(row.get("sectionnum") or 0)]
        lecture_label = _choose_lecture_label(lecture_rows, _choose_section_label(lecture_rows, int(row.get("sectionnum") or 0)))
        lid = f"{shortname}:lecture:{int(row.get('sectionnum') or 0)}:{slugify(lecture_label) or 'lecture'}"
        for label, slug in concepts:
            cid = f"{shortname}:concept:{slug}"
            concept_nodes[cid] = label
            concepts_by_passage.setdefault(ref, []).append(cid)
            graph.add_node(cid, "concept", label, {"inferred": True, "approved": False}, [ref])
            graph.add_edge("DEFINED_IN", cid, ref, [ref], _CONFIDENCE["DEFINED_IN"], approved=False)
            graph.add_edge("TAUGHT_IN", cid, lid, [ref], _CONFIDENCE["TAUGHT_IN"], approved=False)
        # Co-occurrence inside one passage, inferred only.
        passage_concepts = concepts_by_passage.get(ref, [])
        for i, left in enumerate(passage_concepts):
            for right in passage_concepts[i + 1:]:
                graph.add_edge("RELATED_TO", left, right, [ref], _CONFIDENCE["RELATED_TO"], approved=False)
        # Explicit prerequisite marker -> ordered concept prerequisite edges.
        if _PREREQ_RE.search(str(row.get("text") or "")) and len(passage_concepts) >= 2:
            for i, left in enumerate(passage_concepts):
                for right in passage_concepts[i + 1:]:
                    graph.add_edge("PREREQUISITE_OF", left, right, [ref],
                                   _CONFIDENCE["PREREQUISITE_OF"], approved=False)

    # Curated prerequisite links (real provenance required by add_edge).
    for link in prerequisite_links or ():
        source = _resolve_concept(graph, link.get("from"), shortname, concept_nodes)
        target = _resolve_concept(graph, link.get("to"), shortname, concept_nodes)
        if source is None or target is None:
            continue
        graph.add_edge(
            "PREREQUISITE_OF",
            source,
            target,
            list(link.get("provenance") or ()),
            _CONFIDENCE["PREREQUISITE_OF"],
            approved=bool(link.get("approved", False)),
        )

    graph.validate()
    return graph


def _resolve_concept(
    graph: Graph, value: Any, shortname: str, known: Mapping[str, str]
) -> str | None:
    if not value:
        return None
    text = str(value)
    if text in known:
        return text
    cid = f"{shortname}:concept:{slugify(text)}"
    if graph.node(cid) is not None:
        return cid
    return None


def build_from_bank_rows(
    shortname: str,
    rows: Iterable[Mapping[str, Any]],
    *,
    prerequisite_links: Sequence[Mapping[str, Any]] | None = None,
) -> Graph:
    """Build from raw meat rows (the exact shape in ``course-meat-13``)."""
    return build_course_graph(
        shortname,
        passages_from_rows(shortname, rows).values(),
        prerequisite_links=prerequisite_links,
    )


def build_from_repo(shortname: str) -> Graph:
    """Build from the pack bank via ``ai.moodle_bank`` (read-only, lazy).

    The import is local so importing this module never pulls Django or the
    engine. No reader module is imported; loaders already return plain dicts.
    """
    from ai import moodle_bank  # local import: keeps module import graph light

    merged: dict[str, dict] = {}
    for bank in (
        moodle_bank.load_c3(shortname),
        moodle_bank.load_c4_files(shortname),
        moodle_bank.load_c4_drive(shortname),
        moodle_bank.load_c5_youtube(shortname),
    ):
        merged.update(bank)
    return build_course_graph(shortname, merged.values())
