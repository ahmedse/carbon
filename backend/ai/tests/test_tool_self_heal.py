"""Bounded, read-only self-heal on a missed tool lookup."""
from __future__ import annotations

import pytest

from ai.engine.cognition.turn.self_heal import (
    Repair,
    annotate_repair,
    is_repairable_miss,
    propose_repair,
)

CONFIG = {
    "api_catalog": [
        {"name": "get_my_leave_balance", "method": "GET"},
        {"name": "list_my_leave", "method": "GET"},
        {"name": "submit_my_leave", "method": "POST", "requires_confirmation": True},
    ],
}


# ── Miss detection ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("tool,result", [
    ("get_entity_details", {"entity": None, "message": "Entity 'x' not found"}),
    ("search_knowledge", {"status": "no_match", "count": 0}),
    ("call_host_api", {"error": "Unknown API 'leave_balance'"}),
    ("call_host_api", {"status_code": 404, "data": {}}),
])
def test_repairable_misses(tool, result):
    assert is_repairable_miss(tool, result) is True


@pytest.mark.parametrize("tool,result", [
    # Real data — never second-guessed.
    ("get_entity_details", {"entity": {"name": "employee"}}),
    # A truthfully empty list is an answer, not a miss.
    ("call_host_api", {"status_code": 200, "data": []}),
    # A real host failure belongs to recovery synthesis, not a retry.
    ("call_host_api", {"error": "connection timeout"}),
    # Mutations are out of scope entirely.
    ("learn_fact", {"entity": None}),
])
def test_non_repairable_results(tool, result):
    assert is_repairable_miss(tool, result) is False


# ── Repair proposal ──────────────────────────────────────────────────────────

def test_entity_miss_routes_to_the_live_endpoint():
    repair = propose_repair(
        "get_entity_details",
        {"entity_name": "leave_balance"},
        {"entity": None, "message": "Entity 'leave_balance' not found"},
        instance_config=CONFIG,
    )
    assert repair is not None
    assert repair.tool_name == "call_host_api"
    assert repair.tool_args["api_name"] == "get_my_leave_balance"
    assert repair.strategy == "catalog_alias"


def test_invented_api_name_routes_to_the_nearest_read():
    repair = propose_repair(
        "call_host_api",
        {"api_name": "leave_balance"},
        {"error": "Unknown API 'leave_balance'"},
        instance_config=CONFIG,
    )
    assert repair is not None
    assert repair.tool_args["api_name"] == "get_my_leave_balance"


def test_repair_never_targets_a_mutation():
    # "submit_leave" is closest to the POST endpoint — it must NOT be proposed.
    repair = propose_repair(
        "call_host_api",
        {"api_name": "submit_leave"},
        {"error": "Unknown API 'submit_leave'"},
        instance_config=CONFIG,
    )
    assert repair is None or repair.tool_args["api_name"] != "submit_my_leave"


def test_no_repair_when_the_tool_found_data():
    assert propose_repair(
        "get_entity_details",
        {"entity_name": "leave_balance"},
        {"entity": {"name": "leave_balance"}},
        instance_config=CONFIG,
    ) is None


def test_no_repair_without_a_matching_capability():
    assert propose_repair(
        "get_entity_details",
        {"entity_name": "carbon_footprint"},
        {"entity": None},
        instance_config=CONFIG,
    ) is None


# ── Provenance ───────────────────────────────────────────────────────────────

def test_repaired_result_carries_visible_provenance():
    repair = Repair(
        tool_name="call_host_api",
        tool_args={"api_name": "get_my_leave_balance"},
        strategy="catalog_alias",
        reason="Read the live platform record instead of the knowledge base",
    )
    annotated = annotate_repair({"data": [{"remaining": 23}]}, repair, "get_entity_details")
    assert annotated["self_heal"]["from"] == "get_entity_details"
    assert annotated["self_heal"]["strategy"] == "catalog_alias"
    assert annotated["data"] == [{"remaining": 23}]


# ── Dispatcher integration ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatcher_repairs_a_missed_entity_lookup(monkeypatch):
    import json as _json

    from ai.engine.cognition.turn import execute as execute_mod

    calls: list[tuple[str, dict]] = []

    async def _entity_details(**kwargs):
        calls.append(("get_entity_details", kwargs))
        return {"entity": None, "message": "Entity 'leave_balance' not found"}

    async def _host_api(**kwargs):
        calls.append(("call_host_api", kwargs))
        return {"status_code": 200, "data": [{"leave_type": "annual", "remaining": 23}]}

    async def _executors():
        return {
            "get_entity_details": _entity_details,
            "call_host_api": _host_api,
        }

    monkeypatch.setattr(
        "ai.engine.agent.tools.get_tool_executors", _executors, raising=False,
    )

    result = await execute_mod._execute_single_tool(
        {
            "function": {
                "name": "get_entity_details",
                "arguments": _json.dumps({"entity_name": "leave_balance"}),
            }
        },
        hook_ctx_defaults={"instance_id": "nibras", "instance_config": CONFIG},
    )

    payload = result["result"]
    if isinstance(payload, str):
        payload = _json.loads(payload)
    assert [c[0] for c in calls] == ["get_entity_details", "call_host_api"]
    assert payload["data"][0]["remaining"] == 23
    assert payload["self_heal"]["strategy"] == "catalog_alias"
    assert "self_heal:catalog_alias" in (result.get("guardrail_flags") or [])


@pytest.mark.asyncio
async def test_dispatcher_keeps_the_original_miss_when_repair_also_misses(monkeypatch):
    import json as _json

    from ai.engine.cognition.turn import execute as execute_mod

    async def _entity_details(**kwargs):
        return {"entity": None, "message": "Entity 'leave_balance' not found"}

    async def _host_api(**kwargs):
        return {"status_code": 404, "data": {}}

    async def _executors():
        return {"get_entity_details": _entity_details, "call_host_api": _host_api}

    monkeypatch.setattr(
        "ai.engine.agent.tools.get_tool_executors", _executors, raising=False,
    )

    result = await execute_mod._execute_single_tool(
        {
            "function": {
                "name": "get_entity_details",
                "arguments": _json.dumps({"entity_name": "leave_balance"}),
            }
        },
        hook_ctx_defaults={"instance_id": "nibras", "instance_config": CONFIG},
    )
    payload = result["result"]
    if isinstance(payload, str):
        payload = _json.loads(payload)
    assert payload.get("self_heal") is None
    assert payload["entity"] is None
