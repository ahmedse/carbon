"""F3-B — read-only, outcome-language ``tool_trace`` for the "Considered…" pill.

Covers ``_build_tool_trace`` in isolation (no DB, no Django TestCase):
  * static outcome copy per tool name (``_TOOL_STEP_LABELS``)
  * ``call_host_api*`` → "Queried live platform data"
  * result ``summary`` / ``label`` overrides the static map
  * error / ``requires_confirmation`` tools are dropped
  * multi-step (>=2) gating
  * ``duration_ms`` derived from ``latency_ms`` (int, absent → 0)
  * never raises on malformed results
"""
from __future__ import annotations

import json

from ai.engine_runtime import _build_tool_trace


def _tool(name, result=None, error=None, latency_ms=12):
    item = {"tool_name": name}
    if latency_ms is not None:
        item["latency_ms"] = latency_ms
    if error is not None:
        item["error"] = error
    if result is not None:
        item["result"] = result
    return item


def test_static_label_and_ids():
    tools = [
        _tool("search_knowledge", result=json.dumps({"results": [1]})),
        _tool("get_entity_details", result=json.dumps({"entity": "x"})),
    ]
    trace = _build_tool_trace(tools)
    assert len(trace) == 2
    assert trace[0] == {
        "step_label": "Searched the knowledge base",
        "tool_id": "search_knowledge",
        "duration_ms": 12,
    }
    assert trace[1]["step_label"] == "Looked up entity details"


def test_call_host_api_label():
    tools = [
        _tool("call_host_api:list_emission_factors", result=json.dumps({"rows": []})),
        _tool("search_knowledge", result=json.dumps({"results": []})),
    ]
    trace = _build_tool_trace(tools)
    assert trace[0]["step_label"] == "Queried live platform data"
    assert trace[0]["tool_id"] == "call_host_api:list_emission_factors"


def test_result_summary_overrides_static_map():
    tools = [
        _tool("search_knowledge", result=json.dumps({"summary": "Found 3 matching factors"})),
        _tool("get_entity_details", result=json.dumps({})),
    ]
    trace = _build_tool_trace(tools)
    assert trace[0]["step_label"] == "Found 3 matching factors"


def test_result_label_used_when_no_summary():
    tools = [
        _tool("search_knowledge", result=json.dumps({"label": "Rule ABC-123"})),
        _tool("get_entity_details", result=json.dumps({})),
    ]
    trace = _build_tool_trace(tools)
    assert trace[0]["step_label"] == "Rule ABC-123"


def test_drops_error_and_confirmation_tools():
    tools = [
        _tool("search_knowledge", result=json.dumps({"results": []})),
        _tool("learn_fact", error="boom"),
        _tool("forget_fact", result=json.dumps({"requires_confirmation": True, "execution_id": "x"})),
        _tool("get_entity_details", result=json.dumps({"entity": "e"})),
    ]
    trace = _build_tool_trace(tools)
    assert [s["tool_id"] for s in trace] == ["search_knowledge", "get_entity_details"]


def test_single_tool_returns_empty():
    assert _build_tool_trace([_tool("search_knowledge", result="{}")]) == []


def test_two_valid_tools_returns_two_elements():
    tools = [
        _tool("search_knowledge", result="{}"),
        _tool("learn_fact", result="{}"),
    ]
    assert len(_build_tool_trace(tools)) == 2


def test_duration_ms_int_conversion_and_absent():
    tools = [
        _tool("search_knowledge", result="{}", latency_ms="8"),
        _tool("learn_fact", result="{}", latency_ms=None),  # latency_ms absent → 0
    ]
    trace = _build_tool_trace(tools)
    assert trace[0]["duration_ms"] == 8
    assert trace[1]["duration_ms"] == 0


def test_never_raises_on_malformed_result():
    tools = [
        _tool("search_knowledge", result="not-json{{{", latency_ms=5),
        _tool("learn_fact", result="{}", latency_ms=6),
    ]
    trace = _build_tool_trace(tools)
    assert trace[0] == {
        "step_label": "Searched the knowledge base",
        "tool_id": "search_knowledge",
        "duration_ms": 5,
    }
