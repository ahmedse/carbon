"""Declared provider reasoning and the understand call's malformed repair (ADR-0057)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from ai.engine.core.config import get_settings
from ai.engine.cognition.turn.decision import decision_or_cause
from ai.engine.cognition.turn.understand import read_decision, understand_turn
from ai.engine.llm.provider import reasoning_mode


# ── declared modes ───────────────────────────────────────────────────────────


def test_anthropic_reasons_by_effort_and_never_under_a_forced_tool():
    mode = reasoning_mode("anthropic/claude-haiku-4.5", "https://api.example.test/v1")
    assert mode is not None
    assert mode.body == {"reasoning_effort": "low"}
    assert mode.forced_tool is False
    assert mode.temperature == 1.0


def test_deepseek_reasons_by_thinking_flag():
    mode = reasoning_mode("deepseek-flash", "https://api.deepseek.com/v1")
    assert mode is not None
    assert mode.body == {"thinking": {"type": "enabled"}}


def test_undeclared_model_has_no_reasoning_mode():
    assert reasoning_mode("gpt-4o-mini", "https://api.example.test/v1") is None


# ── route_chat applies the declared mode ─────────────────────────────────────


class _Message:
    def __init__(self, trace: str = ""):
        self.content = None
        self.tool_calls = None
        self.reasoning_content = trace


class _Choice:
    def __init__(self, trace: str = ""):
        self.message = _Message(trace)
        self.finish_reason = "tool_calls"


class _Usage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


class _Response:
    def __init__(self, trace: str = ""):
        self.choices = [_Choice(trace)]
        self.usage = _Usage()


@pytest.fixture
def sent(monkeypatch):
    captured: dict = {}

    async def _fake(client, **kwargs):
        captured.update(kwargs)
        return _Response("First I weigh what the user asked.")

    get_settings.cache_clear()
    monkeypatch.setattr("ai.engine.llm.provider.create_completion", _fake)
    monkeypatch.setattr("ai.engine.llm.provider.get_llm_client", lambda: object())
    monkeypatch.setattr("ai.engine.llm.router._check_budget", AsyncMock(return_value=0.0))
    monkeypatch.setattr("ai.engine.llm.router._log_call", AsyncMock())
    yield captured
    get_settings.cache_clear()


_TOOLS = [{"type": "function", "function": {"name": "emit_decision", "parameters": {"type": "object"}}}]


async def _route(**kw):
    from ai.engine.llm.router import route_chat

    return await route_chat(
        task="cognition", instance_id="i", conversation_id="c",
        messages=[{"role": "user", "content": "hi"}], tools=_TOOLS,
        tool_choice={"name": "emit_decision"}, temperature=0.0, db=object(), **kw,
    )


@pytest.mark.asyncio
async def test_reasoning_relaxes_a_forced_choice_the_mode_cannot_hold(sent):
    result = await _route(model="anthropic/claude-haiku-4.5", reasoning=True)
    assert sent["tool_choice"] == "auto"
    assert sent["extra_body"]["reasoning_effort"] == "low"
    assert sent["temperature"] == 1.0
    assert result["tool_choice"] == "auto"
    assert result["reasoning_text"] == "First I weigh what the user asked."


@pytest.mark.asyncio
async def test_no_reasoning_keeps_the_forced_choice(sent):
    result = await _route(model="anthropic/claude-haiku-4.5")
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "emit_decision"}}
    assert "reasoning_effort" not in (sent.get("extra_body") or {})
    assert result["tool_choice"] == sent["tool_choice"]


@pytest.mark.asyncio
async def test_deepseek_thinking_yields_when_a_tool_is_forced(sent, monkeypatch):
    monkeypatch.setattr(
        "ai.engine.llm.provider.client_for_model",
        lambda model: (object(), "deepseek-flash", "https://api.deepseek.com/v1"),
    )
    result = await _route(model="deepseek-flash", reasoning=True)
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "emit_decision"}}
    assert "thinking" not in (sent.get("extra_body") or {})
    assert result["tool_choice"] == sent["tool_choice"]


def test_deepseek_client_turns_thinking_off_under_another_primary(monkeypatch):
    from ai.engine.llm.provider import _apply_provider_kwargs

    get_settings.cache_clear()
    monkeypatch.setenv("LLM_BASE_URL", "https://api.poe.com/v1")
    try:
        routed = _apply_provider_kwargs({"model": "deepseek-flash"}, "https://api.deepseek.com/v1/")
        primary = _apply_provider_kwargs({"model": "claude-haiku-4.5"}, "https://api.poe.com/v1/")
    finally:
        get_settings.cache_clear()
    assert routed["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "extra_body" not in primary


@pytest.mark.asyncio
async def test_reasoning_on_an_undeclared_model_changes_nothing(sent):
    await _route(model="gpt-4o-mini", reasoning=True)
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "emit_decision"}}
    assert sent["temperature"] == 0.0


# ── malformed emissions are classified, recorded, repaired once ──────────────


def _call(args) -> dict:
    raw = args if isinstance(args, str) else json.dumps(args)
    return {"tool_calls": [{"id": "c1", "function": {"name": "emit_decision", "arguments": raw}}]}


_GOOD = {"commands": [{"op": "answer", "text": "hello"}], "language": "en", "confidence": 0.9}


@pytest.mark.parametrize(
    ("payload", "cause"),
    [
        ("{not json", "not_json"),
        ([], "not_object"),
        ({"commands": '[{"op": "answer"}]'}, "commands_not_list"),
        ({"commands": []}, "no_commands"),
        ({"commands": [{"op": "dance"}]}, "unknown_op"),
        ({"commands": ["answer"]}, "bad_command"),
    ],
)
def test_every_unusable_shape_has_a_cause(payload, cause):
    assert decision_or_cause(payload) == (None, cause)


def test_no_emission_is_its_own_cause():
    decision, cause, head = read_decision({"tool_calls": [], "content": "Sure, here you go"})
    assert decision is None
    assert cause == "no_tool_call"
    assert head == "Sure, here you go"


def _run(results: list[dict]):
    sent: list[list[dict]] = []
    seen: list[tuple[str, str]] = []

    async def complete(*, messages, tools, tool_choice, strict_tools):
        sent.append(list(messages))
        return results[len(sent) - 1]

    decision = asyncio.run(understand_turn(
        complete=complete,
        messages=[{"role": "user", "content": "hi"}],
        on_malformed=lambda cause, head: seen.append((cause, head)),
    ))
    return decision, sent, seen


def test_malformed_emission_is_told_its_cause_and_repaired():
    decision, sent, seen = _run([_call({"commands": '[{"op":"answer"}]'}), _call(_GOOD)])
    assert decision is not None and decision.repaired is True
    assert seen == [("commands_not_list", '{"commands": "[{\\"op\\":\\"answer\\"}]"}')]
    feedback = json.loads(sent[1][-1]["content"])
    assert feedback["status"] == "malformed"
    assert feedback["cause"] == "commands_not_list"


def test_no_emission_is_emitted_again_with_the_same_messages():
    decision, sent, seen = _run([{"tool_calls": [], "content": "chat"}, _call(_GOOD)])
    assert decision is not None
    assert sent[1] == sent[0]
    assert [c for c, _ in seen] == ["no_tool_call"]


def test_one_repair_per_turn_then_undecided():
    bad = _call({"commands": []})
    decision, sent, seen = _run([bad, bad, _call(_GOOD)])
    assert decision is None
    assert len(sent) == 2
    assert [c for c, _ in seen] == ["no_commands", "no_commands"]
