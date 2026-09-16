"""P2-06b — ``call_host_api`` routed through the command boundary.

Offline wiring tests: no LLM, no live DB (except the PDP permit-policy test,
which mirrors ``test_pdp.py``'s ``django_db(transaction=True)``).

Two levels are asserted:

* **Tool → boundary** — ``execute_call_host_api`` delegates its resolved host
  effect to the executor's ``execute_host_api_via_boundary`` seam (and falls
  back to the legacy direct effect when no boundary seam exists).
* **Host → boundary** — ``CarbonHostExecutor.execute_host_api_via_boundary``
  builds a real ``Command`` and routes it through ``CommandBoundary`` (PDP +
  contract + ledger), with the tool's effect closure as the boundary executor.

Run (from ``backend/``):

    /home/ahmed/ws/carbon/.venv/bin/python -m pytest ai/tests/test_call_host_api_boundary.py -q
"""
from __future__ import annotations

import pytest

import ai.command_boundary_factory as factory_module
from ai.command_boundary import Command, CommandBoundary
from ai.command_boundary_factory import get_command_boundary
from ai.engine.agent.tools import execute_call_host_api
from ai.engine.ports import Decision
from ai.host_executor import CarbonHostExecutor
from ai.pdp import PDP
from ai.protocol import Scope

pytestmark = pytest.mark.asyncio


# ── Fakes / stubs ──────────────────────────────────────────────────────────

class _StubPDP:
    def __init__(self, decision: Decision = Decision.ALLOW, reason: str = "permit"):
        self.decision = decision
        self.reason = reason

    async def decide(self, principal, action, objects, process_state=None,
                     autonomy="human_only", budget=None, time=None, **kwargs) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "policy_version": "v1",
        }


class _FakeLedger:
    def __init__(self):
        self.rows: list[dict] = []

    async def record_stage(self, **kwargs) -> str | None:
        self.rows.append(kwargs)
        return f"row-{len(self.rows)}"


class _CountingExecutor:
    def __init__(self):
        self.calls = 0

    async def __call__(self, command: Command):
        self.calls += 1
        return {"ok": True}


class _CapturingBoundary:
    """Wraps a real boundary so the tool's Command + Outcome can be inspected."""

    def __init__(self, inner: CommandBoundary):
        self._inner = inner
        self.last_command: Command | None = None
        self.last_outcome = None

    async def execute(self, command: Command):
        self.last_command = command
        self.last_outcome = await self._inner.execute(command)
        return self.last_outcome


class _FakeExecution:
    def __init__(self, id: str = "exec-1"):
        self.id = id


class _FakeHostExecutor:
    """Stands in for HostAPIExecutor/CarbonHostExecutor — no HTTP, no DB."""

    def __init__(self, *, method: str = "GET", path: str = "/x",
                 result=None, requires_confirmation: bool = False,
                 user_token: str = "tok", host_user_id: str = "u1", db=None):
        self.method = method
        self.path = path
        self._result = result if result is not None else {"data": [{"id": 1}]}
        self._requires_confirmation = requires_confirmation
        self.user_token = user_token
        self.host_user_id = host_user_id
        self.db = db
        self.instance_config = {"display_name": "test-host", "name": "test"}
        self.pending: list[dict] = []

    def get_catalog_entry(self, api_name: str) -> dict | None:
        return {
            "name": api_name,
            "method": self.method,
            "path": self.path,
            "requires_confirmation": self._requires_confirmation,
        }

    def requires_confirmation(self, api_name: str) -> bool:
        return self._requires_confirmation

    async def call_api_direct(self, method, endpoint, params=None, body=None) -> dict:
        return dict(self._result)

    async def create_pending_execution(self, **kwargs) -> _FakeExecution:
        ex = _FakeExecution()
        self.pending.append(kwargs)
        return ex


class _BoundaryBackedExecutor:
    """Tool-level fake exposing the host boundary seam."""

    def __init__(self, *, method: str = "GET", path: str = "/x",
                 requires_confirmation: bool = False, boundary_result=None):
        self.method = method
        self.path = path
        self._requires_confirmation = requires_confirmation
        self._boundary_result = boundary_result or {"via_boundary": True}
        self.user_token = "tok"
        self.host_user_id = "u1"
        self.instance_config = {"display_name": "test-host", "name": "test"}
        self.calls: list[dict] = []

    def get_catalog_entry(self, api_name: str) -> dict | None:
        return {
            "name": api_name,
            "method": self.method,
            "path": self.path,
            "requires_confirmation": self._requires_confirmation,
        }

    def requires_confirmation(self, api_name: str) -> bool:
        return self._requires_confirmation

    async def call_api_direct(self, method, endpoint, params=None, body=None) -> dict:
        return {"direct": True, "method": method, "endpoint": endpoint}

    async def create_pending_execution(self, **kwargs):
        class _Ex:
            id = "exec-1"
        return _Ex()

    async def execute_host_api_via_boundary(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self._boundary_result


class _PlainExecutor:
    """Tool-level fake WITHOUT the boundary seam (legacy fallback path)."""

    def __init__(self, *, method: str = "GET", path: str = "/x",
                 requires_confirmation: bool = False):
        self.method = method
        self.path = path
        self._requires_confirmation = requires_confirmation
        self.user_token = "tok"
        self.host_user_id = "u1"
        self.instance_config = {"display_name": "test-host", "name": "test"}
        self.pending: list[dict] = []

    def get_catalog_entry(self, api_name: str) -> dict | None:
        return {
            "name": api_name,
            "method": self.method,
            "path": self.path,
            "requires_confirmation": self._requires_confirmation,
        }

    def requires_confirmation(self, api_name: str) -> bool:
        return self._requires_confirmation

    async def call_api_direct(self, method, endpoint, params=None, body=None) -> dict:
        return {"data": [{"id": 1}]}

    async def create_pending_execution(self, **kwargs):
        class _Ex:
            id = "exec-1"
        self.pending.append(kwargs)
        return _Ex()


def _install_capturing_boundary(monkeypatch, fake_ledger) -> dict:
    """Monkeypatch the factory so the tool builds a real boundary with fakes."""
    captured: dict = {}

    def _factory(db, *, executor=None, tool_catalog=None, pdp=None,
                 ledger=None, clock=None):
        inner = CommandBoundary(
            pdp=_StubPDP(),
            ledger=fake_ledger,
            executor=executor,
            tool_catalog=tool_catalog,
        )
        wrapper = _CapturingBoundary(inner)
        captured["wrapper"] = wrapper
        captured["executor"] = executor
        captured["tool_catalog"] = tool_catalog
        return wrapper

    monkeypatch.setattr(factory_module, "get_command_boundary", _factory)
    return captured


# ── Tests ──────────────────────────────────────────────────────────────────

async def test_mutation_host_call_delegates_to_boundary_seam():
    ex = _BoundaryBackedExecutor(method="POST", path="/rules", requires_confirmation=False)

    result = await execute_call_host_api(
        "create_rule", explanation="make a rule",
        executor=ex, conversation_id="c1", instance_id="i1",
    )

    assert result == {"via_boundary": True}
    assert len(ex.calls) == 1
    call = ex.calls[0]
    assert callable(call["effect"])
    assert call["api_name"] == "create_rule"
    assert call["method"] == "POST"
    assert call["path"] == "/rules"
    assert call["needs_confirmation"] is True
    assert call["instance_id"] == "i1"
    assert call["host_user_id"] == "u1"


async def test_get_host_call_delegates_to_boundary_seam():
    ex = _BoundaryBackedExecutor(method="GET", path="/tables", requires_confirmation=False)

    result = await execute_call_host_api(
        "list_tables", explanation="list tables",
        executor=ex, conversation_id="c1", instance_id="i1",
    )

    assert result == {"via_boundary": True}
    assert ex.calls[0]["needs_confirmation"] is False


async def test_legacy_fallback_without_boundary_seam():
    """An executor without the boundary seam still produces a host effect."""
    ex = _PlainExecutor(method="POST", path="/rules", requires_confirmation=False)

    result = await execute_call_host_api(
        "create_rule", explanation="make a rule",
        executor=ex, conversation_id="c1", instance_id="i1",
    )

    assert result.get("requires_confirmation") is True
    assert result.get("execution_id") == "exec-1"
    assert len(ex.pending) == 1


async def test_no_executor_returns_error_without_boundary(monkeypatch):
    def _factory(*args, **kwargs):
        raise AssertionError("boundary must not be invoked")

    monkeypatch.setattr(factory_module, "get_command_boundary", _factory)

    result = await execute_call_host_api("x", explanation="", executor=None)
    assert result == {"error": "Host API executor not available"}


async def test_host_executor_routes_through_boundary(monkeypatch):
    ledger = _FakeLedger()
    captured = _install_capturing_boundary(monkeypatch, ledger)
    ex = CarbonHostExecutor(
        db=None, instance_config={}, user_token="tok", host_user_id="u1",
    )

    async def _effect(command=None) -> dict:
        return {"requires_confirmation": True, "execution_id": "exec-1",
                "method": "POST", "endpoint": "/rules",
                "confirmation_message": "ok?"}

    result = await ex.execute_host_api_via_boundary(
        effect=_effect,
        api_name="create_rule",
        method="POST",
        path="/rules",
        needs_confirmation=True,
        instance_id="i1",
        host_user_id="u1",
    )

    assert result.get("requires_confirmation") is True
    assert result.get("execution_id") == "exec-1"

    wrapper = captured["wrapper"]
    assert wrapper.last_command is not None
    assert wrapper.last_command.tool == "call_host_api"
    assert wrapper.last_command.action == "call_host_api"
    assert wrapper.last_command.requires_confirmation is False
    assert wrapper.last_command.autonomy == "human_only"
    assert wrapper.last_command.scope.user_identifier == "u1"
    assert wrapper.last_outcome.status == "executed"

    # The boundary recorded its audit stage.
    assert any(row["stage"] == "command_boundary" for row in ledger.rows)


async def test_host_executor_read_is_auto(monkeypatch):
    ledger = _FakeLedger()
    captured = _install_capturing_boundary(monkeypatch, ledger)
    ex = CarbonHostExecutor(
        db=None, instance_config={}, user_token="tok", host_user_id="u1",
    )

    async def _effect(command=None) -> dict:
        return {"data": [{"id": 1}]}

    result = await ex.execute_host_api_via_boundary(
        effect=_effect,
        api_name="list_tables",
        method="GET",
        path="/tables",
        needs_confirmation=False,
        instance_id="i1",
        host_user_id="u1",
    )

    assert result == {"data": [{"id": 1}]}
    assert captured["wrapper"].last_command.autonomy == "auto"


async def test_factory_contract_refuses_undeclared_tool():
    boundary = get_command_boundary(
        None,
        tool_catalog={"some_other_tool": True},
        pdp=_StubPDP(),
        ledger=_FakeLedger(),
        executor=_CountingExecutor(),
    )
    command = Command(
        principal="u",
        scope=Scope(user_identifier="u"),
        tool="call_host_api",
        action="call_host_api",
        requires_confirmation=False,
    )

    outcome = await boundary.execute(command)

    assert outcome.status == "refused"
    assert outcome.stages == ["identity", "scope", "contract"]
    assert "not declared" in (outcome.error or "")


@pytest.mark.django_db(transaction=True)
async def test_pdp_permits_call_host_api_and_denies_unknown():
    pdp = PDP()

    allowed = await pdp.decide("u", "call_host_api", [], autonomy="human_only")
    assert allowed["decision"] is Decision.ALLOW

    denied = await pdp.decide("u", "unknown_action", [], autonomy="auto")
    assert denied["decision"] is Decision.REFUSE
    assert "default deny" in denied["reason"].lower()
