"""W3-A chat bridge — ``plan_task`` plugin tests.

Covers: registration at startup, metadata (RULE_21 non-mutating planning),
authentication gating, empty-brief handling, and a successful decompose →
pending_approval plan with outcome copy (RULE_23).

The engine planner is faked exactly like ``test_plans.py``'s
``patch_engine_seams`` fixture (no LLM call, deterministic 2-step plan), so
``create_plan`` runs the same service path the API views use.
"""
from __future__ import annotations

import asyncio

import pytest

import ai.engine.agent.plugins as plugins_mod
from ai.engine.agent.plugins import ToolContext, registered_plugins
from ai.plugins.plan_task import PlanTask


@pytest.fixture(autouse=True)
def _reset_plugins():
    original = list(plugins_mod._PLUGINS)
    yield
    plugins_mod._PLUGINS[:] = original


# ── Engine seam fakes (mirror ai/tests/test_plans.py) ────────────────────


def _plan_from_steps(spec: dict):
    """Build an engine Plan object from a spec dict (same as test_plans.py)."""
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    return Plan(
        pattern=spec.get("pattern", "custom"),
        steps=[
            PlanStep(
                step_id=int(s["step_id"]),
                intent=s["intent"],
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args") or {},
                depends_on=s.get("depends_on") or [],
            )
            for s in spec.get("steps", [])
        ],
        synthesis_instruction=spec.get("synthesis_instruction", ""),
        source=spec.get("source", "custom"),
        skill_name=spec.get("skill_name"),
        needs_confirmation=False,
    )


class _FakePlanner:
    """Stand-in for SkillAwarePlanner — no LLM call, deterministic 2-step."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def decompose(self, **kwargs):
        return _plan_from_steps({
            "pattern": "root_cause",
            "source": "llm_decompose",
            "steps": [
                {"step_id": 0, "intent": "Load the emissions totals",
                 "tool_name": None, "tool_args": {}, "depends_on": []},
                {"step_id": 1, "intent": "Compare against the baseline",
                 "tool_name": None, "tool_args": {}, "depends_on": [0]},
            ],
            "synthesis_instruction": "Summarize findings.",
        })


class _FakeSession:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeFactory:
    def __call__(self):
        return _FakeSession()


@pytest.fixture
def patch_planner_seams(monkeypatch):
    monkeypatch.setattr(
        "ai.engine.cognition.plan.planner.SkillAwarePlanner", _FakePlanner
    )
    monkeypatch.setattr(
        "ai.engine.core.database.get_session_factory", lambda *a, **k: _FakeFactory()
    )


def _run(args, *, host_user_id="42", conversation_id="conv-1") -> dict:
    plugin = PlanTask()
    ctx = ToolContext(
        conversation_id=conversation_id,
        host_user_id=host_user_id,
    )
    return asyncio.run(plugin.execute(args, ctx=ctx))


# ── Registration + metadata ──────────────────────────────────────────────


def test_plan_task_is_registered_at_startup():
    from ai.plugins import register_builtin_plugins

    register_builtin_plugins()
    names = {p.name for p in registered_plugins()}
    assert "plan_task" in names


def test_plan_task_metadata():
    from ai.plugins import register_builtin_plugins

    register_builtin_plugins()
    plugin = next(p for p in registered_plugins() if p.name == "plan_task")
    assert plugin.requires_confirmation is False
    assert "brief" in plugin.input_schema["properties"]
    assert plugin.input_schema["required"] == ["brief"]


def test_plan_task_appears_in_chat_tool_definitions():
    """The chat planner's curated set must include plan_task (runner.py)."""
    from ai.plugins import register_builtin_plugins

    register_builtin_plugins()
    from ai.engine.agent.tools import get_tool_definitions

    names = {d["function"]["name"] for d in get_tool_definitions()}
    assert "plan_task" in names


# ── execute() gating ─────────────────────────────────────────────────────


def test_execute_requires_authenticated_session():
    result = _run({"brief": "plan an audit"}, host_user_id=None)
    assert "error" in result
    assert "authenticated session" in result["error"]


def test_execute_requires_brief():
    result = _run({}, host_user_id="42")
    assert "error" in result
    assert "brief" in result["error"].lower()


def test_execute_rejects_blank_brief():
    result = _run({"brief": "   "}, host_user_id="42")
    assert "error" in result


@pytest.mark.django_db
def test_execute_unknown_user_is_graceful():
    # An id that does not exist in the DB → graceful error, not a crash.
    result = _run({"brief": "plan an audit"}, host_user_id="does-not-exist")
    assert "error" in result
    assert "not found" in result["error"].lower()


# ── Successful plan creation (RULE_21 non-mutating + RULE_23 copy) ───────


@pytest.mark.django_db(transaction=True)
def test_execute_creates_pending_approval_plan(create_user, patch_planner_seams):
    user = create_user("plan-owner")
    from ai.models.core import Run, RunStep

    result = _run(
        {"brief": "Audit the emissions uploads for completeness"},
        host_user_id=str(user.pk),
    )

    assert result["requires_confirmation"] is False
    assert result["action"] == "plan_created"
    plan_id = result["plan_id"]
    assert plan_id
    assert result["status"] == "pending_approval"
    assert len(result["steps"]) == 2
    assert [s["step_id"] for s in result["steps"]] == [0, 1]
    assert result["steps"][0]["intent"] == "Load the emissions totals"
    # RULE_23 — product terms, no engine names, and an explicit "not executed".
    assert "Nothing has executed" in result["message"]
    assert "pending_approval" in result["message"]
    assert "ReActLoop" not in result["message"]

    run = Run.objects.get(id=plan_id)
    assert run.host_user_id == str(user.pk)
    assert run.status == "pending_approval"
    assert run.conversation_id == "conv-1"
    assert RunStep.objects.filter(run_id=run.id).count() == 2
