"""F3-B + S-TRACE-01 — read-only, outcome-language ``tool_trace`` for the
"Considered…" / "Why this answer" surface.

Covers ``_build_tool_trace`` in isolation (no DB, no Django TestCase):
  * static outcome copy per tool name (``_TOOL_STEP_LABELS``)
  * ``call_host_api*`` → "Queried live platform data"
  * result ``summary`` / ``label`` overrides the static map
  * error / ``requires_confirmation`` tools are dropped
  * S-TRACE-01: ``tool``, ``input``, ``output``, ``confidence`` per step
  * single-tool turns now emit a trace (S-TRACE-01 — multi-step gate removed)
  * ``duration_ms`` derived from ``latency_ms`` (int, absent → 0)
  * never raises on malformed results
"""
from __future__ import annotations

import json

from ai.engine_runtime import _build_tool_trace


def _tool(name, result=None, error=None, latency_ms=12, tool_args=None):
    item = {"tool_name": name}
    if latency_ms is not None:
        item["latency_ms"] = latency_ms
    if error is not None:
        item["error"] = error
    if result is not None:
        item["result"] = result
    if tool_args is not None:
        item["tool_args"] = tool_args
    return item


def test_static_label_and_ids():
    tools = [
        _tool("search_knowledge", result=json.dumps({"results": [1]})),
        _tool("get_entity_details", result=json.dumps({"entity": "x"})),
    ]
    trace = _build_tool_trace(tools)
    assert len(trace) == 2
    assert trace[0]["step_label"] == "Searched the knowledge base"
    assert trace[0]["tool_id"] == "search_knowledge"
    assert trace[0]["tool"] == "search_knowledge"
    assert trace[0]["duration_ms"] == 12
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


def test_single_tool_emits_trace():
    # S-TRACE-01: a single-tool turn still carries a trace entry.
    trace = _build_tool_trace([_tool("search_knowledge", result="{}")])
    assert len(trace) == 1
    assert trace[0]["tool"] == "search_knowledge"


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
    assert trace[0]["step_label"] == "Searched the knowledge base"
    assert trace[0]["tool_id"] == "search_knowledge"
    assert trace[0]["duration_ms"] == 5


def test_trace_carries_input_output_confidence():
    tools = [
        _tool(
            "search_knowledge",
            result=json.dumps({"entities": [{"name": "Payroll Run Lifecycle"}], "count": 1}),
            tool_args={"query": "payroll run lifecycle"},
        ),
    ]
    trace = _build_tool_trace(tools)
    step = trace[0]
    assert step["tool"] == "search_knowledge"
    assert step["input"] == "payroll run lifecycle"
    assert step["output"] == "Found 1 match(es)"
    assert step["confidence"] == "high"


def test_output_summary_count_shape():
    # count-only shape (no results/rows key) → generic item count.
    trace = _build_tool_trace([
        _tool("call_host_api:list_payroll_runs", result=json.dumps({"count": 4})),
    ])
    assert trace[0]["output"] == "Returned 4 item(s)"
    assert trace[0]["confidence"] == "high"


def test_output_summary_rows_shape():
    trace = _build_tool_trace([
        _tool(
            "call_host_api:list_payroll_runs",
            result=json.dumps({"count": 2, "results": [{"id": 1}, {"id": 2}]}),
        ),
    ])
    assert trace[0]["output"] == "Returned 2 row(s)"


def test_empty_result_low_confidence():
    trace = _build_tool_trace([
        _tool("search_knowledge", result=json.dumps({"entities": [], "count": 0})),
    ])
    assert trace[0]["confidence"] == "low"


def test_input_summary_falls_back_to_kv():
    trace = _build_tool_trace([
        _tool(
            "call_host_api:list_employees",
            result=json.dumps({"count": 10}),
            tool_args={"limit": 50, "offset": 0},
        ),
    ])
    assert trace[0]["input"] == "limit=50, offset=0"


def test_input_summary_empty_when_no_args():
    trace = _build_tool_trace([
        _tool("search_knowledge", result=json.dumps({"count": 1})),
    ])
    assert trace[0]["input"] == ""
