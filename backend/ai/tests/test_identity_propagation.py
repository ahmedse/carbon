"""PEC-ID-1 — identity propagation / actor_chain attribution on PDP audit rows.

Asserts:
* every PDP decision persists actor_chain + user_id + instance_id + request_id
* CBAC deny/allow outcomes are unchanged by attribution kwargs
* inproc token form remains documented on the engine hop
"""
from __future__ import annotations

import pytest
from asgiref.sync import sync_to_async

from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports import Decision
from ai.identity_propagation import build_actor_chain
from ai.models.pdp import PolicyDecisionRow
from ai.pdp import PDP
from ai.protocol import Scope

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
async def test_pdp_persists_actor_chain_attribution():
    pdp = PDP()
    chain = build_actor_chain(
        user_id="42",
        instance_id="carbon",
        request_id="req-abc-123",
        tool="call_host_api",
    )
    result = await pdp.decide(
        "42",
        "call_host_api",
        ["people.list_employees"],
        autonomy="auto",
        actor_chain=chain,
        request_id="req-abc-123",
        instance_id="carbon",
        host_user_id="42",
    )
    assert result["decision"] is Decision.ALLOW

    row = await sync_to_async(PolicyDecisionRow.objects.get, thread_sensitive=True)(
        principal="42", action="call_host_api"
    )
    assert row.request_id == "req-abc-123"
    assert row.instance_id == "carbon"
    assert row.host_user_id == "42"
    assert isinstance(row.actor_chain, list)
    assert len(row.actor_chain) >= 2
    assert row.actor_chain[0]["role"] == "user"
    assert row.actor_chain[0]["id"] == "42"
    assert row.actor_chain[1]["role"] == "engine"
    assert row.actor_chain[1]["id"] == "inproc"
    assert row.actor_chain[1]["token_form"] == "inproc:carbon:42"
    assert row.actor_chain[2]["role"] == "tool"
    assert row.actor_chain[2]["id"] == "call_host_api"


@pytest.mark.asyncio
async def test_attribution_does_not_change_cbac_deny():
    """Default-deny still refuses unknown actions even with full attribution."""
    pdp = PDP()
    chain = build_actor_chain(
        user_id="alice",
        instance_id="nibras",
        request_id="req-deny",
        tool="shutdown_system",
    )
    with_attr = await pdp.decide(
        "alice",
        "shutdown_system",
        ["reactor-1"],
        autonomy="auto",
        actor_chain=chain,
        request_id="req-deny",
        instance_id="nibras",
        host_user_id="alice",
    )
    without = await pdp.decide(
        "alice",
        "shutdown_system",
        ["reactor-1"],
        autonomy="auto",
    )
    assert with_attr["decision"] is Decision.REFUSE
    assert without["decision"] is Decision.REFUSE
    assert with_attr["decision"] is without["decision"]
    assert "default deny" in with_attr["reason"].lower()


@pytest.mark.asyncio
async def test_attribution_does_not_change_cbac_allow():
    pdp = PDP()
    chain = build_actor_chain(
        user_id="bob",
        instance_id="carbon",
        request_id="req-allow",
        action="read",
    )
    with_attr = await pdp.decide(
        "bob",
        "read",
        ["tbl"],
        autonomy="human_only",
        actor_chain=chain,
        request_id="req-allow",
        instance_id="carbon",
        host_user_id="bob",
    )
    without = await pdp.decide("bob", "read", ["tbl"], autonomy="human_only")
    assert with_attr["decision"] is Decision.ALLOW
    assert without["decision"] is Decision.ALLOW


@pytest.mark.asyncio
async def test_boundary_mints_request_id_and_persists_chain():
    """Host-effect via CommandBoundary stamps attribution on the PDP row."""
    calls: list[Command] = []

    async def _exec(command: Command):
        calls.append(command)
        return {"ok": True}

    boundary = CommandBoundary(
        pdp=PDP(),
        executor=_exec,
        tool_catalog={"call_host_api": True},
    )
    outcome = await boundary.execute(
        Command(
            principal="99",
            scope=Scope(user_identifier="99"),
            tool="call_host_api",
            action="call_host_api",
            objects=["api"],
            requires_confirmation=False,
            autonomy="auto",
            instance_id="carbon",
            host_user_id="99",
            # request_id intentionally empty → minted
        )
    )
    assert outcome.status in ("executed", "confirmed")
    assert calls and calls[0].request_id  # minted on the command

    row = await sync_to_async(
        PolicyDecisionRow.objects.filter(principal="99").latest, thread_sensitive=True
    )("created_at")
    assert row.request_id == calls[0].request_id
    assert row.instance_id == "carbon"
    assert row.host_user_id == "99"
    assert row.actor_chain[0]["role"] == "user"
    assert row.actor_chain[1]["token_form"] == "inproc:carbon:99"
