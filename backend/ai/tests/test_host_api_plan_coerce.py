"""Host API catalog coercion + get_entity_details alias (SIM-20260919-N10).

Agent Plan·Run historically bound catalog names like ``get_my_leave_balance``
to ``get_entity_details``, which only searches the knowledge store and soft-
misses with ``Entity '…' not found``. Chat uses ``call_host_api``. These
tests lock the systemic rewrite + runtime alias.
"""
from __future__ import annotations

import pytest


def test_decompose_prompt_lists_host_api_catalog():
    from ai.engine.cognition.plan.planner import _DECOMPOSE_AGENT_PROMPT

    assert "{host_api_list}" in _DECOMPOSE_AGENT_PROMPT
    assert "call_host_api" in _DECOMPOSE_AGENT_PROMPT
    assert "NEVER put a catalog name in" in _DECOMPOSE_AGENT_PROMPT


def test_coerce_get_entity_details_leave_balance_to_call_host_api():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance", "create_leave_record", "list_my_leave"}
    step = PlanStep(
        step_id=0,
        intent="Retrieve leave balance",
        tool_name="get_entity_details",
        tool_args={"entity_name": "get_my_leave_balance"},
    )
    _coerce_host_api_steps([step], catalog)
    assert step.tool_name == "call_host_api"
    assert step.tool_args.get("api_name") == "get_my_leave_balance"
    assert "entity_name" not in step.tool_args


def test_coerce_tool_name_that_is_catalog_api():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance"}
    step = PlanStep(
        step_id=1,
        intent="Get balance",
        tool_name="get_my_leave_balance",
        tool_args={},
    )
    _coerce_host_api_steps([step], catalog)
    assert step.tool_name == "call_host_api"
    assert step.tool_args == {"api_name": "get_my_leave_balance"}


def test_coerce_leaves_real_knowledge_entity_alone():
    from ai.engine.cognition.plan.planner import PlanStep, _coerce_host_api_steps

    catalog = {"get_my_leave_balance"}
    step = PlanStep(
        step_id=2,
        intent="Schema for employees table",
        tool_name="get_entity_details",
        tool_args={"entity_name": "employees"},
    )
    _coerce_host_api_steps([step], catalog)
    assert step.tool_name == "get_entity_details"
    assert step.tool_args == {"entity_name": "employees"}


@pytest.mark.asyncio
async def test_get_entity_details_aliases_catalog_name_to_call_host_api(monkeypatch):
    from ai.engine.agent import tools as tools_mod

    seen = {}

    async def _fake_call_host_api(**kwargs):
        seen.update(kwargs)
        return {"status_code": 200, "data": [{"leave_type": "annual", "remaining": "16.00"}]}

    monkeypatch.setattr(tools_mod, "execute_call_host_api", _fake_call_host_api)

    class _Exec:
        instance_config = {
            "api_catalog": [
                {"name": "get_my_leave_balance", "method": "GET", "path": "/x/"},
            ]
        }

    result = await tools_mod.execute_get_entity_details(
        entity_name="get_my_leave_balance",
        knowledge_store=None,
        instance_id="nibras",
        executor=_Exec(),
    )
    assert result["status_code"] == 200
    assert seen.get("api_name") == "get_my_leave_balance"
    assert seen.get("executor") is not None


@pytest.mark.asyncio
async def test_get_entity_details_still_misses_unknown_knowledge_name():
    from ai.engine.agent.tools import execute_get_entity_details

    class _KS:
        async def get_entity(self, instance_id, name):
            return None

    result = await execute_get_entity_details(
        entity_name="totally_unknown_kg_thing",
        knowledge_store=_KS(),
        instance_id="nibras",
        executor=type("E", (), {"instance_config": {"api_catalog": []}})(),
    )
    assert result["entity"] is None
    assert "not found" in result["message"]
