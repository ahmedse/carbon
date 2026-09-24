"""Bare catalog tool names must execute as call_host_api (chart path)."""
from __future__ import annotations


def test_coerce_analyze_employees_to_call_host_api():
    from ai.engine.cognition.turn.execute import coerce_bare_catalog_tool

    cfg = {
        "api_catalog": [
            {"name": "analyze_employees", "method": "GET"},
            {"name": "list_employees", "method": "GET"},
        ]
    }
    name, args = coerce_bare_catalog_tool(
        "analyze_employees",
        {"dimension": "nationality", "explanation": "GOFSCO mix"},
        cfg,
    )
    assert name == "call_host_api"
    assert args["api_name"] == "analyze_employees"
    assert args["query_params"] == {"dimension": "nationality"}
    assert args["explanation"] == "GOFSCO mix"


def test_coerce_preserves_nested_query_params():
    from ai.engine.cognition.turn.execute import coerce_bare_catalog_tool

    cfg = {"api_catalog": [{"name": "list_employees", "method": "GET"}]}
    name, args = coerce_bare_catalog_tool(
        "list_employees",
        {"query_params": {"is_active": True}, "page_size": 50},
        cfg,
    )
    assert name == "call_host_api"
    assert args["api_name"] == "list_employees"
    assert args["query_params"]["is_active"] is True
    assert args["query_params"]["page_size"] == 50


def test_coerce_leaves_real_tools_alone():
    from ai.engine.cognition.turn.execute import coerce_bare_catalog_tool

    cfg = {"api_catalog": [{"name": "analyze_employees", "method": "GET"}]}
    name, args = coerce_bare_catalog_tool(
        "aggregate_entity",
        {"entity_type": "employee", "metric": "headcount"},
        cfg,
    )
    assert name == "aggregate_entity"
    assert args == {"entity_type": "employee", "metric": "headcount"}


def test_coerce_call_host_api_passthrough():
    from ai.engine.cognition.turn.execute import coerce_bare_catalog_tool

    cfg = {"api_catalog": [{"name": "analyze_employees", "method": "GET"}]}
    name, args = coerce_bare_catalog_tool(
        "call_host_api",
        {"api_name": "analyze_employees", "query_params": {"dimension": "gender"}},
        cfg,
    )
    assert name == "call_host_api"
    assert args["api_name"] == "analyze_employees"
