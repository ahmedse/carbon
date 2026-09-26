"""ADR-0049 §9 — one capability surface, typed rejection, bounded self-repair.

No LLM, no DB. The GOFSCO regression (conv fc9eb86b, 2026-09-24 14:34):
the prompt offered a tool validation refused, the refusal text reached the
user, the valid reads after it were dropped, and their args were discarded.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.engine.cognition.turn.capability import (
    CapabilitySurface,
    capability_surface,
    flat_args,
    internal_name_labels,
    scrub_internal_names,
)
from ai.engine.cognition.turn.decision import Command, Decision, parse_decision
from ai.engine.cognition.turn.pipeline_v21 import (
    act_on_decision,
    decision_render,
    failed_reads,
    speak_rows,
)
from ai.engine.cognition.turn.understand import catalog_prompt_lines, understand_turn

_BREAKDOWN = {
    "name": "org_breakdown",
    "method": "GET",
    "path": "/api/org/analytics/",
    "audience": ["hr"],
    "description": "Server-side breakdown by one dimension.",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "required": ["dimension"],
        "properties": {"dimension": {"type": "string", "enum": ["gender", "is_active"]}},
    },
}
_RECORD = {
    "name": "get_record",
    "method": "GET",
    "path": "/api/records/{id}/",
    "audience": ["hr"],
    "description": "One record by id.",
}
_SELF = {"name": "get_my_summary", "method": "GET", "path": "/api/my/summary/", "description": "Own summary."}
_CFG = {"api_catalog": [_BREAKDOWN, _RECORD, _SELF]}
_HR = {"username": "hr_user", "audience": ["ess", "hr"]}
_ESS = {"username": "ess_user", "audience": ["ess"]}


def _ecf(monkeypatch: pytest.MonkeyPatch, on: bool) -> None:
    import ai.engine.agent.tools as tools

    monkeypatch.setattr(tools, "get_settings", lambda: SimpleNamespace(ECF_ENABLED=on))


# ── One surface ──────────────────────────────────────────────────────────────

def test_surface_is_audience_scoped_and_carries_registry_capabilities(monkeypatch):
    _ecf(monkeypatch, True)
    hr = capability_surface(_CFG, _HR)
    ess = capability_surface(_CFG, _ESS)
    assert {"org_breakdown", "get_record", "aggregate_entity", "resolve_entity"} <= hr.names
    host = {e["name"] for e in ess.entries if e.get("source") != "tool"}
    assert host == {"get_my_summary"}
    # ADR-0056: the engine's chat tools are on the same surface, run by name.
    tools = {e["name"] for e in ess.entries if e.get("source") == "tool"}
    assert {"learn_fact", "search_knowledge", "export_document"} <= tools
    assert not tools & {"plan_task", "edit_plan", "approve_plan"}
    # The prompt offers exactly what validation allows.
    _lines, allowed, _writes = catalog_prompt_lines("report", list(hr.entries))
    assert allowed == hr.names


def test_registry_capabilities_absent_when_flag_off(monkeypatch):
    _ecf(monkeypatch, False)
    assert "aggregate_entity" not in capability_surface(_CFG, _HR).names


def test_prompt_lines_show_declared_args():
    lines, _, _ = catalog_prompt_lines("breakdown", [_BREAKDOWN], k=0)
    assert any("Args: dimension* (gender|is_active)" in ln for ln in lines)


def test_host_call_binds_path_and_query_params():
    caps = CapabilitySurface(entries=(_BREAKDOWN, _RECORD))
    call = caps.host_call("get_record", {"id": 7, "fields": "a"}, call_id="c1")
    args = json.loads(call["function"]["arguments"])
    assert call["function"]["name"] == "call_host_api"
    assert args["api_name"] == "get_record"
    assert args["path_params"] == {"id": 7}
    assert args["query_params"] == {"fields": "a"}
    nested = caps.host_call("org_breakdown", {"query_params": {"dimension": "gender"}}, call_id="c2")
    assert json.loads(nested["function"]["arguments"])["query_params"] == {"dimension": "gender"}


def test_arg_violations_come_from_the_entry_schema():
    caps = CapabilitySurface(entries=(_BREAKDOWN,))
    assert caps.arg_violations("org_breakdown", {}) == ["missing required field 'dimension'"]
    assert caps.arg_violations("org_breakdown", {"dimension": "gender"}) == []
    assert flat_args({"query_params": {"a": 1}, "b": 2, "api_name": "x"}) == {"a": 1, "b": 2}


# ── Bounded self-repair ──────────────────────────────────────────────────────

def _emit(commands: list[dict], call_id: str = "call_1") -> dict:
    return {
        "tool_calls": [{
            "id": call_id,
            "function": {
                "name": "emit_decision",
                "arguments": json.dumps({"commands": commands, "language": "en", "confidence": 0.9}),
            },
        }],
    }


def _gofsco_first_emit() -> dict:
    return _emit([
        {"op": "call_tool", "name": "headcount_metric", "args": {"metric": "headcount"}},
        {"op": "call_tool", "name": "org_breakdown", "args": {}},
        {"op": "call_tool", "name": "org_breakdown", "args": {"dimension": "is_active"}},
    ])


def test_rejected_commands_are_repaired_once_from_typed_feedback():
    caps = CapabilitySurface(entries=(_BREAKDOWN,))
    seen: list[list[dict]] = []
    replies = [
        _gofsco_first_emit(),
        _emit([
            {"op": "call_tool", "name": "org_breakdown", "args": {"dimension": "gender"}, "render": "chart"},
            {"op": "call_tool", "name": "org_breakdown", "args": {"dimension": "is_active"}, "render": "chart"},
        ], call_id="call_2"),
    ]

    async def complete(*, messages, **_kw):
        seen.append(list(messages))
        return replies[len(seen) - 1]

    decision = asyncio.run(understand_turn(
        complete=complete,
        messages=[{"role": "user", "content": "summary report with charts"}],
        surface="chat",
        allowed_tools=caps.names,
        arg_violations=caps.arg_violations,
    ))
    assert len(seen) == 2
    feedback = seen[1][-1]
    assert feedback["role"] == "tool" and feedback["tool_call_id"] == "call_1"
    body = json.loads(feedback["content"])
    assert {r["name"] for r in body["rejected"]} == {"headcount_metric", "org_breakdown"}
    assert seen[1][-2]["tool_calls"][0]["id"] == "call_1"
    assert decision.repaired is True
    assert [(c.name, c.args) for c in decision.commands] == [
        ("org_breakdown", {"dimension": "gender"}),
        ("org_breakdown", {"dimension": "is_active"}),
    ]
    assert {r.code for r in decision.rejections} == {"not_on_surface", "invalid_args"}
    assert decision.raw_ops == ["call_tool", "call_tool", "call_tool"]
    assert decision_render(decision) == "chart"


def test_repair_budget_is_one_and_leftovers_are_dropped_not_spoken():
    caps = CapabilitySurface(entries=(_BREAKDOWN,))
    calls = {"n": 0}

    async def complete(**_kw):
        calls["n"] += 1
        return _gofsco_first_emit()

    decision = asyncio.run(understand_turn(
        complete=complete,
        messages=[{"role": "user", "content": "report"}],
        surface="chat",
        allowed_tools=caps.names,
        arg_violations=caps.arg_violations,
    ))
    assert calls["n"] == 2
    assert [c.args for c in decision.commands] == [{"dimension": "is_active"}]
    for cmd in decision.commands:
        assert "headcount_metric" not in (cmd.question + cmd.text + cmd.reason)


def test_nothing_valid_left_means_no_commands():
    async def complete(**_kw):
        return _emit([{"op": "call_tool", "name": "not_here"}])

    decision = asyncio.run(understand_turn(
        complete=complete,
        messages=[{"role": "user", "content": "x"}],
        surface="chat",
        allowed_tools={"org_breakdown"},
    ))
    assert decision.commands == []
    assert decision.rejections and decision.repaired
    assert asyncio.run(act_on_decision(decision, execute_tool=None, user_message="x")) is None


# ── Execution: every read, with its args; policy first ──────────────────────

def test_every_decided_read_runs_with_its_args():
    ran: list[tuple[str, dict]] = []

    async def execute_tool(name, args):
        ran.append((name, args))
        return {"data": {"results": [{"label": "a", "count": 3}]}}

    decision = Decision(commands=[
        Command(op="call_tool", name="org_breakdown", args={"dimension": "gender"}),
        Command(op="call_tool", name="org_breakdown", args={"dimension": "is_active"}),
        Command(op="call_tool", name="org_breakdown", args={"dimension": "gender"}),
    ])
    executed: list[dict] = []
    asyncio.run(act_on_decision(decision, execute_tool=execute_tool, user_message="r", executed=executed))
    assert ran == [
        ("org_breakdown", {"dimension": "gender"}),
        ("org_breakdown", {"dimension": "is_active"}),
    ]
    assert executed[0]["tool_args"] == {
        "api_name": "org_breakdown", "query_params": {"dimension": "gender"},
    }


def test_handoff_anywhere_wins_over_reads():
    async def execute_tool(name, args):
        raise AssertionError("a read ran beside a handoff")

    decision = Decision(commands=[
        Command(op="call_tool", name="org_breakdown", args={"dimension": "gender"}),
        Command(op="handoff_agent", process_id="plan"),
    ])
    text = asyncio.run(act_on_decision(decision, execute_tool=execute_tool, user_message="r"))
    assert text and "Plan" in text


def test_act_binds_period_end_from_the_latest_list_row():
    catalog = [{
        "name": "list_payroll_runs",
        "kind": "list",
        "latest_by": "period_end",
        "returns": ["id", "period_end", "status"],
    }, {
        "name": "analyze_committed_pay",
        "kind": "read",
        "parameters": {
            "type": "object",
            "required": ["period_end", "dimension"],
            "properties": {"period_end": {"type": "string"}, "dimension": {"type": "string"}},
        },
    }]
    seen: list[tuple[str, dict]] = []

    async def execute_tool(name, args):
        seen.append((name, dict(args)))
        if name == "list_payroll_runs":
            return {"results": [
                {"id": 32, "period_end": "2026-07-31", "status": "committed"},
                {"id": 31, "period_end": "2026-08-31", "status": "committed"},
            ]}
        return {
            "period_end": args.get("period_end"),
            "dimension": args.get("dimension"),
            "breakdown": [{"label": "Operations", "headcount": 12, "total": "16800.000"}],
        }

    decision = Decision(commands=[
        Command(op="call_tool", name="list_payroll_runs"),
        Command(op="call_tool", name="analyze_committed_pay", args={"dimension": "org_unit"}),
    ])
    rows: list[dict] = []
    asyncio.run(act_on_decision(
        decision, execute_tool=execute_tool, user_message="last payroll report",
        executed=rows, catalog=catalog,
    ))
    assert seen[0][0] == "list_payroll_runs"
    assert seen[1][0] == "analyze_committed_pay"
    assert seen[1][1]["period_end"] == "2026-08-31"
    assert seen[1][1]["dimension"] == "org_unit"


def test_visual_ask_charts_a_text_decision_from_pay_totals():
    rows = [{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "analyze_committed_pay"},
        "result": {
            "dimension": "org_unit",
            "breakdown": [
                {"label": "Operations", "headcount": 12, "total": "16800.000"},
                {"label": "Finance", "headcount": 4, "total": "9200.000"},
            ],
        },
    }]
    decision = Decision(commands=[Command(op="call_tool", name="analyze_committed_pay")])
    text, envelope = speak_rows(
        decision, rows, text="Committed pay structure (2)",
        user_message="Give me a detailed report with visuals",
    )
    assert text == "Committed pay structure (2)"
    assert envelope is not None
    assert envelope["charts"]
    chart_vals = {point[1] for point in envelope["charts"][0]["series"][0]["data"]}
    assert 16800.0 in chart_vals or 16800 in chart_vals


def test_unrestated_rows_are_shown_not_called_failed():
    rows = [{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "org_breakdown", "query_params": {"dimension": "gender"}},
        "result": {"data": {"results": [
            {"gender": "M", "count": 40}, {"gender": "F", "count": 12},
        ]}},
    }]
    decision = Decision(commands=[Command(op="call_tool", name="org_breakdown", render="chart")])
    text, envelope = speak_rows(decision, rows, text="", user_message="report with charts")
    assert "Could not read" not in text
    if envelope is not None:
        assert text


def test_failed_reads_surface_host_argument_rejections():
    rows = [{"tool_args": {"api_name": "org_breakdown"}, "result": {"status_code": 400, "error": "unknown dimension 'x'"}}]
    assert failed_reads(rows) == [{"name": "org_breakdown", "detail": "unknown dimension 'x'"}]


# ── Egress invariant ─────────────────────────────────────────────────────────

def test_internal_identifiers_never_reach_the_user():
    labels = internal_name_labels({"api_catalog": [dict(_BREAKDOWN, label="Org breakdown")]})
    text, hits = scrub_internal_names(
        "I can't use org_breakdown from here. **call_host_api**: 6 rows. See loan_installment.",
        labels,
    )
    assert "org_breakdown" not in text and "call_host_api" not in text
    assert "Org breakdown" in text
    assert "loan_installment" in text  # a field name, not a tool
    assert set(hits) == {"org_breakdown", "call_host_api"}


def test_tool_summary_names_the_capability_not_the_executor():
    from ai.engine.cognition.turn.execute import _build_tool_result_summary

    summary = _build_tool_result_summary([{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "get_my_summary"},
        "result": {"data": [{"a": 1}]},
    }])
    assert "call_host_api" not in summary and "get_my_summary" in summary


# ── Pack contract: prompt text names only tools its reader can call ─────────

def test_shipped_packs_name_only_reachable_tools():
    from ai.eval.pack_contract import check_all

    _rows, violations = check_all()
    assert violations == []


def test_pack_contract_catches_identity_and_cross_audience_names(tmp_path: Path):
    from ai.eval.pack_contract import tool_reference_violations

    path = tmp_path / "instance.yaml"
    path.write_text(
        "persona: Call org_breakdown for any org question.\n"
        "api_catalog:\n"
        "  - name: get_my_summary\n"
        "    method: GET\n"
        "    path: /my/summary/\n"
        "    description: Own summary. HR uses org_breakdown or aggregate_entity.\n"
        "  - name: org_breakdown\n"
        "    method: GET\n"
        "    path: /org/\n"
        "    audience: [hr]\n"
        "    description: Breakdown.\n",
        encoding="utf-8",
    )
    found = tool_reference_violations(path)
    assert any(v.startswith("persona names tools ['org_breakdown']") for v in found)
    assert "api_catalog.get_my_summary names org_breakdown, hidden from ['ess']" in found
    assert "api_catalog.get_my_summary names engine tool aggregate_entity" in found
