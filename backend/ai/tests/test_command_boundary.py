"""P2-06a — Command Boundary core: per-stage + stage-order unit tests.

Offline: no LLM, no network, no ORM.  All ports are fakes/stubs injected into
:class:`ai.command_boundary.CommandBoundary`; the PDP is a stub returning a
canned ``Decision``.  The default-deny / fail-closed behaviour is exercised by
driving each stage to its refusal path and asserting the recorded ``stages``.

Run (from ``backend/``):

    /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_command_boundary.py -q
"""
from __future__ import annotations

from typing import Any

import pytest

from ai.command_boundary import (
    STAGES,
    BudgetVerdict,
    Command,
    CommandBoundary,
    Outcome,
)
from ai.engine.ports import Decision
from ai.protocol import Scope

pytestmark = pytest.mark.asyncio


# ── Fakes / stubs ──────────────────────────────────────────────────────────

class _StubPDP:
    """Returns a canned decision; records calls for assertions."""

    def __init__(self, decision: Decision = Decision.ALLOW,
                 reason: str = "test allow", policy_version: str = "v1"):
        self.decision = decision
        self.reason = reason
        self.policy_version = policy_version
        self.calls: list[dict] = []

    async def decide(self, principal, action, objects, process_state=None,
                     autonomy="human_only", budget=None, time=None) -> dict:
        self.calls.append({"principal": principal, "action": action, "objects": objects})
        return {
            "decision": self.decision,
            "reason": self.reason,
            "policy_version": self.policy_version,
        }


class _CountingExecutor:
    def __init__(self, result: Any | None = None):
        self.calls = 0
        self.result = result if result is not None else {"ok": True}

    async def __call__(self, command: Command) -> Any:
        self.calls += 1
        return dict(self.result)


class _FakeLedger:
    def __init__(self):
        self.rows: list[dict] = []

    async def record_stage(self, **kwargs) -> str | None:
        self.rows.append(kwargs)
        return f"row-{len(self.rows)}"


class _FakeEventBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish(self, channel: str, payload: dict) -> None:
        self.events.append((channel, payload))


class _AlwaysEligible:
    async def __call__(self, command: Command) -> bool:
        return True


class _FailingVerifier:
    async def __call__(self, command: Command, result: Any) -> None:
        raise RuntimeError("verification failed")


async def _raise_identity(command: Command) -> str:
    raise ValueError("no identity")


def make_scope(**kwargs) -> Scope:
    defaults = dict(
        user_identifier="u1",
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=True,
    )
    defaults.update(kwargs)
    return Scope(**defaults)


def make_command(**kwargs) -> Command:
    defaults = dict(
        principal="u1",
        scope=make_scope(),
        tool="test_tool",
        action="test_tool",
        params={},
        objects=[],
        requires_confirmation=False,
    )
    defaults.update(kwargs)
    return Command(**defaults)


def make_boundary(**kwargs) -> CommandBoundary:
    defaults = dict(
        pdp=_StubPDP(),
        executor=_CountingExecutor(),
        tool_catalog={"test_tool": {}},
        eligibility_checker=_AlwaysEligible(),
    )
    defaults.update(kwargs)
    return CommandBoundary(**defaults)


# ── Stage tests ────────────────────────────────────────────────────────────

async def test_null_scope_refused_at_stage_2():
    boundary = make_boundary()
    outcome = await boundary.execute(make_command(scope=None))
    assert outcome.status == "refused"
    assert outcome.stages == ["identity", "scope"]
    assert "Scope" in (outcome.error or "")


async def test_unknown_tool_refused_at_stage_3():
    boundary = make_boundary()
    outcome = await boundary.execute(
        make_command(tool="nope", action="nope")
    )
    assert outcome.status == "refused"
    assert outcome.stages == ["identity", "scope", "contract"]
    assert "not declared" in (outcome.error or "")


async def test_pdp_refuse_default_deny_at_stage_6():
    # Default boundary (no PDP injected) is default-deny.
    boundary = CommandBoundary(
        executor=_CountingExecutor(),
        tool_catalog={"test_tool": {}},
    )
    outcome = await boundary.execute(make_command())
    assert outcome.status == "refused"
    assert outcome.decision == Decision.REFUSE
    assert outcome.stages == [
        "identity", "scope", "contract", "validate",
        "state_eligibility", "pdp",
    ]


async def test_pdp_explicit_refuse_at_stage_6():
    boundary = make_boundary(pdp=_StubPDP(Decision.REFUSE, reason="policy forbid"))
    outcome = await boundary.execute(make_command())
    assert outcome.status == "refused"
    assert outcome.decision == Decision.REFUSE
    assert outcome.reason == "policy forbid"


async def test_requires_confirmation_without_token_refused_at_stage_7():
    boundary = make_boundary()
    outcome = await boundary.execute(
        make_command(requires_confirmation=True, confirmation_token=None)
    )
    assert outcome.status == "refused"
    assert "confirmation_token" in (outcome.error or "")
    assert outcome.stages == [
        "identity", "scope", "contract", "validate",
        "state_eligibility", "pdp", "consent",
    ]


async def test_allow_with_confirmation_requires_token_at_stage_7():
    boundary = make_boundary(
        pdp=_StubPDP(Decision.ALLOW_WITH_CONFIRMATION),
    )
    # requires_confirmation=False on the command, but PDP forces confirmation.
    outcome = await boundary.execute(
        make_command(requires_confirmation=False, confirmation_token=None)
    )
    assert outcome.status == "refused"
    assert "confirmation_token" in (outcome.error or "")


async def test_confirmation_with_token_yields_confirmed_status():
    boundary = make_boundary(
        pdp=_StubPDP(Decision.ALLOW_WITH_CONFIRMATION),
    )
    outcome = await boundary.execute(
        make_command(
            requires_confirmation=True,
            confirmation_token="tok-123",
        )
    )
    assert outcome.status == "confirmed"
    assert outcome.confirmation_token == "tok-123"


async def test_budget_exceeded_refused_at_stage_9():
    async def over_budget(command: Command) -> BudgetVerdict:
        return BudgetVerdict(allowed=False, reason="run token budget exceeded",
                             flags=["budget_exceeded"])

    boundary = make_boundary(budget_checker=over_budget)
    outcome = await boundary.execute(make_command())
    assert outcome.status == "refused"
    assert "budget exceeded" in (outcome.error or "")
    assert outcome.stages[-1] == "budget"


async def test_idempotent_repeat_is_noop_single_execution():
    executor = _CountingExecutor()
    boundary = make_boundary(executor=executor)

    command = make_command(idempotency_key="k1")
    first = await boundary.execute(command)
    second = await boundary.execute(command)

    assert first.status == "executed"
    assert second.status == "executed"
    assert executor.calls == 1  # executed exactly once
    assert first.result == second.result
    assert first.event_ids == second.event_ids


async def test_verify_failure_fails_closed():
    boundary = make_boundary(verifier=_FailingVerifier())
    outcome = await boundary.execute(make_command())
    assert outcome.status == "failed"
    assert "verification failed" in (outcome.error or "")
    assert outcome.stages[-1] == "verify"


async def test_identity_failure_refused_at_stage_1():
    boundary = make_boundary(identity_resolver=_raise_identity)
    outcome = await boundary.execute(make_command())
    assert outcome.status == "refused"
    assert outcome.stages == ["identity"]


async def test_clean_allow_path_yields_executed():
    boundary = make_boundary()
    outcome = await boundary.execute(make_command())
    assert outcome.status == "executed"
    assert outcome.result == {"ok": True}


async def test_stage_order_runs_exactly_1_to_14():
    boundary = make_boundary()
    outcome = await boundary.execute(make_command())
    assert outcome.status == "executed"
    assert outcome.stages == list(STAGES)
    # strict, positional ordering
    assert len(outcome.stages) == len(STAGES) == 14


# ── Grant stage (P3-06 business approval) ────────────────────────────

async def test_grant_refused_when_requires_grant_and_no_resolver():
    # No grant resolver injected → the default resolver returns None (fail-closed).
    boundary = make_boundary()
    outcome = await boundary.execute(
        make_command(requires_grant=True, capability="ai:publisher")
    )
    assert outcome.status == "refused"
    assert outcome.stages[-1] == "grant"
    assert "ApprovalGrant" in (outcome.error or "")


async def test_grant_allowed_when_resolver_returns_match():
    async def grant_ok(command: Command):
        return {"id": "g1", "granted_by": "alice"}

    boundary = make_boundary(grant_resolver=grant_ok)
    outcome = await boundary.execute(
        make_command(requires_grant=True, capability="ai:publisher")
    )
    assert outcome.status == "executed"
    assert "grant" in outcome.stages


async def test_grant_enforced_via_catalog_requires_grant_flag():
    seen: list[str] = []

    async def recording_resolver(command: Command):
        seen.append(command.capability)
        return None  # fail-closed: no matching grant

    boundary = make_boundary(
        tool_catalog={
            "test_tool": {
                "requires_grant": True,
                "required_capability": "ai:publisher",
            }
        },
        grant_resolver=recording_resolver,
    )
    # command does not set requires_grant/capability — resolved from the catalog.
    outcome = await boundary.execute(make_command())
    assert outcome.status == "refused"
    assert outcome.stages[-1] == "grant"
    assert seen == ["ai:publisher"]


async def test_grant_resolver_exception_fails_closed():
    async def boom(command: Command):
        raise RuntimeError("grant backend down")

    boundary = make_boundary(grant_resolver=boom)
    outcome = await boundary.execute(make_command(requires_grant=True))
    assert outcome.status == "refused"
    assert "grant backend down" in (outcome.error or "")
    assert outcome.stages[-1] == "grant"


async def test_grant_stage_skipped_when_not_required():
    calls: list[Command] = []

    async def recording_resolver(command: Command):
        calls.append(command)
        return None

    boundary = make_boundary(grant_resolver=recording_resolver)
    outcome = await boundary.execute(make_command())  # requires_grant=False
    assert outcome.status == "executed"
    assert calls == []  # resolver never invoked
    assert "grant" in outcome.stages  # stage recorded but a no-op


async def test_persist_writes_ledger_and_event_bus():
    ledger = _FakeLedger()
    event_bus = _FakeEventBus()
    boundary = make_boundary(ledger=ledger, event_bus=event_bus)

    outcome = await boundary.execute(make_command())

    assert outcome.status == "executed"
    assert len(ledger.rows) == 1
    assert outcome.event_ids == ["row-1"]
    assert len(event_bus.events) == 1
    assert event_bus.events[0][0] == "command.executed"


async def test_to_action_outcome_maps_engine_shape():
    boundary = make_boundary()
    outcome = await boundary.execute(make_command())
    ao = outcome.to_action_outcome()
    assert ao["status"] == "executed"
    assert ao["result"] == {"ok": True}
    assert ao["event_ids"] == []
    assert "confirmation_token" in ao
    assert "error" in ao
