"""Pulse 2.1 understand prompt + dialogue-act Decision ops."""
from __future__ import annotations

import asyncio
import json

import pytest

from ai.engine.cognition.state_store import ConversationState
from ai.engine.cognition.turn.decision import parse_decision, validate_decision
from ai.engine.cognition.turn.pipeline_v21 import act_on_decision
from ai.engine.cognition.turn.understand import (
    build_understand_system_prompt,
    understand_turn,
)


def test_understand_prompt_includes_state_block():
    state = ConversationState(
        slots={"days": 3},
        open_question={"text": "Should I fetch your leave balance?", "asked_turn": 2},
        last_results=[
            {
                "turn": 1,
                "tool": "call_host_api",
                "api": "get_my_leave_balance",
                "digest": "call_host_api get_my_leave_balance: remaining=6",
            }
        ],
    )
    prompt = build_understand_system_prompt(
        catalog_lines=["- get_my_leave_balance: remaining days"],
        state=state,
        user_info={"audience": ["ess"], "display_name": "Bilal"},
        instance_config={"persona": "You assist Nibras employees."},
    )
    assert "CONVERSATION STATE" in prompt
    assert "Should I fetch your leave balance?" in prompt
    assert "remaining=6" in prompt
    assert "emit confirm" in prompt
    assert "emit continue" in prompt.lower() or "emit continue" in prompt
    assert "Emit emit_decision only" in prompt


def test_confirm_op_parses():
    decision = parse_decision(
        {
            "commands": [{"op": "confirm"}],
            "language": "en",
            "confidence": 0.9,
        }
    )
    assert decision is not None
    assert decision.commands[0].op == "confirm"


def test_validate_downgrades_confirm_without_pending_question():
    decision = parse_decision(
        {
            "commands": [{"op": "confirm"}],
            "language": "en",
            "confidence": 0.9,
        }
    )
    checked = validate_decision(decision, surface="chat", state=ConversationState())
    assert checked.commands[0].op == "clarify"


def test_validate_allows_confirm_with_pending_question():
    decision = parse_decision(
        {
            "commands": [{"op": "confirm"}],
            "language": "en",
            "confidence": 0.9,
        }
    )
    state = ConversationState(
        open_question={
            "text": "Fetch leave balance?",
            "confirm": {"op": "call_tool", "api": "get_my_leave_balance"},
        }
    )
    checked = validate_decision(decision, surface="chat", state=state)
    assert checked.commands[0].op == "confirm"


def test_act_on_decision_confirm_executes_stored_api():
    executed: dict = {}

    async def execute_tool(name: str, args: dict):
        executed["name"] = name
        executed["args"] = args
        return json.dumps([{"leave_type": "annual", "entitled": 20, "remaining": 6}])

    state = ConversationState(
        open_question={
            "text": "Should I check your balance?",
            "confirm": {"op": "call_tool", "api": "get_my_leave_balance"},
        }
    )
    decision = parse_decision(
        {
            "commands": [{"op": "confirm"}],
            "language": "en",
            "confidence": 1.0,
        }
    )
    text = asyncio.run(
        act_on_decision(
            decision,
            execute_tool=execute_tool,
            user_message="yes",
            state=state,
        )
    )
    assert executed["name"] == "get_my_leave_balance"
    assert text and "6" in text


def test_act_on_decision_continue_reissues_last_api():
    executed: dict = {}

    async def execute_tool(name: str, args: dict):
        executed["name"] = name
        return json.dumps([{"leave_type": "annual", "entitled": 20, "remaining": 4}])

    state = ConversationState(
        last_results=[
            {
                "turn": 1,
                "tool": "call_host_api",
                "api": "get_my_leave_balance",
                "digest": "remaining=4",
            }
        ]
    )
    decision = parse_decision(
        {
            "commands": [{"op": "continue"}],
            "language": "en",
            "confidence": 0.8,
        }
    )
    text = asyncio.run(
        act_on_decision(
            decision,
            execute_tool=execute_tool,
            user_message="is that for me?",
            state=state,
        )
    )
    assert executed["name"] == "get_my_leave_balance"
    assert text


def test_understand_turn_passes_state_to_validation(monkeypatch: pytest.MonkeyPatch):
    seen: dict = {}

    def _capture_validate(decision, **kwargs):
        seen.update(kwargs)
        return decision

    monkeypatch.setattr(
        "ai.engine.cognition.turn.understand.validate_decision",
        _capture_validate,
    )

    state = ConversationState(open_question={"text": "Which one?"})

    async def complete(**kwargs):
        return {
            "tool_calls": [
                {
                    "function": {
                        "name": "emit_decision",
                        "arguments": '{"commands":[{"op":"confirm"}],"language":"en","confidence":0.5}',
                    }
                }
            ]
        }

    asyncio.run(
        understand_turn(
            complete=complete,
            messages=[{"role": "user", "content": "yes"}],
            state=state,
        )
    )
    assert seen.get("state") is state
