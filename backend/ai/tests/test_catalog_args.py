"""Catalog parameter contract: one repair, then stop. A dependent write waits."""

from types import SimpleNamespace

import pytest

from ai.engine.cognition.plan.catalog_args import (
    READ_GAP,
    catalog_arg_violations,
    is_invalid_argument_error,
    mutation_blocked_by_failed_read,
)
from ai.engine.cognition.plan.loop import ReActLoop
from ai.engine.cognition.plan.planner import PlanStep
from ai.engine.workflow.heal import propose_heal
from ai.engine.workflow.retry import should_retry

CATALOG = [{
    "name": "analyze_employees",
    "method": "GET",
    "parameters": {
        "type": "object",
        "required": ["dimension"],
        "properties": {
            "dimension": {
                "type": "string",
                "enum": ["gender", "nationality", "position"],
            },
        },
    },
}]

EMPTY = {
    "api_name": "analyze_employees",
    "query_params": {"dimension": ""},
}


def _empty_args():
    return {
        "api_name": "analyze_employees",
        "query_params": {"dimension": ""},
    }


def test_empty_dimension_is_a_schema_miss():
    misses = catalog_arg_violations(CATALOG, "call_host_api", EMPTY)
    assert misses
    assert catalog_arg_violations(
        CATALOG,
        "call_host_api",
        {"api_name": "analyze_employees", "query_params": {"dimension": "nationality"}},
    ) == []


def test_timeout_is_not_an_argument_repair():
    timeout = "[timeout] exceeded timeout_ms=1000"
    assert is_invalid_argument_error(timeout) is False
    assert is_invalid_argument_error("Host API request timed out (30s)") is False
    assert should_retry({"retry_on": ["timeout", "transient"]}, timeout, 0) is True
    assert is_invalid_argument_error("Host API returned 400: bad field") is True
    assert should_retry(None, "Host API returned 400: bad field", 0) is False


def test_export_depending_on_a_failed_read_is_blocked():
    export = PlanStep(
        step_id=7,
        intent="Export the brief",
        tool_name="export_document",
        is_mutation=True,
        depends_on=[3],
    )
    assert mutation_blocked_by_failed_read(export, {3}) is True
    assert mutation_blocked_by_failed_read(export, set()) is False


def test_heal_keeps_a_mutation_dependency_on_the_failed_read():
    failed = PlanStep(step_id=3, intent="People records", depends_on=[])
    export = PlanStep(
        step_id=7,
        intent="Export",
        tool_name="export_document",
        is_mutation=True,
        depends_on=[3],
    )
    proposal = propose_heal(
        goal="loan portfolio brief",
        failed_step=failed,
        failed_error="bad field",
        remaining_steps=[export],
        next_step_id=10,
    )
    assert 3 in proposal.new_steps[1].depends_on


class _Draft:
    def __init__(self, text):
        self.text = text

    async def draft(self, **_kwargs):
        return SimpleNamespace(text=self.text, tokens_used=0)


@pytest.mark.asyncio
async def test_one_repair_with_an_allowed_value_updates_the_call():
    loop = ReActLoop()
    step = PlanStep(
        step_id=3,
        intent="People by nationality",
        tool_name="call_host_api",
        tool_args=_empty_args(),
    )
    calls = [{
        "function": {
            "name": "call_host_api",
            "arguments": "{}",
        },
    }]
    updated, gap, used = await loop._repair_catalog_call(
        step,
        calls,
        _Draft('{"dimension": "nationality"}'),
        instance_config={"api_catalog": CATALOG},
        user_info={},
        instance_id="i",
        conversation_id="c",
        conversation_history=[],
    )
    assert gap is None
    assert used == 1
    assert step.tool_args["query_params"]["dimension"] == "nationality"
    assert "nationality" in updated[0]["function"]["arguments"]


@pytest.mark.asyncio
async def test_a_second_miss_fails_the_step_without_calling_the_host():
    loop = ReActLoop()
    step = PlanStep(
        step_id=3,
        intent="People records",
        tool_name="call_host_api",
        tool_args=_empty_args(),
    )
    _calls, gap, used = await loop._repair_catalog_call(
        step,
        [],
        _Draft('{"dimension": "not-a-real-field"}'),
        instance_config={"api_catalog": CATALOG},
        user_info={},
        instance_id="i",
        conversation_id="c",
        conversation_history=[],
    )
    assert gap == READ_GAP
    assert used == 1
    assert catalog_arg_violations(CATALOG, "call_host_api", step.tool_args)
