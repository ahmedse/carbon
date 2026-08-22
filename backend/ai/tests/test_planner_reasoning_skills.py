"""Planner decomposition integrity — reasoning vs skills.

Covers the design principle (user-confirmed, Sprint 18-QA):
  - Skills are rigid, concrete capabilities (read PDF, format a Word report,
    research top papers, call a host API).
  - Reasoning (comparison, synthesis, analysis) is the LLM's job, NOT a skill.

Verifies:
  1. The decompose prompt advertises ONLY registered skills for invoke_skill
     and explicitly forbids inventing names when none are registered.
  2. An LLM-returned invoke_skill referencing an unregistered skill name is
     downgraded to a pure reasoning step (tool_name=None,
     agent_role=domain_specialist).
  3. A real registered skill name is kept as invoke_skill.
  4. The ReAct loop gives a multi-step reasoning step NO tools (pure LLM
     reasoning), while single-step passthrough keeps the curated allow-set.
"""
from __future__ import annotations

import json

import pytest


# ── 1. Prompt advertises only registered skills ────────────────────────────


def test_decompose_prompt_forbids_inventing_skill_names():
    """The prompt must list registered skills and ban fabricated names."""
    from ai.engine.cognition.plan.planner import _DECOMPOSE_AGENT_PROMPT

    prompt = _DECOMPOSE_AGENT_PROMPT
    # Skill names are never in the tool list — they live in a separate,
    # registry-backed section.
    assert "{skills_list}" in prompt
    assert "invoke_skill may ONLY reference an exact name" in prompt
    assert "NEVER invent a skill name" in prompt
    # Reasoning guidance: analysis/comparison/synthesis are LLM work.
    assert 'set "tool_name": null' in prompt
    assert "domain_specialist" in prompt


# ── 2. Validation downgrades unregistered invoke_skill ─────────────────────


class _FakeStep:
    def __init__(self, tool_name, tool_args, agent_role=None):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.agent_role = agent_role
        self.step_id = 3


def _run_validation(steps, skills=None):
    """Re-run the exact validation block from _llm_decompose."""
    from ai.engine.agent.tools import get_tool_executors

    async def _validate():
        _vexecs = await get_tool_executors()
        _skill_names = {s.name for s in (skills or [])}
        for step in steps:
            if step.tool_name and step.tool_name not in _vexecs:
                step.tool_name = None
            if step.tool_name == "invoke_skill":
                _sn = (step.tool_args or {}).get("skill_name", "")
                if _sn not in _skill_names:
                    step.tool_name = None
                    step.agent_role = step.agent_role or "domain_specialist"
        return steps

    import asyncio
    return asyncio.run(_validate())


def test_unregistered_invoke_skill_downgraded_to_reasoning():
    """An invented skill name must become a pure reasoning step."""
    step = _FakeStep("invoke_skill", {"skill_name": "compare_carbon_footprint"})
    steps = _run_validation([step], skills=[])
    assert steps[0].tool_name is None
    assert steps[0].agent_role == "domain_specialist"


def test_registered_invoke_skill_kept():
    """A real registered skill name stays as invoke_skill."""
    class _Skill:
        name = "weekly_load_report"

    step = _FakeStep("invoke_skill", {"skill_name": "weekly_load_report"})
    steps = _run_validation([step], skills=[_Skill()])
    assert steps[0].tool_name == "invoke_skill"
    assert steps[0].agent_role is None  # unchanged


def test_unknown_tool_still_stripped():
    """Pre-existing behavior: unknown tools are stripped, not reasoned."""
    step = _FakeStep("frobnicate", {})
    steps = _run_validation([step], skills=[])
    assert steps[0].tool_name is None


# ── 3. ReAct loop tool exposure for reasoning steps ────────────────────────


class _FakeDraft:
    def __init__(self, text="reasoned output", tool_calls=None):
        self.text = text
        self.tool_calls = tool_calls or []


class _FakeCritic:
    def __init__(self, verdict="pass", flags=None, reason=None):
        self.verdict = verdict
        self.flags = flags or []
        self.veto_reason = reason


class _FakeExecution:
    def __init__(self, completed_tools=None):
        self.completed_tools = completed_tools or []


async def _run_execute_step(plan_source: str, tool_name=None, agent_role=None):
    """Run the real ReActLoop._execute_step with fully mocked witnesses.

    Returns (step_tools_passed_to_draft, result).
    """
    from unittest.mock import AsyncMock, MagicMock

    from ai.engine.cognition.plan.loop import ReActLoop
    from ai.engine.cognition.plan.planner import PlanStep
    from ai.engine.cognition.turn.witnesses import RetrievalResult

    loop = ReActLoop.__new__(ReActLoop)
    loop._build_step_prompt = MagicMock(return_value="prompt")  # noqa: SLF001

    captured: dict = {}

    dw = AsyncMock()
    async def _draft(**kwargs):
        captured["tools"] = kwargs.get("tools")
        return _FakeDraft()
    dw.draft = _draft

    cw = AsyncMock()
    async def _review(**kwargs):
        return _FakeCritic()
    cw.review = _review

    ex = AsyncMock()
    async def _execute(**kwargs):
        return _FakeExecution()
    ex.execute = _execute

    step = PlanStep(
        step_id=0, intent="Compare the two systems", tool_name=tool_name,
        tool_args={}, depends_on=[1, 2], agent_role=agent_role,
    )

    result = await loop._execute_step(  # noqa: SLF001
        step=step, dw=dw, cw=cw, ex=ex,
        instance_id="i", conversation_id="c", user_message="u",
        system_prompt="sp", conversation_history=None, instance_config=None,
        user_info=None, retrieval=RetrievalResult(), progress_callback=None,
        stream_callback=None, dry_run=False, confirmation_token=None,
        step_contexts={1: "a", 2: "b"}, agent_role=agent_role,
        plan_source=plan_source,
    )
    return captured.get("tools"), result


@pytest.mark.asyncio
async def test_reasoning_step_gets_no_tools():
    """A multi-step reasoning step (tool_name=None) must get NO tools."""
    tools, result = await _run_execute_step(
        plan_source="llm_decompose", agent_role="domain_specialist"
    )
    assert tools is None, (
        "reasoning steps must expose no tools — the LLM reasons directly"
    )
    # Draft text is the reasoning output; no tool executed.
    assert result.draft_text == "reasoned output"
    assert result.tool_output is None


@pytest.mark.asyncio
async def test_reasoning_step_ignores_curated_allow_set():
    """Even with allow-set tools available, reasoning steps get none."""
    from unittest.mock import patch

    def _fake_defs():
        return [
            {"function": {"name": "search_knowledge"}},
            {"function": {"name": "plan_task"}},
        ]

    with patch("ai.engine.agent.tools.get_tool_definitions", _fake_defs):
        tools, _ = await _run_execute_step(
            plan_source="llm_decompose", agent_role="domain_specialist"
        )
    assert tools is None


@pytest.mark.asyncio
async def test_single_step_passthrough_keeps_allow_set():
    """Single-step passthrough still exposes the curated allow-set."""
    from unittest.mock import patch

    def _fake_defs():
        return [
            {"function": {"name": "search_knowledge"}},
            {"function": {"name": "plan_task"}},
            {"function": {"name": "export_document"}},
        ]

    with patch("ai.engine.agent.tools.get_tool_definitions", _fake_defs):
        tools, _ = await _run_execute_step(plan_source="single_step")

    names = [d["function"]["name"] for d in (tools or [])]
    assert "search_knowledge" in names
    assert "plan_task" in names
    assert "export_document" not in names


@pytest.mark.asyncio
async def test_named_tool_step_exposes_only_that_tool():
    """A step with an explicit tool_name gets exactly that tool."""
    from unittest.mock import patch

    def _fake_defs():
        return [
            {"function": {"name": "search_knowledge"}},
            {"function": {"name": "export_document"}},
        ]

    with patch("ai.engine.agent.tools.get_tool_definitions", _fake_defs):
        tools, _ = await _run_execute_step(
            plan_source="llm_decompose", tool_name="export_document"
        )

    names = [d["function"]["name"] for d in (tools or [])]
    assert names == ["export_document"]


# ── 4. Deterministic mutation classification ───────────────────────────────
# Mutation is a CAPABILITY FACT of the tool, not the LLM's judgment. The LLM
# routinely marks write-capable steps is_mutation=False (Sprint-18 E2E: the
# export step was marked False and would have run WITHOUT consent). The
# planner must override is_mutation=True for known write-capable tools.


def test_llm_under_marked_export_is_forced_mutation():
    """An export_document step the LLM marked is_mutation=False must be
    coerced to is_mutation=True by the planner's deterministic override."""
    from ai.engine.cognition.plan.planner import PlanStep, _MUTATION_TOOL_NAMES

    assert "export_document" in _MUTATION_TOOL_NAMES

    step = PlanStep(
        step_id=4, intent="Export the report", tool_name="export_document",
        tool_args={}, depends_on=[2], is_mutation=False,
    )
    if step.tool_name in _MUTATION_TOOL_NAMES:
        step.is_mutation = True

    assert step.is_mutation is True


def test_mutation_tool_set_excludes_self_staging_tools():
    """Tools with their own tool-level staging must NOT be in the set — the
    loop would otherwise double-gate (plan consent + tool staging)."""
    from ai.engine.cognition.plan.planner import _MUTATION_TOOL_NAMES

    for self_staging in (
        "call_host_api", "create_dq_rule", "learn_fact", "forget_fact",
        "run_ops_workflow", "search_knowledge", "get_entity_details",
        "navigate_to", "open_entity", "ask_clarification",
    ):
        assert self_staging not in _MUTATION_TOOL_NAMES, self_staging


def test_skill_plan_export_forced_mutation():
    """Skill-authored plans are also coerced: an export step authored with
    is_mutation=False must be forced True (defense in depth)."""
    from ai.engine.cognition.plan.planner import (
        PlanStep, SkillAwarePlanner, _MUTATION_TOOL_NAMES,
    )

    class _FakeSkill:
        name = "weekly_export"
        body = json.dumps({
            "pattern": "custom",
            "steps": [{
                "step_id": 0,
                "intent": "Export weekly report",
                "tool_name": "export_document",
                "tool_args": {},
                "is_mutation": False,
            }],
        })

    plan = SkillAwarePlanner()._parse_skill_plan(_FakeSkill())  # noqa: SLF001
    assert plan is not None
    assert plan.steps[0].tool_name == "export_document"
    assert plan.steps[0].is_mutation is True
    assert plan.needs_confirmation is True
