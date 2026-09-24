"""PV21-Q1 — tool_choice and strict_tools plumbing for route_chat."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from ai.engine.core.config import get_settings
from ai.engine.llm.tool_choice import apply_strict, normalize_tool_choice


# ── normalize_tool_choice ───────────────────────────────────────────────────


def test_normalize_none_and_empty():
    assert normalize_tool_choice(None) is None
    assert normalize_tool_choice("") is None


def test_normalize_auto_and_required():
    assert normalize_tool_choice("auto") == "auto"
    assert normalize_tool_choice("required") == "required"


def test_normalize_function_name_short_form():
    assert normalize_tool_choice({"name": "foo"}) == {
        "type": "function",
        "function": {"name": "foo"},
    }


def test_normalize_function_name_canonical_form():
    assert normalize_tool_choice(
        {"type": "function", "function": {"name": "bar", "extra": 1}}
    ) == {
        "type": "function",
        "function": {"name": "bar"},
    }


def test_normalize_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_tool_choice("none")
    with pytest.raises(ValueError):
        normalize_tool_choice({"type": "function"})


# ── apply_strict ────────────────────────────────────────────────────────────


def test_apply_strict_noop_when_not_strict():
    tools = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
    assert apply_strict(tools, False) is tools
    assert apply_strict(None, True) is None


def test_apply_strict_does_not_mutate_input():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    original = tools[0]["function"].copy()
    out = apply_strict(tools, True)
    assert out is not tools
    assert "strict" not in tools[0]["function"]
    assert tools[0]["function"] == original
    assert out[0]["function"]["strict"] is True
    assert out[0]["function"]["parameters"]["additionalProperties"] is False


# ── route_chat kwargs (no network) ──────────────────────────────────────────


class _FakeMessage:
    content = "ok"
    tool_calls = None


class _FakeChoice:
    def __init__(self):
        self.message = _FakeMessage()
        self.finish_reason = "stop"


class _FakeUsage:
    prompt_tokens = 1
    completion_tokens = 1
    total_tokens = 2


class _FakeResponse:
    def __init__(self):
        self.choices = [_FakeChoice()]
        self.usage = _FakeUsage()


@pytest.fixture
def cfg():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def route_patches(monkeypatch):
    captured: dict = {}

    async def _fake_create_completion(client, **kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(
        "ai.engine.llm.provider.create_completion", _fake_create_completion
    )
    monkeypatch.setattr("ai.engine.llm.provider.get_llm_client", lambda: object())
    monkeypatch.setattr(
        "ai.engine.llm.router._check_budget", AsyncMock(return_value=0.0)
    )
    monkeypatch.setattr("ai.engine.llm.router._log_call", AsyncMock())
    return captured


def _sample_tools():
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


@pytest.mark.asyncio
async def test_route_chat_omits_tool_choice_by_default(route_patches, cfg):
    from ai.engine.llm.router import route_chat

    result = await route_chat(
        task="chat",
        instance_id="inst-1",
        conversation_id="conv-1",
        messages=[{"role": "user", "content": "hi"}],
        db=object(),
    )

    assert "tool_choice" not in route_patches
    assert result["tool_choice"] is None


@pytest.mark.asyncio
async def test_route_chat_passes_required_tool_choice(route_patches, cfg):
    from ai.engine.llm.router import route_chat

    tools = _sample_tools()
    result = await route_chat(
        task="chat",
        instance_id="inst-1",
        conversation_id="conv-2",
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        tool_choice="required",
        db=object(),
    )

    assert route_patches["tool_choice"] == "required"
    assert result["tool_choice"] == "required"


@pytest.mark.asyncio
async def test_route_chat_strict_tools_copies_without_mutating(route_patches, cfg):
    from ai.engine.llm.router import route_chat

    tools = _sample_tools()
    result = await route_chat(
        task="chat",
        instance_id="inst-1",
        conversation_id="conv-3",
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        strict_tools=True,
        db=object(),
    )

    sent = route_patches["tools"]
    assert sent is not tools
    assert sent[0]["function"]["strict"] is True
    assert sent[0]["function"]["parameters"]["additionalProperties"] is False
    assert "strict" not in tools[0]["function"]
    assert result["tool_choice"] is None
