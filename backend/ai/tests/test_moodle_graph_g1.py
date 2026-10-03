"""L-G G1 — staff-tool graph queries over the committed aast-med graph.

Locks the authored gold ``domain_packs/aast-med/gold/graph-g1.yaml`` and the
staff surface (``ai.moodle_graph`` + the HMAC ``MoodleGraphView``). Every
returned row must carry a REAL ``passage_id`` that resolves to a passage node in
the committed graph; an unresolved node or an unknown query is an honest empty,
never an invented edge. The graph stays additive: ``ai/engine/**`` never
references it, and there is no write path (ADR-0046).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
import yaml
from django.test import override_settings
from rest_framework.test import APIClient

from ai.content_engine.graph import is_passage_ref
from ai.moodle_graph import QUERY_SET, load_graph, run_query

_PACK = Path(__file__).resolve().parents[3] / "domain_packs" / "aast-med"
_GOLD = yaml.safe_load((_PACK / "gold" / "graph-g1.yaml").read_text(encoding="utf-8"))
_CASES = _GOLD["cases"]
_OUT = _GOLD["out_of_scope"]
_SHORT = _GOLD["shortname"]

_SECRET = "graph-g1-hmac"
_GRAPH_URL = "/carbon-api/ai/moodle/graph/"


def _graph_rows(case: dict) -> list[dict]:
    """Grounding rows the staff tool returns, flattened across the query set."""
    result = run_query(_SHORT, case["query"], case["value"])
    assert result["ok"] is True, result
    if case["query"] == "explain_passage":
        if not result["results"]:
            return []
        explained = result["results"][0]
        rows = [
            {"node_id": explained["passage_id"], "passage_id": explained["passage_id"]}
        ]
        rows += explained.get("concepts", [])
        rows += explained.get("containers", [])
        return rows
    return result["results"]


def _signed(body: bytes) -> dict[str, str]:
    ts = str(int(time.time()))
    sig = hmac.new(_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return {"HTTP_X_PULSE_TIMESTAMP": ts, "HTTP_X_PULSE_SIGNATURE": sig}


# -- gold shape ------------------------------------------------------------


def test_g1_gold_shape_and_query_set_coverage():
    assert _GOLD["query_set"] == list(QUERY_SET)
    assert len(_CASES) >= _GOLD["thresholds"]["min_cases"]
    assert {case["query"] for case in _CASES} == set(QUERY_SET)
    assert _GOLD["thresholds"]["passage_id_coverage"] == 1.0
    assert _GOLD["thresholds"]["fabricated_rows"] == 0
    for case in _CASES:
        for key in ("id", "query", "value", "expected"):
            assert case.get(key) not in (None, ""), key


@pytest.mark.parametrize("case", _CASES, ids=[case["id"] for case in _CASES])
def test_g1_gold_case_matches_committed_graph(case: dict):
    expected = {(row["node_id"], row["passage_id"]) for row in case["expected"]}
    actual_rows = _graph_rows(case)
    actual = {(row["node_id"], row["passage_id"]) for row in actual_rows}
    assert actual == expected, case["id"]
    assert len(actual_rows) == len(actual), "duplicate node ids in a result set"


def test_g1_every_returned_row_is_passage_grounded_and_real():
    graph = load_graph(_SHORT)
    passage_ids = {n.node_id for n in graph.nodes.values() if n.type == "passage"}
    checked = 0
    for case in _CASES:
        for row in _graph_rows(case):
            pid = row["passage_id"]
            assert is_passage_ref(pid), (case["id"], pid)
            # The passage id resolves to a real committed passage node with a
            # real source ref — no invented edge is surfaced.
            assert pid in passage_ids, (case["id"], pid)
            assert graph.node(pid).sources, (case["id"], pid)
            checked += 1
    assert checked >= len(_CASES)


def test_g1_out_of_scope_is_refused_or_empty_never_invented():
    for case in _OUT["unknown_query"]:
        result = run_query(_SHORT, case["query"], case["value"])
        assert result["ok"] is False, result
        assert result["error"] == "unknown_query"
        assert result["results"] == []
    for case in _OUT["unresolved_node"]:
        result = run_query(_SHORT, case["query"], case["value"])
        assert result["ok"] is True and result["count"] == 0, result
        assert result["results"] == []
    for case in _OUT["non_passage_explain"]:
        result = run_query(_SHORT, case["query"], case["value"])
        assert result["ok"] is True and result["count"] == 0, result


def test_g1_is_read_only_and_deterministic():
    before = {p.name: p.stat().st_mtime_ns for p in (_PACK / "graph").glob("*.jsonl")}
    first = run_query(_SHORT, "lectures_teaching", "NMD1103:concept:arterial-blood-pressure-what")
    second = run_query(_SHORT, "lectures_teaching", "NMD1103:concept:arterial-blood-pressure-what")
    after = {p.name: p.stat().st_mtime_ns for p in (_PACK / "graph").glob("*.jsonl")}
    assert first == second
    assert before == after, "a read-only query must not rewrite the committed graph"


def test_g1_graph_is_not_imported_by_engine():
    """The tool stays additive; no ``ai/engine/**`` module may consume it."""
    ai_root = Path(__file__).resolve().parents[1]
    engine = ai_root / "engine"
    offenders = [
        str(p.relative_to(ai_root))
        for p in sorted(engine.rglob("*.py"))
        if "moodle_graph" in p.read_text(encoding="utf-8")
        or "content_engine" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], offenders


# -- staff HMAC surface ----------------------------------------------------


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_graph_view_unsigned_is_rejected():
    client = APIClient()
    body = json.dumps({"shortname": _SHORT, "query": "lectures_teaching", "value": "x"}).encode()
    resp = client.generic("POST", _GRAPH_URL, body, content_type="application/json")
    assert resp.status_code == 401
    assert resp.json()["ok"] is False


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_graph_view_off_list_is_refused():
    client = APIClient()
    body = json.dumps({"shortname": "ZZZ999", "query": "lectures_teaching", "value": "x"}).encode()
    resp = client.generic("POST", _GRAPH_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 404
    assert resp.json()["error"] == "off_list"


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_graph_view_signed_answers_which_lectures_teach():
    client = APIClient()
    body = json.dumps(
        {
            "shortname": _SHORT,
            "query": "lectures_teaching",
            "value": "NMD1103:concept:arterial-blood-pressure-what",
        }
    ).encode()
    resp = client.generic("POST", _GRAPH_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True and data["count"] == 1
    row = data["results"][0]
    assert row["type"] == "lecture"
    assert is_passage_ref(row["passage_id"])


@pytest.mark.django_db
@override_settings(MOODLE_PULSE_HMAC_SECRET=_SECRET)
def test_graph_view_unknown_query_is_400_not_a_fake_answer():
    client = APIClient()
    body = json.dumps({"shortname": _SHORT, "query": "drop_table", "value": "x"}).encode()
    resp = client.generic("POST", _GRAPH_URL, body, content_type="application/json", **_signed(body))
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
