"""Pulse 2.1 Decision, grounding, normalize, catalog rank. No LLM."""
from __future__ import annotations

import pytest

from ai.engine.cognition.catalog_retrieval import rank_tools, select_for_surface
from ai.engine.cognition.turn.force_tool import choice_from_resolution, tool_choice_enabled
from ai.engine.cognition.turn.decision import (
    parse_decision,
    tool_choice_for,
    validate_decision,
)
from ai.engine.cognition.turn.grounding import ungrounded_numbers
from ai.engine.cognition.turn.understand import decision_from_tool_result, understand_mode
from ai.engine.text.normalize import normalize_text
from ai.eval.intelligence_ladder import score_l6, score_l7, score_ladder


def test_parse_and_chat_write_becomes_handoff():
    decision = parse_decision(
        {
            "commands": [{"op": "call_tool", "name": "submit_leave", "args": {}}],
            "language": "ar",
            "confidence": 0.8,
        }
    )
    assert decision is not None
    assert decision.language == "ar"
    checked = validate_decision(decision, surface="chat")
    assert checked.commands[0].op == "handoff_agent"


def test_unknown_tool_clarifies_when_allowlist_set():
    decision = parse_decision(
        {
            "commands": [{"op": "call_tool", "name": "get_my_leave_balance"}],
            "language": "en",
            "confidence": 0.9,
        }
    )
    checked = validate_decision(
        decision, surface="chat", allowed_tools={"list_my_leave"}
    )
    assert checked.commands[0].op == "clarify"


def test_named_tool_choice_only_for_single_call():
    one = parse_decision(
        {
            "commands": [{"op": "call_tool", "name": "get_my_leave_balance"}],
            "language": "en",
            "confidence": 1,
        }
    )
    assert tool_choice_for(one) == {"name": "get_my_leave_balance"}
    two = parse_decision(
        {
            "commands": [
                {"op": "call_tool", "name": "get_my_leave_balance"},
                {"op": "call_tool", "name": "list_my_payslips"},
            ],
            "language": "en",
            "confidence": 1,
        }
    )
    assert tool_choice_for(two) is None


def test_understand_turn_forces_decision_and_blocks_chat_write():
    import asyncio

    from ai.engine.cognition.turn.understand import understand_turn

    seen: dict = {}

    async def complete(**kwargs):
        seen.update(kwargs)
        return {
            "tool_calls": [
                {
                    "function": {
                        "name": "emit_decision",
                        "arguments": '{"commands":[{"op":"call_tool","name":"submit_leave"}],"language":"en","confidence":0.99}',
                    }
                }
            ]
        }

    decision = asyncio.run(
        understand_turn(
            complete=complete,
            messages=[{"role": "user", "content": "submit my leave"}],
            surface="chat",
        )
    )
    assert seen["tool_choice"] == {"name": "emit_decision"}
    assert seen["strict_tools"] is True
    assert decision.commands[0].op == "handoff_agent"


def test_malformed_tool_result_is_none():
    assert decision_from_tool_result({"tool_calls": [], "content": "hello"}) is None


def test_understand_defaults_v21(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PULSE_UNDERSTAND", raising=False)
    assert understand_mode() == "v21"
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    assert understand_mode() == "legacy"
    monkeypatch.setenv("PULSE_UNDERSTAND", "shadow")
    assert understand_mode() == "shadow"
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    assert understand_mode() == "v21"


def test_normalize_hamza_and_digits():
    assert normalize_text("إجازة ٠") == "اجازه 0"
    assert normalize_text("  آآ  ") == "اا"


def test_ungrounded_zero_is_flagged():
    assert ungrounded_numbers("remaining 0 days", [{"results": []}]) == []
    # count 0 is in the payload via empty list length
    assert "12" in ungrounded_numbers("you have 12 days", [{"remaining": 4}])
    from ai.engine.cognition.turn.grounding import strip_ungrounded_numbers
    assert strip_ungrounded_numbers("you have 12 days and 4 left", [{"remaining": 4}]) == "you have days and 4 left"


def test_rank_tools_prefers_description_overlap():
    catalog = [
        {"name": "list_my_leave", "description": "leave requests history", "kind": "history"},
        {"name": "get_my_leave_balance", "description": "remaining leave days balance", "kind": "balance"},
        {"name": "submit_leave", "description": "submit a leave request", "kind": "write"},
    ]
    ranked = rank_tools("what is my leave balance remaining", catalog, k=2)
    assert ranked[0]["name"] == "get_my_leave_balance"
    chat = select_for_surface("submit leave", catalog, surface="chat", k=5)
    assert all(t["kind"] != "write" for t in chat)


def test_tool_choice_on_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PULSE_TOOL_CHOICE", raising=False)
    assert tool_choice_enabled() is True
    monkeypatch.setenv("PULSE_TOOL_CHOICE", "off")
    assert tool_choice_enabled() is False
    monkeypatch.delenv("PULSE_TOOL_CHOICE", raising=False)

    class _C:
        name = "get_my_leave_balance"

    class _R:
        confidence = 0.95
        needs_host_data = True
        candidates = [_C()]

    assert choice_from_resolution(_R()) == {"name": "get_my_leave_balance"}
    monkeypatch.setenv("PULSE_TOOL_CHOICE", "off")
    assert choice_from_resolution(_R()) is None


def test_v2_ladder_unchanged_v21_separate():
    report = score_ladder(lookup_zero_llm=True, write_zero_llm=True)
    ids = [row["id"] for row in report["levels"]]
    assert ids == ["L0", "L1", "L2", "L3", "L4", "L5"]
    v21 = {row["id"]: row["status"] for row in report["v21_levels"]}
    assert set(v21) == {"L6", "L7"}
    # Baseline evidence is not inside the lean ceilings.
    assert score_l7({"staged_exits": 13, "re_compile": 227, "arabic_regex": 53, "runner_lines": 5908, "tool_choice_uses": 0}).status == "missing"
    assert score_l6({}).status == "missing"
