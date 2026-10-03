"""Tests for the content-engine knowledge graph (additive, default-OFF).

Uses a small inline sample of real-shaped bank rows (the exact keys the
``domain_packs/aast-med/bank/course-meat-13`` rows carry). No repo bank file
is required, so the test is hermetic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.content_engine.graph import (
    Graph,
    GraphError,
    ProvenanceError,
    build_course_graph,
    build_from_bank_rows,
    extract_concepts,
    is_passage_ref,
    passages_from_rows,
)

_AI_ROOT = Path(__file__).resolve().parents[2]
_SHORT = "TST101"

# Real-shaped bank rows: section rows (no activity id), page/book rows with
# the ``course:kind:cmid`` ref style, and a URL label row that must be
# filtered out of concept extraction.
_SAMPLE_ROWS = [
    {
        "course": _SHORT,
        "sectionnum": 0,
        "section": "Introduction to Immunity",
        "visible": True,
        "kind": "section",
        "name": "Section 0",
        "ref": "section:0",
        "text": "Course overview.",
    },
    {
        "course": _SHORT,
        "sectionnum": 0,
        "section": "Introduction to Immunity",
        "kind": "page",
        "name": "Innate Immunity Overview",
        "ref": "page:1558",
        "text": (
            "Innate Immunity responds to Pathogen Associated patterns. "
            "Viral Replication is a prerequisite for Host Range. "
            "Innate Immunity is fast and non specific."
        ),
    },
    {
        "course": _SHORT,
        "sectionnum": 0,
        "section": "Introduction to Immunity",
        "kind": "book",
        "name": "Immunology Chapter 1",
        "ref": "book:20",
        "text": "Adaptive Immunity develops later and remembers Host Range.",
    },
    {
        "course": _SHORT,
        "sectionnum": 1,
        "section": "Applied Immunology",
        "kind": "page",
        "name": "Vaccination",
        "ref": "page:2001",
        "text": "Vaccination trains Adaptive Immunity against Pathogen Associated patterns.",
    },
    {
        "course": _SHORT,
        "sectionnum": 1,
        "section": "Applied Immunology",
        "kind": "label",
        "name": "https://youtu.be/abc",
        "ref": "label:2002",
        "text": "https://youtu.be/abc",
    },
]


def _graph() -> Graph:
    return build_from_bank_rows(_SHORT, _SAMPLE_ROWS)


def _concept_id(slug: str) -> str:
    return f"{_SHORT}:concept:{slug}"


# -- model + provenance contract -------------------------------------------


def test_passage_ref_shape():
    assert is_passage_ref("TST101:page:1558") is True
    assert is_passage_ref("TST101:file:853:foo.pdf") is True
    assert is_passage_ref("page:1558") is False
    assert is_passage_ref("") is False
    assert is_passage_ref(None) is False


def test_node_without_provenance_is_rejected():
    with pytest.raises(ProvenanceError):
        Graph().add_node("TST101:page:1", "passage", "orphan", sources=[])


def test_edge_without_provenance_is_rejected():
    graph = Graph()
    graph.add_node("a", "concept", "A", sources=["TST101:page:1"])
    graph.add_node("b", "passage", "B", sources=["TST101:page:1"])
    with pytest.raises(ProvenanceError):
        graph.add_edge("DEFINED_IN", "a", "b", [])


def test_edge_with_non_ref_provenance_is_rejected():
    graph = Graph()
    graph.add_node("a", "concept", "A", sources=["TST101:page:1"])
    graph.add_node("b", "passage", "B", sources=["TST101:page:1"])
    with pytest.raises(ProvenanceError):
        graph.add_edge("DEFINED_IN", "a", "b", ["not-a-ref"])


def test_add_edge_with_unknown_endpoint_is_rejected():
    graph = Graph()
    graph.add_node("a", "concept", "A", sources=["TST101:page:1"])
    with pytest.raises(GraphError):
        graph.add_edge("DEFINED_IN", "a", "missing", ["TST101:page:1"])


def test_load_rejects_edge_without_provenance(tmp_path):
    path = tmp_path / "graph.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "record": "node",
                        "node_id": "a",
                        "type": "concept",
                        "label": "A",
                        "props": {},
                        "sources": ["TST101:page:1"],
                    }
                ),
                json.dumps(
                    {
                        "record": "node",
                        "node_id": "b",
                        "type": "passage",
                        "label": "B",
                        "props": {},
                        "sources": ["TST101:page:1"],
                    }
                ),
                json.dumps(
                    {
                        "record": "edge",
                        "edge_id": "e",
                        "type": "DEFINED_IN",
                        "from_id": "a",
                        "to_id": "b",
                        "confidence": 0.5,
                        "approved": False,
                        "provenance": [],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ProvenanceError):
        Graph.load(path)


# -- builders off real-shaped bank data ------------------------------------


def test_passages_from_rows_uses_real_refs_and_filters_labels():
    passages = passages_from_rows(_SHORT, _SAMPLE_ROWS)
    assert set(passages) == {
        "TST101:page:1558",
        "TST101:book:20",
        "TST101:page:2001",
        "TST101:label:2002",
    }
    assert all(is_passage_ref(pid) for pid in passages)
    assert passages["TST101:page:1558"]["sectionnum"] == 0


def test_build_creates_expected_node_types():
    graph = _graph()
    kinds = {node.type for node in graph.nodes.values()}
    assert {"course", "section", "lecture", "activity", "passage", "concept"} <= kinds
    refs = {n.node_id for n in graph.nodes.values() if n.type == "passage"}
    # Four real bank passages (the URL label is still a passage, but it never
    # becomes a concept).
    assert refs == {
        "TST101:page:1558",
        "TST101:book:20",
        "TST101:page:2001",
        "TST101:label:2002",
    }


def test_every_node_and_edge_traces_to_a_real_passage_ref():
    graph = _graph()
    graph.validate()  # raises on any provenance gap
    for node in graph.nodes.values():
        assert node.sources, node.node_id
    for edge in graph.edges.values():
        assert edge.provenance, edge.edge_id


def test_concepts_are_inferred_and_unapproved():
    graph = _graph()
    concept_ids = [n.node_id for n in graph.nodes.values() if n.type == "concept"]
    assert _concept_id("viral-replication") in concept_ids
    assert _concept_id("host-range") in concept_ids
    for node_id in concept_ids:
        node = graph.nodes[node_id]
        assert node.props["approved"] is False
        assert node.props["inferred"] is True
    inferred_types = {"DEFINED_IN", "TAUGHT_IN", "RELATED_TO", "PREREQUISITE_OF", "PRECEDES"}
    for edge in graph.edges.values():
        if edge.type in inferred_types:
            assert edge.approved is False, edge.edge_id


def test_teacher_approval_flips_inferred_flags():
    graph = _graph()
    cid = _concept_id("viral-replication")
    graph.approve_node(cid)
    assert graph.nodes[cid].props["approved"] is True
    edge_id = next(
        eid for eid, e in graph.edges.items() if e.type == "DEFINED_IN" and e.from_id == cid
    )
    graph.approve_edge(edge_id)
    assert graph.edges[edge_id].approved is True


def test_extract_concepts_is_deterministic_and_filters_urls():
    first = extract_concepts("Viral Replication supports Host Range.", "https://x/y")
    assert first == extract_concepts("Viral Replication supports Host Range.", "https://x/y")
    labels = [label for label, _ in first]
    assert "Viral Replication" in labels
    assert "Host Range" in labels


# -- queries ---------------------------------------------------------------


def test_query_passages_explaining_concept_returns_citable_refs():
    graph = _graph()
    cid = _concept_id("viral-replication")
    passages = graph.passages_explaining(cid)
    assert passages, "concept must resolve to at least one passage"
    assert all(is_passage_ref(p["node_id"]) for p in passages)
    assert all(p["props"]["text"] for p in passages)
    refs = {p["node_id"] for p in passages}
    assert "TST101:page:1558" in refs


def test_query_prerequisites_returns_inferred_source_concept():
    graph = _graph()
    target = _concept_id("host-range")
    prereqs = graph.prerequisites(target)
    assert prereqs, "explicit prerequisite marker must produce a PREREQUISITE_OF edge"
    assert all(p["type"] == "concept" for p in prereqs)
    assert _concept_id("viral-replication") in {p["node_id"] for p in prereqs}


def test_query_passages_under_section_and_lecture():
    graph = _graph()
    section_id = f"{_SHORT}:section:0"
    under = graph.passages_under(section_id)
    refs = {p["node_id"] for p in under}
    assert {"TST101:page:1558", "TST101:book:20"} <= refs
    assert "TST101:page:2001" not in refs
    lecture_id = next(
        n.node_id for n in graph.nodes.values() if n.type == "lecture" and ":0:" in n.node_id
    )
    assert {p["node_id"] for p in graph.passages_under(lecture_id)} >= refs


def test_query_passages_under_missing_node_is_empty():
    assert _graph().passages_under("TST101:section:does-not-exist") == []


# -- staff-tool queries (L-G G1) -------------------------------------------


def test_staff_explain_passage_returns_provenance_bearing_rows():
    graph = _graph()
    explained = graph.explain_passage("TST101:page:1558")
    assert explained["passage_id"] == "TST101:page:1558"
    assert explained["provenance"]
    assert explained["concepts"], "passage must expose the concepts it defines"
    for concept in explained["concepts"]:
        assert concept["type"] == "concept"
        assert is_passage_ref(concept["passage_id"])
    for container in explained["containers"]:
        assert is_passage_ref(container["passage_id"])
    # A non-passage ref is refused rather than guessed.
    assert graph.explain_passage("TST101:section:0") == {}
    assert graph.explain_passage("missing") == {}


def test_staff_lectures_teaching_returns_passage_ids():
    graph = _graph()
    rows = graph.lectures_teaching(_concept_id("viral-replication"))
    assert rows, "a defined concept must resolve to the lecture that teaches it"
    for row in rows:
        assert row["type"] == "lecture"
        assert is_passage_ref(row["passage_id"])
        assert row["provenance"]
    # Unknown concept -> empty, never invented.
    assert graph.lectures_teaching("TST101:concept:not-a-concept") == []


def test_staff_precedes_and_related_carry_passage_ids():
    graph = _graph()
    starts = {e.from_id for e in graph.edges.values() if e.type == "PRECEDES"}
    assert starts, "registration order must produce PRECEDES edges"
    successor_ids = set()
    for start in starts:
        successors = graph.precedes(start)
        assert successors, start
        for row in successors:
            assert is_passage_ref(row["passage_id"])
            successor_ids.add(row["node_id"])
    assert successor_ids
    related = graph.related(_concept_id("viral-replication"))
    assert related, "co-occurring concepts must be RELATED_TO"
    for row in related:
        assert row["type"] == "concept"
        assert is_passage_ref(row["passage_id"])


def test_prerequisites_rows_also_carry_passage_ids():
    graph = _graph()
    rows = graph.prerequisites(_concept_id("host-range"))
    assert rows
    for row in rows:
        assert row["type"] == "concept"
        assert is_passage_ref(row["passage_id"])


def test_staff_queries_are_not_imported_by_engine():
    """The G1 helpers stay additive; no turn path may consume the graph."""
    engine_root = _AI_ROOT / "engine"
    offenders = [
        str(p.relative_to(_AI_ROOT))
        for p in sorted(engine_root.rglob("*.py"))
        if "content_engine" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders


# -- storage ---------------------------------------------------------------


def test_jsonl_round_trip(tmp_path):
    graph = _graph()
    path = tmp_path / "nested" / "graph.jsonl"
    written = graph.save(path)
    assert written.is_file()
    reloaded = Graph.load(path)
    assert reloaded.stats() == graph.stats()
    assert {k: v.to_dict() for k, v in reloaded.nodes.items()} == {
        k: v.to_dict() for k, v in graph.nodes.items()
    }
    assert {k: v.to_dict() for k, v in reloaded.edges.items()} == {
        k: v.to_dict() for k, v in graph.edges.items()
    }


def test_load_missing_file_is_empty(tmp_path):
    graph = Graph.load(tmp_path / "absent.jsonl")
    assert graph.stats() == {"nodes": 0, "edges": 0}


def test_explicit_empty_passages_builds_empty_graph():
    graph = build_course_graph(_SHORT, [])
    assert graph.stats() == {"nodes": 0, "edges": 0}


# -- additive, default-OFF -------------------------------------------------


def test_no_turn_path_imports_graph():
    """The graph is a side index; no engine turn path may import it."""
    engine_root = _AI_ROOT / "engine"
    offenders = [
        str(p.relative_to(_AI_ROOT))
        for p in sorted(engine_root.rglob("*.py"))
        if "content_engine" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders
