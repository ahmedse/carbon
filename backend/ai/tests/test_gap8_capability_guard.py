"""Tests for the capability-tool salience guard (GAP-M7).

``list_my_capabilities`` must only be surfaced when the user explicitly asks
about capabilities/access (or on an identity-domain turn), never as a
confusion fallback.

All assertions are domain-agnostic.
"""
import pytest
from ai.engine.cognition.turn.runner import (
    _is_capability_query,
    _filter_draft_tools,
    TurnPipelineRunner,
)


# ── _is_capability_query ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    [
        "what can you do",
        "what do you have access to",
        "what features do you have",
        "show me capabilities",
        "what are your capabilities",
        "what are you able to do",
        "what can I use",
    ],
)
def test_matches_capability_queries(text):
    assert _is_capability_query(text), text


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "what is a table",
        "explain GHG",
        "please analyze the Dataset",
        "show me the report",
        "",
    ],
)
def test_rejects_non_capability_text(text):
    assert not _is_capability_query(text), text


def test_capability_query_none_handling():
    assert not _is_capability_query(None)


# ── _filter_draft_tools ──────────────────────────────────────────────────────

def _draft_tools_with_capability():
    return [
        {"function": {"name": "list_my_capabilities"}},
        {"function": {"name": "search_knowledge"}},
        {"function": {"name": "learn_fact"}},
    ]


def _names(tools):
    return {d.get("function", {}).get("name") for d in tools}


def test_filter_excludes_capability_tool_for_non_capability_message():
    tools = _draft_tools_with_capability()
    filtered = _filter_draft_tools(tools, "what is a table", "general")
    names = _names(filtered)
    assert "list_my_capabilities" not in names
    assert "search_knowledge" in names
    assert "learn_fact" in names


def test_filter_includes_capability_tool_for_capability_message():
    tools = _draft_tools_with_capability()
    filtered = _filter_draft_tools(tools, "what can you do", "general")
    assert "list_my_capabilities" in _names(filtered)


def test_filter_includes_capability_tool_for_identity_domain():
    tools = _draft_tools_with_capability()
    filtered = _filter_draft_tools(tools, "hello there", "identity")
    assert "list_my_capabilities" in _names(filtered)


def test_filter_returns_none_for_none_tools():
    assert _filter_draft_tools(None, "what can you do", "general") is None


def test_filter_does_not_drop_other_tools():
    tools = _draft_tools_with_capability()
    filtered = _filter_draft_tools(tools, "yes", "general")
    assert "search_knowledge" in _names(filtered)
    assert "learn_fact" in _names(filtered)


# ── _draft_tools allow set ───────────────────────────────────────────────────

def test_draft_tools_allow_set_includes_memory_tools():
    runner = TurnPipelineRunner(executor=object())
    names = _names(runner._draft_tools or [])
    assert "learn_fact" in names
    assert "forget_fact" in names


def test_draft_tools_none_without_executor():
    runner = TurnPipelineRunner(executor=None)
    assert runner._draft_tools is None
