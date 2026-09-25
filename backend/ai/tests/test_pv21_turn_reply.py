"""A read turn answers the message it was given (conv c5801082, 2026-09-24 22:37).

Three different messages ("pie charts", "i told you pie", "what ?") got the
same fixed template and bar charts. The named shape is a typed Decision
field, a turn no restater covers gets prose written for its message, a
follow-up re-renders the last view without a host read, and a failed stage
says so instead of showing the template (ADR-0053).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from ai.engine.cognition.state_store import ConversationState, bound_view, render_state_block
from ai.engine.cognition.turn.decision import Command, Decision, parse_decision
from ai.engine.cognition.turn.pipeline_v21 import act_on_decision, rows_envelope, speak_turn

_GAP = "99.8% of employees have no 'gender' recorded — this distribution is incomplete."
_ROWS = [{
    "tool_name": "call_host_api",
    "tool_args": {"api_name": "analyze_employees", "query_params": {"dimension": "gender"}},
    "result": {
        "dimension": "gender",
        "total": 555,
        "suggested_chart_type": "bar",
        "breakdown": [
            {"label": "(blank)", "count": 554, "pct": 99.8},
            {"label": "female", "count": 1, "pct": 0.2},
        ],
        "caveats": [_GAP],
    },
}]


def _decision(chart: str = "", reason: str = "", op: str = "call_tool") -> Decision:
    return Decision(
        commands=[Command(op=op, name="analyze_employees", render="chart", chart=chart)],
        reason=reason,
    )


def test_chart_shape_is_a_typed_field():
    d = parse_decision({"commands": [
        {"op": "call_tool", "name": "a", "render": "chart", "chart": "pie"},
    ], "language": "en", "confidence": 0.9})
    assert d.commands[0].chart == "pie"
    bad = parse_decision({"commands": [
        {"op": "call_tool", "name": "a", "chart": "donut"},
    ], "language": "en", "confidence": 0.9})
    assert bad.commands[0].chart == ""


def test_named_pie_is_drawn_even_when_the_host_suggests_bar():
    env = rows_envelope(_ROWS, render="chart", chart="pie")
    assert env["charts"][0]["chart_type"] == "pie"
    assert any("most of the total" in c["text"] for c in env["caveats"])
    plain = rows_envelope(_ROWS, render="chart")
    assert plain["charts"][0]["chart_type"] == "bar"


def test_host_data_gap_caveat_reaches_the_reply():
    env = rows_envelope(_ROWS, render="chart")
    assert any(c["text"] == _GAP for c in env["caveats"])


def _stub_synth(monkeypatch, headline: str = "", prose: list[str] | None = None, *, raises=None):
    from ai.envelope import AnswerEnvelope

    seen = {"calls": 0}

    async def fake(**kwargs):
        seen["calls"] += 1
        seen.update(kwargs)
        if raises is not None:
            raise raises
        return AnswerEnvelope(headline=headline, prose=prose or [])

    monkeypatch.setattr("ai.envelope_service.synthesize_envelope", fake)
    return seen


def test_reply_is_written_for_this_message(monkeypatch):
    seen = _stub_synth(monkeypatch, "Gender is almost all unrecorded", [
        "Only 1 of 555 employees has a gender on file, so the split says more about the data than the people.",
        "About 90 percent are in one site.",
    ])
    text, env, degraded = asyncio.run(speak_turn(
        _decision("pie", reason="user repeats that they asked for a pie"), _ROWS,
        text="", user_message="i told you pie", instance_id="i", conversation_id="c",
    ))
    assert degraded is None
    assert seen["strict"] is True
    assert "i told you pie" in seen["user_message"]
    assert "Understood as" in seen["user_message"]
    assert text.startswith("Gender is almost all unrecorded")
    assert "90 percent" not in text
    assert env["charts"][0]["chart_type"] == "pie"
    assert env["tables"]


def test_writer_failure_is_said_not_templated(monkeypatch):
    from ai.envelope_service import FALLBACK_HEADLINE, EnvelopeWriteError

    _stub_synth(monkeypatch, raises=EnvelopeWriteError("invalid_output"))
    text, env, degraded = asyncio.run(speak_turn(
        _decision(), _ROWS, text="", user_message="what ?", instance_id="i", conversation_id="c",
    ))
    assert degraded is not None and degraded.to_dict() == {"stage": "write", "cause": "invalid_output"}
    assert FALLBACK_HEADLINE not in text
    assert "could not write the summary" in text
    assert env["tables"] and env["charts"]
    assert any("degraded: write (invalid_output)" in c["text"] for c in env["caveats"])


def test_all_ungrounded_prose_is_a_degradation(monkeypatch):
    _stub_synth(monkeypatch, "Headcount", ["There are 9999 people."])
    text, _, degraded = asyncio.run(speak_turn(
        _decision(), _ROWS, text="", user_message="how many", instance_id="i", conversation_id="c",
    ))
    assert degraded is not None and degraded.cause == "ungrounded"
    assert "9999" not in text


def test_strict_writer_raises_instead_of_templating(monkeypatch):
    import pytest

    from ai.envelope_service import EnvelopeWriteError, synthesize_envelope

    with pytest.raises(EnvelopeWriteError) as exc:
        asyncio.run(synthesize_envelope(
            instance_id="i", conversation_id="c", user_message="x", usable_tools=[], strict=True,
        ))
    assert exc.value.cause == "no_rows"


def test_a_restated_read_is_not_rewritten(monkeypatch):
    async def boom(**kwargs):
        raise AssertionError("narration ran over a restated read")

    monkeypatch.setattr("ai.envelope_service.synthesize_envelope", boom)
    text, _, degraded = asyncio.run(speak_turn(
        _decision(), _ROWS, text="Your balance is 12 days.", user_message="balance",
        instance_id="i", conversation_id="c",
    ))
    assert text == "Your balance is 12 days."
    assert degraded is None


def test_a_read_turn_remembers_its_view(monkeypatch):
    _stub_synth(monkeypatch, "Gender", ["Only 1 of 555 has a gender on file."])
    state = ConversationState()
    asyncio.run(speak_turn(
        _decision(), _ROWS, text="", user_message="gender split",
        instance_id="i", conversation_id="c", state=state,
    ))
    assert state.last_view["apis"] == ["analyze_employees"]
    assert state.last_view["tables"] and state.last_view["charts"]
    restored = ConversationState.from_dict(state.to_dict())
    assert restored.last_view == state.last_view
    assert "Last view" in render_state_block(restored)


def test_follow_up_renders_the_last_view_without_a_host_read(monkeypatch):
    seen = _stub_synth(monkeypatch, "Same split as a pie", ["554 records have no gender on file."])
    state = ConversationState()
    state.last_view = bound_view({
        "turn": 1, "apis": ["analyze_employees"],
        **{k: v for k, v in rows_envelope(_ROWS, render="chart").items() if k in {"tables", "charts", "caveats"}},
    })

    async def no_read(name, args):
        raise AssertionError("continue on a stored view read the host again")

    follow = _decision("pie", op="continue")
    rows: list[dict] = []
    reply = asyncio.run(act_on_decision(
        follow, execute_tool=no_read, user_message="what ?", state=state, executed=rows,
    ))
    assert reply is None and rows == []
    text, env, degraded = asyncio.run(speak_turn(
        follow, rows, text=reply, user_message="what ?",
        instance_id="i", conversation_id="c", state=state,
    ))
    assert degraded is None
    assert seen["calls"] == 1
    assert text.startswith("Same split as a pie")
    assert env["charts"][0]["chart_type"] == "pie"
    assert any(c["text"] == _GAP for c in env["caveats"])


def test_view_is_bounded():
    table = {"title": "t", "columns": ["a"], "rows": [[i] for i in range(100)]}
    view = bound_view({"turn": 2, "tables": [table] * 9, "charts": []})
    assert len(view["tables"]) == 3
    assert len(view["tables"][0]["rows"]) == 20
    assert bound_view({"tables": [], "charts": []}) == {}


def test_failed_understanding_answers_with_a_typed_error():
    from ai.engine.cognition.turn.degradation import Degradation
    from ai.engine.cognition.turn.runner_surfaces import _degraded_reply

    ledger = SimpleNamespace(decision_signals=[], final_response="", turn_decision="")
    state = ConversationState(language="ar")
    response, _ = _degraded_reply(ledger, Degradation("understand", "malformed_decision"), state, "v21")
    assert "تعذّر" in response.text
    assert {"gate": "degraded", "fired": True, "stage": "understand",
            "cause": "malformed_decision"} in ledger.decision_signals
    assert response.envelope["caveats"][0]["level"] == "warning"
    assert _degraded_reply(ledger, Degradation("act", "act_error"), state, "shadow") is None
