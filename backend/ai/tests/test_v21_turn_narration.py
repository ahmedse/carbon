"""ADR-0054 — a v21 turn narrates itself: the rationale first, then each read.

Before this, a v21 turn sent nothing to the progress channel until the reply
was ready, so the thinking panel stayed empty on the fastest path.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from ai.engine.cognition.turn.decision import Command, Decision
from ai.engine.cognition.turn.runner_surfaces import SoftSurfacesMixin
from ai.engine.cognition.turn.witnesses import TurnLedger

_CATALOG = [
    {
        "name": "analyze_employees",
        "description": "Workforce breakdown by a dimension.",
        "kind": "read",
    },
    {
        "name": "list_departments",
        "description": "Departments and their headcount.",
        "kind": "read",
    },
]


class _Runner(SoftSurfacesMixin):
    """Just enough of the turn runner to drive the v21 understand path."""

    def __init__(self):
        self.executor = SimpleNamespace()
        self.knowledge_store = None
        self.rows: list[tuple[str, dict]] = []

    async def _record_understand(self, **kwargs):
        return None

    async def _write_ledger_row(self, *args, **kwargs):
        self.rows.append((args[4], args[6]))
        return None


class _FakeWitness:
    def __init__(self, **kwargs):
        pass

    async def execute(self, **kwargs):
        return SimpleNamespace(completed_tools=[{
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "analyze_employees"},
            "result": {"dimension": "gender", "total": 555, "breakdown": []},
        }])


@pytest.fixture
def turn(monkeypatch):
    """Runs one v21 turn with a decided read and collects the progress lines."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    monkeypatch.setattr(
        "ai.engine.cognition.turn.execute.ExecuteWitness", _FakeWitness,
    )

    async def spoken(decision, executed, **kwargs):
        return "555 people, and gender is blank for almost all of them.", None, None

    monkeypatch.setattr("ai.engine.cognition.turn.pipeline_v21.speak_turn", spoken)

    def run(decision: Decision):
        told: list[str] = []

        async def understood(**kwargs):
            return decision

        monkeypatch.setattr(
            "ai.engine.cognition.turn.understand.understand_turn", understood,
        )

        async def progress(line):
            told.append(line)

        runner = _Runner()
        out = asyncio.run(runner._try_v21_understand(
            user_message="split the workforce by gender",
            conversation_history=[],
            ledger=TurnLedger(),
            turn_id="t-narrate",
            instance_id="nibras",
            conversation_id="c-narrate",
            host_user_id=None,
            instance_config={"api_catalog": _CATALOG},
            t0=0.0,
            surface="chat",
            progress_callback=progress,
        ))
        return told, out, runner

    return run


def test_rationale_comes_before_the_reads_it_explains(turn):
    told, out, _ = turn(Decision(
        commands=[Command(op="call_tool", name="analyze_employees")],
        reason="You asked for the split by gender, so I will read the workforce breakdown.",
        confidence=0.9,
    ))
    assert told, "a v21 turn narrated nothing"
    assert told[0].startswith("You asked for the split")
    assert len(told) > 1, "the read itself was never narrated"
    assert "analyze" in told[1].lower() or "workforce" in told[1].lower()
    assert out is not None


def test_every_distinct_read_gets_its_own_line(turn):
    told, _, _ = turn(Decision(
        commands=[
            Command(op="call_tool", name="analyze_employees"),
            Command(op="call_tool", name="list_departments"),
            # The same read again is one read, so it is narrated once.
            Command(op="call_tool", name="analyze_employees"),
        ],
        reason="Two cuts of the same population.",
        confidence=0.9,
    ))
    reads = told[1:]
    assert len(reads) == 2
    assert all(line.strip() for line in reads)
    assert reads[0] != reads[1]


def test_narration_never_leaks_tool_ids_or_code(turn):
    told, _, _ = turn(Decision(
        commands=[Command(op="call_tool", name="analyze_employees")],
        reason="Reading it now — `call_host_api` with the gender dimension.",
        confidence=0.9,
    ))
    assert "`" not in told[0]
    assert "call_host_api" not in told[0]


def test_a_failing_progress_channel_does_not_break_the_read(monkeypatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    monkeypatch.setattr(
        "ai.engine.cognition.turn.execute.ExecuteWitness", _FakeWitness,
    )

    async def spoken(decision, executed, **kwargs):
        return "Answered anyway.", None, None

    monkeypatch.setattr("ai.engine.cognition.turn.pipeline_v21.speak_turn", spoken)

    async def understood(**kwargs):
        return Decision(
            commands=[Command(op="call_tool", name="analyze_employees")],
            reason="Reading the breakdown.",
            confidence=0.9,
        )

    monkeypatch.setattr(
        "ai.engine.cognition.turn.understand.understand_turn", understood,
    )

    def broken(_line):
        raise RuntimeError("the socket closed")

    out = asyncio.run(_Runner()._try_v21_understand(
        user_message="split the workforce by gender",
        conversation_history=[],
        ledger=TurnLedger(),
        turn_id="t-broken",
        instance_id="nibras",
        conversation_id="c-broken",
        host_user_id=None,
        instance_config={"api_catalog": _CATALOG},
        t0=0.0,
        surface="chat",
        progress_callback=broken,
    ))
    assert out is not None
    assert out[0].text == "Answered anyway."


def test_the_rationale_is_kept_on_the_reply_and_in_the_ledger(turn):
    _, out, runner = turn(Decision(
        commands=[Command(op="call_tool", name="analyze_employees")],
        reason="You asked for the split by gender.",
        confidence=0.9,
    ))
    assert out[0].reasoning_steps[0].startswith("You asked for the split")
    reasoning = [payload for stage, payload in runner.rows if stage == "reasoning"]
    assert reasoning and reasoning[0]["rationale"].startswith("You asked for the split")
