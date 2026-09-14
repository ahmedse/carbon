"""P2-06c — worker fan-out tool calls routed through the command boundary.

``WorkerPool._run_worker`` used to dispatch worker tool calls through an
interim ``ExecuteWitness`` + ``readonly_worker_hook`` pipeline (P1-07). These
tests lock in the P2-06c wiring where the worker delegates to the host
executor's ``execute_worker_tools_via_boundary`` seam, which builds a
``Command`` per tool call and routes it through the 13-stage command boundary:

  * a mutation (``call_host_api`` with a body / non-GET method) is REFUSED at
    the boundary consent stage (the executor never runs) and surfaced in the
    WorkerArtifact;
  * a read-only tool executes via the boundary executor closure and its result
    is aggregated into the artifact;
  * a text-only worker is unchanged.

Fully offline and deterministic: ``route_chat`` and the tool executors are
faked, and ``get_command_boundary`` is monkeypatched to build a boundary with
an offline PDP stub + fake ledger (no DjangoLedgerAdapter, no DB).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import ai.command_boundary_factory as factory_module
import ai.engine.agent.guardrails as guardrails_mod
import ai.engine.agent.workers as workers_mod
from ai.command_boundary import CommandBoundary
from ai.engine.agent.workers import WorkerArtifact, WorkerPool, WorkerTask
from ai.engine.ports import Decision
from ai.host_executor import CarbonHostExecutor


class _FakeSettings:
    """Minimal settings surface used by WorkerPool."""

    AGENT_MAX_WORKERS = 6
    AGENT_WORKER_TIMEOUT_SEC = 30


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


class _OfflinePDP:
    """Offline PDP mirroring ``ai.pdp.DEFAULT_POLICIES``: reads ALLOW, mutations ASK."""

    _READ = frozenset({"read", "list", "get", "search", "view", "inspect", "retrieve", "describe"})
    _MUTATE = frozenset({"create", "update", "upsert", "write", "send", "execute", "run", "archive", "delete"})

    async def decide(self, principal, action, objects, process_state=None,
                     autonomy="human_only", budget=None, time=None) -> dict:
        if action in self._READ:
            return {"decision": Decision.ALLOW, "reason": "read-only action is permitted", "policy_version": "offline-v1"}
        if action in self._MUTATE:
            return {"decision": Decision.ASK, "reason": "mutating action governed by autonomy", "policy_version": "offline-v1"}
        return {"decision": Decision.REFUSE, "reason": "default deny", "policy_version": "offline-v1"}


class _FakeLedger:
    """In-memory ledger sink (no DjangoLedgerAdapter, no DB)."""

    def __init__(self):
        self.rows: list[dict] = []

    async def record_stage(self, **kwargs) -> str | None:
        self.rows.append(kwargs)
        return f"row-{len(self.rows)}"


def _install_offline_boundary(monkeypatch) -> None:
    """Monkeypatch the factory to build an offline, fail-closed boundary."""

    def _factory(db, *, executor=None, tool_catalog=None, pdp=None,
                 ledger=None, clock=None):
        return CommandBoundary(
            pdp=_OfflinePDP(),
            ledger=_FakeLedger(),
            executor=executor,
            tool_catalog=tool_catalog,
        )

    monkeypatch.setattr(factory_module, "get_command_boundary", _factory)


@pytest.fixture
def harness(monkeypatch):
    """Wire fakes around the worker→boundary dispatch path (offline)."""
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

    # Deterministic settings (no budget enforcement → no DB access).
    monkeypatch.setattr(workers_mod, "get_settings", lambda: _FakeSettings())
    # Offline tool executors — the boundary executor closure dispatches here.
    monkeypatch.setattr("ai.engine.agent.tools.get_tool_executors", fake_get_tool_executors)
    # Offline boundary — no DjangoLedgerAdapter / real PDP / DB access.
    _install_offline_boundary(monkeypatch)

    return SimpleNamespace(calls=calls, monkeypatch=monkeypatch)


def _pool() -> WorkerPool:
    return WorkerPool(
        llm_client=None,
        db=None,
        instance_id="inst-1",
        conversation_id="conv-1",
        executor=CarbonHostExecutor(
            db=None, instance_config={}, user_token="tok", host_user_id="u1",
        ),
    )


# ── 1. Worker mutation tool call is BLOCKED and surfaced ────────────────────


@pytest.mark.asyncio
async def test_worker_mutation_tool_call_is_blocked(harness, monkeypatch):
    """A worker's mutation call must be refused by the boundary, not executed."""
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
    # The mutation was refused at the boundary consent stage — never executed.
    assert harness.calls["call_host_api"] == []
    # …and the block is surfaced in the artifact, never swallowed.
    assert artifact.error
    assert "worker_tool_blocked" in artifact.guardrail_flags
    assert "blocked:call_host_api" in artifact.guardrail_flags


# ── 2. Read-only worker tool call executes and its result is used ───────────


@pytest.mark.asyncio
async def test_worker_readonly_tool_call_executes(harness, monkeypatch):
    """A read-only worker call runs and its output lands in the artifact."""
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

    # The read-only executor ran with the LLM's args (via the boundary closure).
    assert harness.calls["search_knowledge"], "read-only executor must run"
    assert harness.calls["search_knowledge"][0]["query"] == "emission factors"
    # Its result is reflected in the artifact as real work.
    assert artifact.error is None
    assert artifact.guardrail_flags == []
    assert "Searching the knowledge base." in artifact.detail
    assert "search_knowledge" in artifact.detail
    assert "grid factor" in artifact.detail


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
