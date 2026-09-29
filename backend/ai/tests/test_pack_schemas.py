"""Spine tool schemas and process files follow the bound pack."""
from __future__ import annotations

from ai.engine.agent.tools import (
    _ECF_AGGREGATE_ENTITY_DEFINITION,
    _ECF_RESOLVE_ENTITY_DEFINITION,
    _enrich_ecf_tool_definitions,
)
from ai.engine.cognition.turn.process_brief import (
    format_process_briefing,
    process_ids,
)
from ai.engine.pack_vocab import bind_pack

_HOST = (
    "list_employees",
    "HRMS",
    "leave_record",
    "analyze_employees",
    "open_leave_count",
)


def _schema_text(pack: str) -> str:
    with bind_pack(pack):
        tools = _enrich_ecf_tool_definitions(
            [_ECF_RESOLVE_ENTITY_DEFINITION, _ECF_AGGREGATE_ENTITY_DEFINITION],
            None,
        )
    return str(tools)


def test_nibras_schema_and_process():
    with bind_pack("nibras"):
        tools = _enrich_ecf_tool_definitions(
            [_ECF_RESOLVE_ENTITY_DEFINITION, _ECF_AGGREGATE_ENTITY_DEFINITION],
            None,
        )
        enum = tools[0]["function"]["parameters"]["properties"]["entity_type"]["enum"]
        assert "leave_record" in enum
        assert "" not in enum
        assert "leave.request.lifecycle" in process_ids()
        assert "cohort.review.lifecycle" not in process_ids()
        text = format_process_briefing("leave.request.lifecycle", lang="en") or ""
        assert "leave.request.lifecycle" in text


def test_medicine_schema_and_process_are_absent():
    text = _schema_text("aast-med")
    for fragment in _HOST:
        assert fragment not in text, fragment
    with bind_pack("aast-med"):
        assert "leave.request.lifecycle" not in process_ids()
        assert format_process_briefing("leave.request.lifecycle") is None


def test_eduos_process_is_its_own():
    with bind_pack("eduos"):
        ids = process_ids()
        assert "cohort.review.lifecycle" in ids
        assert "leave.request.lifecycle" not in ids
        text = format_process_briefing("cohort.review.lifecycle", lang="en") or ""
        assert "human_only" in text


def test_one_metric_example_names_only_that_id():
    from ai.engine.agent.tools import _metric_required_error

    assert _metric_required_error(["headcount"]) == (
        "aggregate_entity requires a metric name (e.g. 'headcount')."
    )
    assert "kuwaiti" not in _metric_required_error(["headcount"])
    assert _metric_required_error(["", ""]) == (
        "aggregate_entity requires a metric name."
    )


def test_missing_metric_error_follows_the_pack():
    import asyncio
    from types import SimpleNamespace

    from ai.engine.agent.tools import execute_call_host_api

    executor = SimpleNamespace(user_token="t", instance_config={"display_name": "Host"})

    async def _err(pack: str) -> str:
        with bind_pack(pack):
            out = await execute_call_host_api(
                "aggregate_entity", executor=executor,
            )
        return str(out.get("error") or "")

    nibras = asyncio.run(_err("nibras"))
    assert nibras == (
        "aggregate_entity requires a metric name (e.g. 'headcount' or 'kuwaiti')."
    )
    medicine = asyncio.run(_err("aast-med"))
    assert medicine == "aggregate_entity requires a metric name."
    for fragment in ("headcount", "kuwaiti", "open_leave_count"):
        assert fragment not in medicine


def test_process_id_cannot_escape_the_pack():
    with bind_pack("aast-med"):
        assert format_process_briefing("../nibras/processes/leave.request.lifecycle") is None
        assert format_process_briefing("") is None
    with bind_pack("nibras"):
        assert "" not in process_ids()
