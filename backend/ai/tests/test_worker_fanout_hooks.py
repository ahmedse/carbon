"""P1-07 regression — worker fan-out tool calls must run through guardrails.

``WorkerPool._run_worker`` used to ignore the tool calls returned by its LLM
call entirely: read-only work was dropped and a mutation was neither executed
*nor* audited. These tests lock in the interim wiring (until P2-06) where every
worker tool call is dispatched through ``ExecuteWitness`` with
``is_worker=True``, so:

  * a mutation (``call_host_api`` with a body / non-GET method) is BLOCKED by
    the default hook pipeline and the block is surfaced in the WorkerArtifact;
  * a read-only tool executes and its result is aggregated into the artifact;
  * a text-only worker is unchanged.

Fully offline and deterministic: ``route_chat`` and the tool executors are
faked, the guardrail budget hook is disabled, and evidence writes / event
broadcasts are no-ops.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import ai.engine.agent.guardrails as guardrails_mod
import ai.engine.agent.workers as workers_mod
import ai.engine.cognition.turn.execute as execute_mod
from ai.engine.agent.workers import WorkerArtifact, WorkerPool, WorkerTask
from ai.engine.cognition.turn.execute import ExecuteWitness


class _FakeSettings:
    """Minimal settings surface used by WorkerPool + the guardrail hooks."""

    AGENT_MAX_WORKERS = 6
    AGENT_WORKER_TIMEOUT_SEC = 30
    GUARDRAIL_MAX_TOOL_CALLS_PER_RUN = 100
    GUARDRAIL_BUDGET_ENFORCEMENT = False
    GUARDRAIL_REDACTED_TOOLS = "[]"


def _tool_call(name: str, args: dict) -> dict:
    return {
        "id": f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class _FakeAgent:
    def __init__(self, role: str, agent_id: str, tool_set: list[str]):
        self.role = role
        self.id = agent_id
        self.is_active = True
        self.tool_set_json = json.dumps(tool_set)


class _FakeRegistry:
    def __init__(self, agent: _FakeAgent):
        self._agent = agent

    async def get_workers_for(self, orchestrator_id: str):
        return [(self._agent, SimpleNamespace(id="handoff-1"))]


def _patch_route_chat(monkeypatch, response: dict) -> None:
    async def fake_route_chat(*args, **kwargs):
        return response

    monkeypatch.setattr("ai.engine.llm.router.route_chat", fake_route_chat)


@pytest.fixture
def harness(monkeypatch):
    """Wire fakes around the worker→ExecuteWitness dispatch path."""
    calls: dict[str, list] = {"search_knowledge": [], "call_host_api": []}

    async def fake_search_knowledge(query=None, **kwargs):
        calls["search_knowledge"].append({"query": query, **kwargs})
        return {"entities": [{"name": "grid factor"}], "count": 1}

    async def fake_call_host_api(api_name=None, **kwargs):
        calls["call_host_api"].append({"api_name": api_name, **kwargs})
        return {"status_code": 200, "data": {"created": True}}

    async def fake_get_tool_executors():
        return {
            "search_knowledge": fake_search_knowledge,
            "call_host_api": fake_call_host_api,
        }

    async def fake_register_evidence(self, **kwargs):
        return None

    async def fake_broadcast(*args, **kwargs):
        return None

    # Deterministic settings (budget hook off → no DB access).
    monkeypatch.setattr(workers_mod, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(guardrails_mod, "get_settings", lambda: _FakeSettings())
    # Offline tool executors + no side-effecting evidence/broadcast.
    monkeypatch.setattr("ai.engine.agent.tools.get_tool_executors", fake_get_tool_executors)
    monkeypatch.setattr(ExecuteWitness, "_register_evidence", fake_register_evidence)
    monkeypatch.setattr(execute_mod, "broadcast_run_event", fake_broadcast)

    return SimpleNamespace(calls=calls, monkeypatch=monkeypatch)


def _pool() -> WorkerPool:
    return WorkerPool(
        llm_client=None,
        db=None,
        instance_id="inst-1",
        conversation_id="conv-1",
    )


# ── 1. Worker mutation tool call is BLOCKED and surfaced ────────────────────


@pytest.mark.asyncio
async def test_worker_mutation_tool_call_is_blocked(harness, monkeypatch):
    """A worker's mutation call must be cancelled by the hooks, not executed."""
    _patch_route_chat(monkeypatch, {
        "content": "Attempting to create a record.",
        "tool_calls": [
            _tool_call("call_host_api", {"api_name": "some_create", "body": {"name": "x"}}),
        ],
        "input_tokens": 11,
        "output_tokens": 5,
        "finish_reason": "tool_calls",
    })
    registry = _FakeRegistry(_FakeAgent("researcher", "worker-agent-1", ["call_host_api"]))
    task = WorkerTask(agent_role="researcher", task="create something")

    artifact = await _pool()._run_worker(task, registry, "orchestrator-1", "sys")

    assert isinstance(artifact, WorkerArtifact)
    # The mutation was blocked at the hook layer — its executor never ran.
    assert harness.calls["call_host_api"] == []
    # …and the block is surfaced in the artifact, never swallowed.
    assert artifact.error
    assert "blocked by guardrail" in artifact.error.lower()
    assert "requires user confirmation" in artifact.error
    assert "worker_tool_blocked" in artifact.guardrail_flags
    assert "blocked:call_host_api" in artifact.guardrail_flags
    assert "guardrail" in (artifact.detail or "").lower()


# ── 2. Read-only worker tool call executes and its result is used ───────────


@pytest.mark.asyncio
async def test_worker_readonly_tool_call_executes(harness, monkeypatch):
    """A read-only worker call runs and its output lands in the artifact."""
    captured_ctx: list = []
    real_readonly_hook = guardrails_mod.readonly_worker_hook

    async def spy_readonly_hook(ctx):
        captured_ctx.append(ctx)
        return await real_readonly_hook(ctx)

    monkeypatch.setattr(guardrails_mod, "readonly_worker_hook", spy_readonly_hook)

    _patch_route_chat(monkeypatch, {
        "content": "Searching the knowledge base.",
        "tool_calls": [
            _tool_call("search_knowledge", {"query": "emission factors"}),
        ],
        "input_tokens": 8,
        "output_tokens": 4,
        "finish_reason": "tool_calls",
    })
    registry = _FakeRegistry(_FakeAgent("researcher", "worker-agent-2", ["search_knowledge"]))
    task = WorkerTask(agent_role="researcher", task="find factors")

    artifact = await _pool()._run_worker(task, registry, "orchestrator-1", "sys")

    # The read-only executor ran with the LLM's args.
    assert harness.calls["search_knowledge"], "read-only executor must run"
    assert harness.calls["search_knowledge"][0]["query"] == "emission factors"
    # Its result is reflected in the artifact as real work.
    assert artifact.error is None
    assert artifact.guardrail_flags == []
    assert "Searching the knowledge base." in artifact.detail
    assert "search_knowledge" in artifact.detail
    assert "grid factor" in artifact.detail
    # is_worker=True was threaded into the HookContext for the worker call.
    assert captured_ctx, "readonly_worker_hook must see the worker tool call"
    assert all(c.is_worker for c in captured_ctx)
    assert captured_ctx[0].agent_role == "researcher"
    assert captured_ctx[0].instance_id == "inst-1"
    assert captured_ctx[0].run_id


# ── 3. A worker with no tool calls keeps the text-only behavior ─────────────


@pytest.mark.asyncio
async def test_worker_without_tool_calls_returns_text_artifact(harness, monkeypatch):
    """No tool calls → unchanged text artifact, no execution attempted."""
    _patch_route_chat(monkeypatch, {
        "content": "Here is a plain textual answer.",
        "tool_calls": None,
        "input_tokens": 3,
        "output_tokens": 6,
        "finish_reason": "stop",
    })
    registry = _FakeRegistry(_FakeAgent("researcher", "worker-agent-3", ["search_knowledge"]))
    task = WorkerTask(agent_role="researcher", task="say hi")

    artifact = await _pool()._run_worker(task, registry, "orchestrator-1", "sys")

    assert artifact.error is None
    assert artifact.guardrail_flags == []
    assert artifact.summary == "Here is a plain textual answer."
    assert artifact.detail == "Here is a plain textual answer."
    assert artifact.tokens_used == 9
    assert harness.calls["search_knowledge"] == []
    assert harness.calls["call_host_api"] == []


# ── Guard-level lock-in: the hook itself blocks workers only ────────────────


@pytest.mark.asyncio
async def test_readonly_worker_hook_blocks_mutation_only_for_workers():
    """readonly_worker_hook cancels a worker mutation, allows the orchestrator."""
    worker_ctx = guardrails_mod.HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "some_create", "body": {"name": "x"}},
        instance_id="inst-1",
        is_worker=True,
    )
    blocked = await guardrails_mod.readonly_worker_hook(worker_ctx)
    assert blocked.action == "cancel"
    assert "worker_mutation_blocked" in blocked.flags

    orchestrator_ctx = guardrails_mod.HookContext(
        tool_name="call_host_api",
        tool_args={"api_name": "some_create", "body": {"name": "x"}},
        instance_id="inst-1",
        is_worker=False,
    )
    allowed = await guardrails_mod.readonly_worker_hook(orchestrator_ctx)
    assert allowed.action == "pass"
