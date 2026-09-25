"""ADR-0056 — v21 finishes every op it emits; nothing falls through to legacy."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from ai.engine.cognition.turn.decision import Command, Decision
from ai.engine.cognition.turn.runner_surfaces import SoftSurfacesMixin
from ai.engine.cognition.turn.witnesses import TurnLedger

_CFG = {
    "api_catalog": [{"name": "get_my_summary", "method": "GET", "description": "Own summary."}],
    "navigation_routes": [
        {"name": "my_home", "path": "/my", "type": "app", "label": "My"},
        {"name": "team_home", "path": "/team", "type": "app", "label": "Team"},
    ],
}


class _Runner(SoftSurfacesMixin):
    def __init__(self):
        self.executor = SimpleNamespace()
        self.knowledge_store = None
        self.memory_manager = None
        self.db = None
        self.calls: list[dict] = []

    async def _record_understand(self, **kwargs):
        return None

    async def _write_ledger_row(self, *args, **kwargs):
        return None


@pytest.fixture
def turn(monkeypatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    seen: dict = {"tool_calls": [], "writer": []}

    class _Witness:
        def __init__(self, **kwargs):
            pass

        async def execute(self, *, tool_calls, **kwargs):
            seen["tool_calls"].extend(tool_calls)
            fn = tool_calls[0]["function"]
            return SimpleNamespace(completed_tools=[{
                "tool_name": fn["name"],
                "tool_args": json.loads(fn["arguments"]),
                "result": {"ok": True, "summary": "done"},
            }])

    monkeypatch.setattr("ai.engine.cognition.turn.execute.ExecuteWitness", _Witness)

    async def fake_retrieve(self, *args, **kwargs):
        from ai.engine.cognition.turn.witnesses import RetrievalResult

        return RetrievalResult()

    monkeypatch.setattr(
        "ai.engine.cognition.turn.retrieve.RetrievalWitness.retrieve", fake_retrieve,
    )

    async def fake_route_chat(**kwargs):
        seen["writer"].append(kwargs)
        return {"content": seen.get("answer", "Hello — how can I help?"), "model": "stub"}

    monkeypatch.setattr("ai.engine.llm.router.route_chat", fake_route_chat)

    async def fake_envelope(**kwargs):
        from ai.envelope import AnswerEnvelope

        seen.setdefault("envelope", []).append(kwargs)
        return AnswerEnvelope(headline="", prose=["The search finished."])

    monkeypatch.setattr("ai.envelope_service.synthesize_envelope", fake_envelope)

    def run(decision: Decision, *, surface="chat", process_mode="ask", answer=None):
        if answer is not None:
            seen["answer"] = answer

        async def understood(**kwargs):
            return decision

        monkeypatch.setattr("ai.engine.cognition.turn.understand.understand_turn", understood)
        ledger = TurnLedger()
        out = asyncio.run(_Runner()._try_v21_understand(
            user_message="hi",
            conversation_history=[],
            ledger=ledger,
            turn_id="t-finish",
            instance_id="nibras",
            conversation_id="c-finish",
            host_user_id=None,
            instance_config=_CFG,
            t0=0.0,
            surface=surface,
            process_mode=process_mode,
        ))
        return out, ledger, seen

    return run


def _fell_through(ledger) -> bool:
    return any(
        s.get("gate") == "v21_understand" and (s.get("detail") or {}).get("reason") == "fallthrough"
        for s in ledger.decision_signals or []
    )


def test_answer_is_written_by_v21_not_the_legacy_draft(turn):
    out, ledger, seen = turn(Decision(
        commands=[Command(op="answer")], reason="A greeting.", confidence=0.9,
    ))
    assert out is not None, "an answer Decision fell through to legacy"
    assert out[0].text == "Hello — how can I help?"
    assert len(seen["writer"]) == 1
    assert not seen["writer"][0].get("tools")
    assert not _fell_through(ledger)


def test_an_empty_answer_is_a_visible_error(turn):
    out, ledger, _ = turn(
        Decision(commands=[Command(op="answer")], confidence=0.9), answer="",
    )
    assert out is not None
    assert any(s.get("gate") == "degraded" for s in ledger.decision_signals or [])


def test_an_ungrounded_answer_retries_once_then_fails(monkeypatch):
    from ai.engine.cognition.turn.finish import write_answer

    calls = {"n": 0, "notes": []}

    async def fake_route_chat(**kwargs):
        calls["n"] += 1
        calls["notes"].append(kwargs.get("messages") or [])
        return {"content": "About 90 remain.", "model": "stub"}

    monkeypatch.setattr("ai.engine.llm.router.route_chat", fake_route_chat)
    text, usage = asyncio.run(write_answer(
        Decision(commands=[Command(op="answer")], reason="A count.", confidence=0.9),
        user_message="how many",
        conversation_history=[],
        state=None,
        user_info=None,
        instance_config=None,
        retrieval=None,
        instance_id="nibras",
        conversation_id="c-ungrounded",
    ))
    assert calls["n"] == 2
    assert text == ""
    assert usage["cause"] == "ungrounded"
    assert "90" in json.dumps(calls["notes"][1])


def test_navigate_opens_the_route_the_decision_named(turn):
    out, ledger, seen = turn(Decision(
        commands=[Command(op="navigate", target_id="team_home")], confidence=0.9,
    ))
    assert out is not None
    assert "Team" in out[0].text
    assert out[0].actions and "/team" in json.dumps(out[0].actions)
    assert not seen["writer"], "navigation needs no model call"
    assert ledger.turn_decision == "navigate"


def test_an_unknown_route_is_not_guessed(turn):
    out, ledger, _ = turn(Decision(
        commands=[Command(op="navigate", target_id="nowhere")], confidence=0.9,
    ))
    assert out is not None
    assert not out[0].actions
    assert any(s.get("gate") == "degraded" for s in ledger.decision_signals or [])


def test_set_slot_stores_the_value_then_answers(turn):
    out, _, seen = turn(Decision(
        commands=[Command(op="set_slot", key="period", value="2026-08")], confidence=0.9,
    ))
    assert out is not None
    assert len(seen["writer"]) == 1


def test_an_engine_tool_runs_as_itself(turn):
    out, ledger, seen = turn(Decision(
        commands=[Command(op="call_tool", name="search_knowledge", args={"query": "policy"})],
        confidence=0.9,
    ))
    assert out is not None
    assert out[0].text == "The search finished."
    fn = seen["tool_calls"][0]["function"]
    assert fn["name"] == "search_knowledge"
    assert json.loads(fn["arguments"]) == {"query": "policy"}
    rows = list(getattr(ledger.execution, "completed_tools", None) or [])
    assert rows and rows[0]["tool_name"] == "search_knowledge"


def test_a_host_read_still_runs_through_call_host_api(turn):
    _, _, seen = turn(Decision(
        commands=[Command(op="call_tool", name="get_my_summary")], confidence=0.9,
    ))
    fn = seen["tool_calls"][0]["function"]
    assert fn["name"] == "call_host_api"
    assert json.loads(fn["arguments"])["api_name"] == "get_my_summary"


def test_a_chat_write_keeps_the_models_args_through_validation():
    from ai.engine.cognition.turn.decision import validate_decision

    body = {"body": {"loan_type": "emergency", "principal": 5000}}
    out = validate_decision(
        Decision(commands=[Command(op="call_tool", name="submit_my_loan", args=body)]),
        surface="chat", allowed_tools={"submit_my_loan"}, write_tools={"submit_my_loan"},
    )
    cmd = out.commands[0]
    assert (cmd.op, cmd.process_id, cmd.args) == ("handoff_agent", "submit_my_loan", body)


def test_a_chat_write_becomes_the_handoff_card_with_its_slots(turn, monkeypatch):
    seeded = {}
    monkeypatch.setattr(
        "ai.engine.cognition.turn.handoff_agent.seed_slots_into_state",
        lambda state_ctx, api, slots: seeded.update(api=api, slots=slots),
    )
    out, ledger, seen = turn(Decision(
        commands=[Command(
            op="handoff_agent", process_id="submit_my_loan",
            args={"body": {"loan_type": "emergency", "principal": 5000}},
        )],
        confidence=0.9,
    ))
    assert out is not None
    assert ledger.turn_decision == "handoff_agent"
    assert seeded == {"api": "submit_my_loan", "slots": {"loan_type": "emergency", "principal": 5000}}
    rows = list(getattr(ledger.execution, "completed_tools", None) or [])
    assert rows[0]["tool_args"] == {"api_name": "submit_my_loan", "body": seeded["slots"]}
    assert "chat_no_host_mutation" in rows[0]["guardrail_flags"]
    assert not seen["tool_calls"], "Chat never runs a write"
    assert not _fell_through(ledger)


def test_agent_dial_write_handoff_goes_to_the_planner(turn, monkeypatch):
    called = {}

    async def planner(self, **kwargs):
        called.update(kwargs)
        return SimpleNamespace(text="Here is a draft."), kwargs["ledger"]

    monkeypatch.setattr(_Runner, "_try_plan_dial_process_plan", planner)
    out, ledger, _ = turn(
        Decision(commands=[Command(op="handoff_agent", process_id="submit_my_loan")], confidence=0.9),
        surface="agent", process_mode="agent",
    )
    assert out is not None and called.get("brief") == "hi"
    assert not _fell_through(ledger)


def test_agent_dial_plan_decision_goes_to_the_planner(turn, monkeypatch):
    called = {}

    async def planner(self, **kwargs):
        called.update(kwargs)
        return SimpleNamespace(text="Here is a draft."), kwargs["ledger"]

    monkeypatch.setattr(_Runner, "_try_plan_dial_process_plan", planner)
    out, _, _ = turn(
        Decision(commands=[Command(op="handoff_agent", process_id="plan")], confidence=0.9),
        surface="agent", process_mode="agent",
    )
    assert out is not None
    assert called.get("brief") == "hi"
