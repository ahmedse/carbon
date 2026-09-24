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
    assert "I have a loan" in read_line and "Not for:" in read_line
    assert "Agent only" in write_line and "handoff_agent" in write_line
    assert "what type of loan" in write_line.lower()
    # Examples ride along so the model sees the conversational phrasings.
    assert any("I noticed I have a loan" in l for l in lines if l.startswith("  e.g."))

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
    assert "plan" in text and "Agent" in text


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
