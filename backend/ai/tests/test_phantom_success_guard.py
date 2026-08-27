"""Regression (2026-08-27) — phantom-success guards.

A hallucinated ``create_dq_rule`` step staged nothing (the tool returned null
output), yet the critic/step/run all read "completed". Two independent guards
now prevent this:

1. The execute witness fails honestly when a confirmation-gated tool returns
   null/empty output.
2. The ReActLoop marks the step failed when a confirmation tool's output
   carries neither ``requires_confirmation`` nor ``error``.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ai.engine.agent.plugins as plugins_mod
from ai.engine.cognition.turn.execute import _execute_single_tool
from ai.plugins import register_builtin_plugins


@pytest.fixture(autouse=True)
def _reset_plugins():
    original = list(plugins_mod._PLUGINS)
    yield
    plugins_mod._PLUGINS[:] = original


# ── Fix 1 — execute witness null-output guard ─────────────────────────────


def test_confirmation_tool_null_output_fails_execute():
    """A confirmation tool returning None must fail honestly, not "null"."""
    register_builtin_plugins()

    async def _null_executor(*args, **kwargs):
        return None

    tool_call = {
        "id": "call-1",
        "function": {
            "name": "create_dq_rule",
            "arguments": json.dumps({"rule_type": "general"}),
        },
    }

    async def _run():
        with patch(
            "ai.engine.agent.tools.get_tool_executors",
            new=AsyncMock(return_value={"create_dq_rule": _null_executor}),
        ):
            return await _execute_single_tool(tool_call)

    result = asyncio.run(_run())
    assert result is not None
    assert result["error"], result
    assert "returned no output" in result["error"]


def test_readonly_tool_null_output_not_guarded():
    """The null-output guard is scoped to confirmation tools only.

    A read-only tool (requires_confirmation=False) returning None must NOT be
    force-failed here — it still flows through the normal serialize path.
    """
    register_builtin_plugins()

    async def _null_executor(*args, **kwargs):
        return None

    tool_call = {
        "id": "call-2",
        "function": {
            "name": "search_knowledge",
            "arguments": json.dumps({"query": "carbon"}),
        },
    }

    async def _run():
        with patch(
            "ai.engine.agent.tools.get_tool_executors",
            new=AsyncMock(return_value={"search_knowledge": _null_executor}),
        ):
            return await _execute_single_tool(tool_call)

    result = asyncio.run(_run())
    # Read-only tool: no error, result serialized to "null" (pre-existing path).
    assert result["error"] is None
    assert result["result"] == "null"


# ── Fix 2 — planner schema validation ──────────────────────────────────────


def test_planner_strips_invalid_tool_args():
    """A hallucinated rule_type must drop the tool call, not emit it."""
    from ai.engine.cognition.plan.planner import PlanStep, _strip_invalid_tool_args

    register_builtin_plugins()

    step = PlanStep(
        step_id=0, intent="Create a DQ rule", tool_name="create_dq_rule",
        tool_args={"rule_type": "general", "level": "field"},
        depends_on=[], agent_role="worker",
    )
    _strip_invalid_tool_args([step])
    assert step.tool_name is None
    assert step.tool_args == {}


def test_planner_keeps_valid_tool_args():
    """Structurally valid args must NOT be stripped."""
    from ai.engine.cognition.plan.planner import PlanStep, _strip_invalid_tool_args

    register_builtin_plugins()

    step = PlanStep(
        step_id=0, intent="Create a DQ rule", tool_name="create_dq_rule",
        tool_args={
            "name": "email not null",
            "rule_type": "not_null",
            "level": "field",
        },
        depends_on=[], agent_role="worker",
    )
    _strip_invalid_tool_args([step])
    assert step.tool_name == "create_dq_rule"
    assert step.tool_args["rule_type"] == "not_null"


# ── Fix 3 — ReActLoop mutation-output validation ──────────────────────────


class _FakeDraft:
    def __init__(self, text="staged", tool_calls=None):
        self.text = text
        self.tool_calls = tool_calls or []


class _FakeCritic:
    def __init__(self, verdict="pass", flags=None):
        self.verdict = verdict
        self.flags = flags or []


class _FakeExecution:
    def __init__(self, completed_tools=None):
        self.completed_tools = completed_tools or []


async def _run_step_with_tool_output(completed_tools, tool_name="create_dq_rule"):
    """Run the real ReActLoop._execute_step with a mocked ExecuteWitness that
    reports the given ``completed_tools`` for a confirmation tool step."""
    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import PlanStep
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    register_builtin_plugins()

    loop = ReActLoop.__new__(ReActLoop)
    loop._build_step_prompt = MagicMock(return_value="prompt")  # noqa: SLF001

    dw = AsyncMock()
    async def _draft(**kwargs):
        return _FakeDraft()
    dw.draft = _draft

    cw = AsyncMock()
    async def _review(**kwargs):
        return _FakeCritic()
    cw.review = _review

    ex = AsyncMock()
    async def _execute(**kwargs):
        return _FakeExecution(completed_tools=completed_tools)
    ex.execute = _execute

    step = PlanStep(
        step_id=0, intent="Create a DQ rule", tool_name=tool_name,
        tool_args={"rule_type": "general"}, depends_on=[], agent_role="worker",
    )

    return await loop._execute_step(  # noqa: SLF001
        step=step, dw=dw, cw=cw, ex=ex,
        instance_id="i", conversation_id="c", user_message="u",
        system_prompt="sp", conversation_history=None, instance_config=None,
        user_info=None, retrieval=RetrievalResult(), progress_callback=None,
        stream_callback=None, dry_run=False, confirmation_token=None,
        step_contexts={}, agent_role="worker", plan_source="llm_decompose",
    )


@pytest.mark.asyncio
async def test_confirmation_tool_null_output_fails_step():
    """Null output from a confirmation tool must mark the step failed."""
    result = await _run_step_with_tool_output(
        [{"tool_name": "create_dq_rule", "result": None}]
    )
    assert result.error, result
    assert "returned no output" in result.error
    assert result.critic_verdict == "veto"


@pytest.mark.asyncio
async def test_confirmation_tool_missing_keys_fails_step():
    """A confirmation tool returning neither confirmation nor error fails."""
    result = await _run_step_with_tool_output(
        [{"tool_name": "create_dq_rule", "result": '{"proposed_rule": "x"}'}]
    )
    assert result.error, result
    assert "neither a confirmation nor an error" in result.error
    assert result.critic_verdict == "veto"


@pytest.mark.asyncio
async def test_confirmation_tool_valid_proposal_not_failed():
    """A proper ``requires_confirmation`` proposal must NOT be failed.

    The existing consent gate (P1.3) handles the pause; this guard must not
    misfire on a healthy staged proposal.
    """
    proposal = json.dumps({
        "requires_confirmation": True,
        "execution_id": "ex-1",
        "proposed_rule": {},
    })
    result = await _run_step_with_tool_output(
        [{"tool_name": "create_dq_rule", "result": proposal}]
    )
    # The consent gate paused the step, not the null-output guard failing it.
    assert result.paused is True
    assert result.error is None
    assert result.confirmation_token is not None
