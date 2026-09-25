"""Catalog contract + v21 act path. No LLM, no Django DB."""
from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from ai.engine.cognition.turn.decision import parse_decision
from ai.engine.cognition.turn.pipeline_v21 import act_on_decision
from ai.eval.api_catalog_contract import catalog_violations


def _nibras_catalog() -> list:
    path = (
        Path(__file__).resolve().parents[1]
        / "engine"
        / "instances"
        / "nibras"
        / "instance.yaml"
    )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data.get("api_catalog") or [])


def test_nibras_kinded_entries_have_not_for_and_empty_render():
    violations = catalog_violations(_nibras_catalog())
    assert violations == [], violations


def test_catalog_prompt_lines_describe_write_twin_as_agent_only():
    """ADR-0049 §2: twins are separated in the catalog. The write twin is
    described (so its not_for can route) but marked Agent-only; a call_tool on
    it is downgraded to handoff_agent, never executed and never 'unknown'."""
    from ai.engine.cognition.turn.decision import validate_decision
    from ai.engine.cognition.turn.understand import catalog_prompt_lines

    lines, allowed, writes = catalog_prompt_lines(
        "I noticed I have a loan, can you give me more details?", _nibras_catalog(), k=12
    )
    assert {"list_my_loans", "submit_my_loan"} <= allowed
    assert "submit_my_loan" in writes and "list_my_loans" not in writes
    read_line = next(l for l in lines if l.startswith("- list_my_loans"))
    write_line = next(l for l in lines if l.startswith("- submit_my_loan"))
    assert "OWN loans" in read_line or "loan_type" in read_line
    assert "Not for:" in read_line
    assert "Agent only" in write_line and "handoff_agent" in write_line
    assert "principal*" in write_line
    assert "what type of loan" in write_line.lower() or "NEW loan" in write_line
    # Examples ride along on top-k so the model sees conversational phrasings.
    assert any("I noticed I have a loan" in l for l in lines if l.startswith("  e.g."))
    pay_lines, _, _ = catalog_prompt_lines(
        "أنا أدفع قسط قرض، اعرضه لي", _nibras_catalog(), k=12
    )
    assert any("أدفع قسط قرض" in l for l in pay_lines if l.startswith("  e.g."))
    dual, _, _ = catalog_prompt_lines("How much leave and what loans?", _nibras_catalog(), k=12)
    leave_line = next(l for l in dual if l.startswith("- get_my_leave_balance"))
    assert "clarify" in leave_line
    payslip_line = next(l for l in pay_lines if l.startswith("- list_my_payslips"))
    assert "list_my_loans" in payslip_line

    decision = parse_decision(
        {
            "commands": [{"op": "call_tool", "name": "submit_my_loan"}],
            "language": "en",
            "confidence": 0.9,
        }
    )
    out = validate_decision(
        decision, surface="chat", allowed_tools=allowed, write_tools=writes
    )
    assert out.commands[0].op == "handoff_agent"
    assert out.commands[0].process_id == "submit_my_loan"


def test_bare_followup_ranks_the_offered_read_from_context():
    from ai.engine.cognition.turn.understand import catalog_context, catalog_prompt_lines

    history = [
        {"role": "user", "content": "What was my last payslip?"},
        {"role": "assistant", "content": "Your payslip: gross 6500; GOSI 1200; net 4500."},
        {"role": "user", "content": "I noticed I have a loan, can you give me more details?"},
        {"role": "assistant", "content": "I can fetch your loan details for you. Want me to?"},
    ]
    lines, allowed, _writes = catalog_prompt_lines(
        "جيبها",
        _nibras_catalog(),
        k=12,
        context=catalog_context(history),
    )
    assert "list_my_loans" in allowed
    assert any(line.startswith("- list_my_loans") for line in lines)


def test_act_clarify_and_chat_handoff_do_not_execute():
    clarify = parse_decision(
        {
            "commands": [{"op": "clarify", "question": "Balance or requests?"}],
            "language": "en",
            "confidence": 0.4,
        }
    )
    called = {"n": 0}

    async def execute_tool(name, args):
        called["n"] += 1
        return []

    text = asyncio.run(
        act_on_decision(clarify, execute_tool=execute_tool, user_message="leave")
    )
    assert text == "Balance or requests?"
    assert called["n"] == 0


def test_act_call_tool_restates_host_payload():
    decision = parse_decision(
        {
            "commands": [{"op": "call_tool", "name": "get_my_leave_balance"}],
            "language": "en",
            "confidence": 0.9,
        }
    )

    async def execute_tool(name, args):
        assert name == "get_my_leave_balance"
        return [{"leave_type": "annual", "remaining": 14, "entitled": 30, "used": 16, "pending": 0}]

    text = asyncio.run(
        act_on_decision(decision, execute_tool=execute_tool, user_message="balance")
    )
    assert text
    assert "0 يوم" not in text


def test_answer_falls_through():
    decision = parse_decision(
        {
            "commands": [{"op": "answer", "text": "hello"}],
            "language": "en",
            "confidence": 0.2,
        }
    )
    text = asyncio.run(
        act_on_decision(decision, execute_tool=None, user_message="hi")
    )
    assert text is None


def test_scoped_catalog_is_fully_described_and_allowed_even_when_ranker_misses():
    """Short Arabic shares no tokens with English descriptions; the right
    read must still be offered and allowed. Admin tools never leak to ESS."""
    from ai.engine.cognition.context_pack import filter_catalog_by_audience
    from ai.engine.cognition.turn.understand import catalog_prompt_lines

    scoped = filter_catalog_by_audience(_nibras_catalog(), ["ess"])
    lines, allowed, writes = catalog_prompt_lines("عن الإجازات", scoped, k=3)
    names = {t["name"] for t in scoped}
    assert allowed == names
    assert "get_my_leave_balance" in allowed
    assert "commit_payroll_run" not in allowed
    assert "submit_my_leave" in writes
    assert sum(1 for ln in lines if ln.startswith("- ")) == len(names)
    assert sum(1 for ln in lines if ln.startswith("  e.g.")) <= 3 * 3


def test_decision_render_parses_and_defaults_to_text():
    chart = parse_decision({
        "commands": [{"op": "continue", "render": "chart"}],
        "language": "en", "confidence": 0.9,
    })
    odd = parse_decision({
        "commands": [{"op": "call_tool", "name": "x", "render": "hologram"}],
        "language": "en", "confidence": 0.9,
    })
    assert chart.commands[0].render == "chart"
    assert odd.commands[0].render == "text"


def test_render_envelope_charts_only_the_decided_read():
    """Continue on a leave thread → leave chart. The payslip payload the
    legacy Draft also fetched cannot reach the envelope."""
    from types import SimpleNamespace

    from ai.engine.cognition.turn.pipeline_v21 import render_envelope

    decision = parse_decision({
        "commands": [{"op": "continue", "render": "chart"}],
        "language": "en", "confidence": 0.9,
    })
    state = SimpleNamespace(
        last_results=[{"api": "get_my_leave_balance"}], open_question=None,
    )
    payloads = {
        "get_my_leave_balance": [
            {"leave_type": "annual", "entitled": 30, "remaining": 30},
            {"leave_type": "sick", "entitled": 30, "remaining": 29},
        ],
        "list_my_payslips": [
            {"line_type": "gross", "amount": 6500},
            {"line_type": "net", "amount": 4500},
        ],
    }
    calls: list[str] = []

    async def execute_tool(name, args):
        calls.append(name)
        return payloads[name]

    executed: list[dict] = []
    text = asyncio.run(act_on_decision(
        decision, execute_tool=execute_tool, user_message="where are the charts?",
        state=state, executed=executed,
    ))
    assert calls == ["get_my_leave_balance"]
    env = render_envelope(decision, executed, headline=text or "")
    assert env is not None
    titles = [c["title"] for c in env["charts"]]
    assert titles == ["Leave balance"]
    assert "Gross" not in repr(env) and "Payslip" not in repr(env)


def test_render_envelope_text_and_table_modes():
    from ai.engine.cognition.turn.pipeline_v21 import render_envelope

    rows = [{
        "tool_name": "call_host_api",
        "tool_args": {"api_name": "get_my_leave_balance"},
        "result": [
            {"leave_type": "annual", "entitled": 30, "remaining": 30},
            {"leave_type": "sick", "entitled": 30, "remaining": 29},
        ],
    }]

    def _d(render):
        return parse_decision({
            "commands": [{"op": "call_tool", "name": "get_my_leave_balance", "render": render}],
            "language": "en", "confidence": 0.9,
        })

    assert render_envelope(_d("text"), rows) is None
    table = render_envelope(_d("table"), rows)
    assert table["charts"] == [] and table["tables"]


def test_non_get_catalog_entries_are_agent_only_writes():
    from ai.engine.cognition.turn.understand import catalog_prompt_lines

    lines, allowed, writes = catalog_prompt_lines("commit the payroll run", _nibras_catalog())
    assert {"compute_payroll_run", "validate_payroll_run", "commit_payroll_run"} <= writes
    assert "list_payroll_runs" not in writes
    commit = next(ln for ln in lines if ln.startswith("- commit_payroll_run"))
    assert "Agent only" in commit


def test_plan_handoff_reply_is_plan_copy():
    decision = parse_decision({
        "commands": [{"op": "handoff_agent", "process_id": "plan"}],
        "language": "en", "confidence": 0.9,
    })
    text = asyncio.run(act_on_decision(decision, execute_tool=None, user_message="run it"))
    # Ask owns answers. Drafting a multi-step run is the Plan dial.
    assert "Plan" in text
    assert "Agent" not in text
    on_plan = asyncio.run(act_on_decision(
        decision, execute_tool=None, user_message="run it", surface="chat.plan",
    ))
    assert on_plan is None


def test_malformed_understand_returns_none_so_legacy_speaks():
    from ai.engine.cognition.turn.understand import understand_turn

    async def complete(**kwargs):
        return {"tool_calls": [{"function": {
            "name": "emit_decision",
            "arguments": '{"commands":[{"op":"export_board_pack"}],"language":"en","confidence":0.4}',
        }}]}

    decision = asyncio.run(understand_turn(
        complete=complete, messages=[{"role": "user", "content": "x"}],
    ))
    assert decision is None


def test_rules_survive_hr_catalog_clip_and_all_tools_fit():
    """HR catalog was ~14k; rules after the catalog were clipped. Rules first
    + compact non-top-k lines keep process_id=plan and every allowed name.
    Ceiling is 10200 so named closed-aggregate entries still fit."""
    from ai.engine.cognition.context_pack import TASK_BLOCK_MAX_CHARS, filter_catalog_by_audience
    from ai.engine.cognition.turn.understand import (
        _UNDERSTAND_RULES,
        build_understand_system_prompt,
        catalog_prompt_lines,
    )

    scoped = filter_catalog_by_audience(_nibras_catalog(), ["ess", "hr"])
    assert len(scoped) >= 30
    lines, allowed, _writes = catalog_prompt_lines(
        "Run October payroll variance for GOFSCO",
        scoped,
        k=12,
    )
    task = f"{_UNDERSTAND_RULES}\n\nCATALOG:\n" + "\n".join(lines)
    assert len(task) <= TASK_BLOCK_MAX_CHARS, len(task)
    prompt = build_understand_system_prompt(
        catalog_lines=lines,
        user_info={"username": "emp_2378", "audience": ["ess", "hr"]},
        instance_config={"api_catalog": scoped},
    )
    assert "process_id=plan" in prompt
    assert "not a clarify" in prompt
    for name in allowed:
        assert f"- {name}" in prompt or f"- {name} (" in prompt


def test_ess_sees_coworker_leave_read_and_module_nav():
    """403-honest coworker leave + bare module navigate need ESS visibility."""
    from ai.engine.cognition.context_pack import filter_catalog_by_audience
    from ai.engine.cognition.turn.understand import navigation_prompt_lines

    tools = filter_catalog_by_audience(_nibras_catalog(), ["ess"])
    names = {t["name"] for t in tools}
    assert "list_leave_entitlements" in names
    assert "get_my_leave_balance" in names
    from ai.engine.core.archetypes import load_instance_config
    from ai.engine.cognition.turn.runner_helpers import _scoped_navigation_routes

    nav = _scoped_navigation_routes(load_instance_config("nibras"), {"audience": ["ess"]})
    nav_names = {r["name"] for r in nav}
    assert {"attendance", "payroll"} <= nav_names
    lines = navigation_prompt_lines(nav)
    assert any(ln.startswith("- attendance:") for ln in lines)


def test_ess_does_not_see_hr_closed_aggregates():
    from ai.engine.cognition.context_pack import filter_catalog_by_audience

    ess = {t["name"] for t in filter_catalog_by_audience(_nibras_catalog(), ["ess"])}
    hr = {t["name"] for t in filter_catalog_by_audience(_nibras_catalog(), ["hr"])}
    hidden = {
        "analyze_kuwaitization",
        "analyze_leave_utilization",
        "analyze_loan_book",
        "analyze_gosi_committed",
        "analyze_cert_expiry",
        "analyze_leave_presence",
    }
    assert hidden.isdisjoint(ess)
    assert hidden <= hr


def test_hr_closed_aggregate_utterances_rank_the_named_get():
    """Top-k must describe the named GET, not a truncated list hop."""
    from ai.engine.cognition.catalog_retrieval import rank_tools
    from ai.engine.cognition.context_pack import filter_catalog_by_audience
    from ai.engine.cognition.turn.understand import catalog_prompt_lines

    hr = filter_catalog_by_audience(_nibras_catalog(), ["ess", "hr"])
    pairs = [
        ("leave utilization by org unit for this year", "analyze_leave_utilization",
         "list_leave_entitlements"),
        ("who is on approved leave this month by department", "analyze_leave_presence",
         "list_leave_records"),
        ("outstanding loan principal by org unit as of 2026-09-30", "analyze_loan_book",
         "list_loans"),
        ("committed GOSI totals by nationality for the period", "analyze_gosi_committed",
         "list_payslip_lines"),
        ("certifications expiring in 90 days by org unit", "analyze_cert_expiry",
         "list_employees"),
        ("committed pay average and median by org unit for the latest period",
         "analyze_committed_pay", "list_payslip_lines"),
    ]
    for utterance, named, hop in pairs:
        ranked = [t["name"] for t in rank_tools(utterance, hr, k=12)]
        assert named in ranked[:5], (utterance, ranked[:8])
        assert ranked.index(named) < ranked.index(hop) if hop in ranked else True
        lines, allowed, _ = catalog_prompt_lines(utterance, hr, k=12)
        assert named in allowed
        described = next(ln for ln in lines if ln.startswith(f"- {named}"))
        assert "Returns:" in described, named


def test_coworker_leave_still_outranks_utilization():
    from ai.engine.cognition.catalog_retrieval import rank_tools
    from ai.engine.cognition.context_pack import filter_catalog_by_audience

    hr = filter_catalog_by_audience(_nibras_catalog(), ["ess", "hr"])
    ranked = [t["name"] for t in rank_tools("what's Wellie's leave balance?", hr, k=8)]
    assert ranked[0] == "list_leave_entitlements"
    assert ranked.index("list_leave_entitlements") < ranked.index("analyze_leave_utilization")


def test_list_loans_does_not_claim_remaining_balance():
    entry = next(t for t in _nibras_catalog() if t.get("name") == "list_loans")
    blob = f"{entry.get('description') or ''} {' '.join(entry.get('returns') or [])}"
    assert "remaining_balance" not in blob
    assert "monthly_installment" not in blob
    assert "principal" in (entry.get("returns") or [])
    assert "status" in (entry.get("returns") or [])
    assert "remaining_balance" not in (entry.get("returns") or [])
