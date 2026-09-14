"""P2-06d — ReAct plan-step consent gate routed through the command boundary.

Offline wiring tests for ``CarbonHostExecutor.execute_step_via_boundary``:
no LLM, no live DB. ``get_command_boundary`` is monkeypatched to build a
fail-closed boundary around an offline permit-PDP stub + in-memory ledger, so
the consent stage (stage 7) is exercised deterministically:

  * a no-token mutation step is REFUSED at the boundary consent stage — the
    effect closure never runs — and surfaces ``requires_confirmation=True``;
  * a mutation step carrying a confirmation token executes the effect closure;
  * ``_tool_requires_confirmation`` fails CLOSED (returns True) when the
    plugin registry import/call raises.

Run (from ``backend/``):

    /home/ahmed/ws/carbon/.venv/bin/python -m pytest ai/tests/test_react_consent_boundary.py -q
"""
from __future__ import annotations

import pytest

import ai.command_boundary_factory as factory_module
from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports import Decision
from ai.host_executor import CarbonHostExecutor

pytestmark = pytest.mark.asyncio


class _StubPDP:
    """Offline PDP that always permits (ALLOW)."""

    def __init__(self, decision: Decision = Decision.ALLOW, reason: str = "permit"):
        self.decision = decision
        self.reason = reason

    async def decide(
        self,
        principal,
        action,
        objects,
        process_state=None,
        autonomy="human_only",
        budget=None,
        time=None,
    ) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "policy_version": "offline-v1",
        }


class _FakeLedger:
    """In-memory ledger sink (mirrors test_delivery_boundary._FakeLedger)."""

    def __init__(self):
        self.rows: list[dict] = []

    async def record_stage(self, **kwargs) -> str | None:
        self.rows.append(kwargs)
        return f"row-{len(self.rows)}"


class _CapturingBoundary:
    """Wraps the boundary so tests can assert the built ``Command``."""

    def __init__(self, inner: CommandBoundary):
        self._inner = inner
        self.last_command: Command | None = None
        self.last_outcome = None

    async def execute(self, command: Command):
        self.last_command = command
        self.last_outcome = await self._inner.execute(command)
        return self.last_outcome


def _install_boundary(monkeypatch) -> dict:
    """Swap the real factory for an offline, fail-closed boundary builder."""
    captured: dict = {}

    def _factory(db, *, executor=None, tool_catalog=None, pdp=None,
                 ledger=None, clock=None):
        inner = CommandBoundary(
            pdp=_StubPDP(),
            ledger=_FakeLedger(),
            executor=executor,
            tool_catalog=tool_catalog,
        )
        wrapper = _CapturingBoundary(inner)
        captured["wrapper"] = wrapper
        return wrapper

    monkeypatch.setattr(factory_module, "get_command_boundary", _factory)
    return captured


def _make_executor() -> CarbonHostExecutor:
    return CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token="tok",
        host_user_id="u1",
    )


async def test_step_via_boundary_refuses_unconfirmed_mutation(monkeypatch):
    captured = _install_boundary(monkeypatch)
    ex = _make_executor()

    ran: list[bool] = []

    async def _effect(command=None) -> dict:
        ran.append(True)
        return {"wrote": True}

    result = await ex.execute_step_via_boundary(
        effect=_effect,
        tool_name="call_host_api",
        is_mutation=True,
        confirmation_token=None,
        instance_id="i1",
        host_user_id="u1",
        conversation_id="c1",
    )

    # No token → stage-7 consent refusal → the consent decision is now a
    # boundary outcome; the effect closure must never run.
    assert result["requires_confirmation"] is True
    assert result["status"] == "refused"
    assert len(ran) == 0, "consent gate must block the effect closure"

    # The built command is fail-closed: confirmation required, no token,
    # human_only autonomy for a mutation.
    wrapper = captured["wrapper"]
    assert wrapper.last_command is not None
    assert wrapper.last_command.requires_confirmation is True
    assert wrapper.last_command.confirmation_token is None
    assert wrapper.last_command.autonomy == "human_only"
    assert wrapper.last_command.tool == "call_host_api"


async def test_step_via_boundary_executes_with_confirmation_token(monkeypatch):
    captured = _install_boundary(monkeypatch)
    ex = _make_executor()

    ran: list[bool] = []

    async def _effect(command=None) -> dict:
        ran.append(True)
        return {"wrote": True}

    result = await ex.execute_step_via_boundary(
        effect=_effect,
        tool_name="call_host_api",
        is_mutation=True,
        confirmation_token="tok-123",
        instance_id="i1",
        host_user_id="u1",
        conversation_id="c1",
    )

    # With a token the boundary confirms at stage 7 and runs the effect.
    assert result["requires_confirmation"] is False
    assert result["status"] == "confirmed"
    assert result["result"] == {"wrote": True}
    assert len(ran) == 1, "effect must run once consent passed"


async def test_tool_requires_confirmation_is_fail_closed(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("plugin registry unavailable")

    monkeypatch.setattr("ai.engine.agent.plugins.is_confirmation_tool", _boom)

    from ai.engine.cognition.plan.loop import _tool_requires_confirmation

    # Lookup failure now means confirmation-required (deny-by-default).
    assert _tool_requires_confirmation("call_host_api") is True
