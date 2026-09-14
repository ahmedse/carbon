"""P2-06e — proactive delivery routed through the command boundary.

Offline wiring tests: no LLM, no live DB (except the PDP permit-policy test,
which mirrors ``test_pdp.py``'s ``django_db(transaction=True)``).

Two levels are asserted:

* **PDP → permit** — ``action="deliver"`` is a permitted host effect, so the
  default-deny policy table returns ``Decision.ALLOW`` (not ``REFUSE``). Every
  delivery decision is persisted as a ``PolicyDecisionRow`` (acceptance
  criterion: "PDP decision row per delivery").
* **Host → boundary** — ``CarbonHostExecutor.execute_delivery_via_boundary``
  builds a real ``Command`` and routes it through ``CommandBoundary`` with the
  delivery effect closure as the boundary executor; the effect only runs when
  the boundary returns ``executed``.

Run (from ``backend/``):

    /home/ahmed/ws/carbon/.venv/bin/python -m pytest ai/tests/test_delivery_boundary.py -q
"""
from __future__ import annotations

import pytest

import ai.command_boundary_factory as factory_module
from ai.command_boundary import Command, CommandBoundary
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
                     autonomy="human_only", budget=None, time=None) -> dict:
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


class _CapturingBoundary:
    def __init__(self, inner: CommandBoundary):
        self._inner = inner
        self.last_command: Command | None = None
        self.last_outcome = None

    async def execute(self, command: Command):
        self.last_command = command
        self.last_outcome = await self._inner.execute(command)
        return self.last_outcome


def _install_capturing_boundary(monkeypatch, fake_ledger) -> dict:
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


# ── PDP permit policy (decision row per delivery) ─────────────────────────

@pytest.mark.django_db(transaction=True)
async def test_pdp_permits_deliver_action():
    pdp = PDP()

    allowed = await pdp.decide("u", "deliver", ["i1"], autonomy="auto")
    assert allowed["decision"] is Decision.ALLOW
    assert allowed["policy_version"] == "pdp-v1.0"


@pytest.mark.django_db(transaction=True)
async def test_delivery_decision_row_is_persisted():
    from asgiref.sync import sync_to_async

    from ai.models.pdp import PolicyDecisionRow

    pdp = PDP()
    await pdp.decide("u", "deliver", ["i1"], autonomy="auto")

    rows = await sync_to_async(
        lambda: list(PolicyDecisionRow.objects.filter(action="deliver")),
        thread_sensitive=True,
    )()
    assert len(rows) == 1
    assert rows[0].principal == "u"
    assert rows[0].decision == Decision.ALLOW.value


# ── Host → boundary (delivery effect only runs when permitted) ────────────

async def test_delivery_seam_routes_through_boundary(monkeypatch):
    ledger = _FakeLedger()
    captured = _install_capturing_boundary(monkeypatch, ledger)
    ex = CarbonHostExecutor(
        db=None, instance_config={}, user_token="tok", host_user_id="u1",
    )

    ran = []

    async def _effect(command=None) -> dict:
        ran.append(True)
        return {"insight_id": "ins-1", "channel": "websocket", "severity": "warning"}

    result = await ex.execute_delivery_via_boundary(
        effect=_effect,
        instance_id="i1",
        host_user_id="u1",
        delivery_type="websocket",
    )

    # The effect ran and its result is surfaced.
    assert result["status"] == "executed"
    assert result["result"] == {
        "insight_id": "ins-1",
        "channel": "websocket",
        "severity": "warning",
    }
    assert len(ran) == 1

    # The Command was declared as a delivery action with a skipped consent gate.
    wrapper = captured["wrapper"]
    assert wrapper.last_command is not None
    assert wrapper.last_command.tool == "proactive_delivery"
    assert wrapper.last_command.action == "deliver"
    assert wrapper.last_command.requires_confirmation is False
    assert wrapper.last_command.autonomy == "auto"
    assert wrapper.last_command.scope.user_identifier == "u1"
    assert wrapper.last_outcome.status == "executed"

    # The boundary recorded its audit stage.
    assert any(row["stage"] == "command_boundary" for row in ledger.rows)


async def test_delivery_seam_refusal_does_not_run_effect(monkeypatch):
    ledger = _FakeLedger()
    captured = _install_capturing_boundary(monkeypatch, ledger)

    # Force the PDP to refuse so the boundary never runs the effect closure.
    captured["refuse"] = True

    def _factory(db, *, executor=None, tool_catalog=None, pdp=None,
                 ledger=None, clock=None):
        inner = CommandBoundary(
            pdp=_StubPDP(decision=Decision.REFUSE, reason="deny"),
            ledger=ledger,
            executor=executor,
            tool_catalog=tool_catalog,
        )
        wrapper = _CapturingBoundary(inner)
        captured["wrapper"] = wrapper
        return wrapper

    monkeypatch.setattr(factory_module, "get_command_boundary", _factory)

    ex = CarbonHostExecutor(
        db=None, instance_config={}, user_token="tok", host_user_id="u1",
    )

    ran = []

    async def _effect(command=None) -> dict:
        ran.append(True)
        return {"insight_id": "ins-1"}

    result = await ex.execute_delivery_via_boundary(
        effect=_effect,
        instance_id="i1",
        host_user_id="u1",
        delivery_type="websocket",
    )

    assert result["status"] == "refused"
    assert result["result"] is None
    assert len(ran) == 0
