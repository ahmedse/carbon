"""P2-07 — PDP v1 behaviour tests (offline, deterministic, no LLM/network).

Covers the fixed semantics from ``ai/engine/ports/policy.py``:

* default deny (no matching permit → refuse)
* forbid overrides permit (deny + permit both match → refuse)
* mandatory policy evaluation error → refuse (fail-closed)
* every decision is persisted (audit row with decision/reason/policy_version)
* the three core Decision values are each produced by some scenario
* the autonomy dial meaningfully changes the outcome
"""
from __future__ import annotations

import pytest
from asgiref.sync import sync_to_async

from ai.engine.ports.policy import Decision
from ai.models.pdp import PolicyDecisionRow
from ai.pdp import DEFAULT_POLICIES, DEFAULT_POLICY_VERSION, PDP, Policy

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
async def test_default_deny_when_no_policy_matches():
    pdp = PDP()
    result = await pdp.decide(
        "alice", "shutdown_system", ["reactor-1"], autonomy="auto"
    )
    assert result["decision"] is Decision.REFUSE
    assert result["policy_version"] == DEFAULT_POLICY_VERSION
    assert "default deny" in result["reason"].lower()


@pytest.mark.asyncio
async def test_forbid_overrides_permit():
    # "delete" matches BOTH the mutating permit and the destructive deny.
    # The deny must win even at full autonomy, where the permit would allow.
    pdp = PDP()
    result = await pdp.decide("alice", "delete", ["ledger"], autonomy="auto")
    assert result["decision"] is Decision.REFUSE
    assert "destructive" in result["reason"].lower()


@pytest.mark.asyncio
async def test_mandatory_policy_error_refuses():
    def _boom(**kwargs) -> bool:
        raise RuntimeError("policy exploded")

    failing = Policy(
        name="mandatory-broken",
        effect="permit",
        reason="never reached",
        mandatory=True,
        matcher=_boom,
    )
    pdp = PDP(policies=(failing, *DEFAULT_POLICIES))

    # "read" would otherwise be allowed; the mandatory failure must fail-closed.
    result = await pdp.decide("alice", "read", ["tbl"], autonomy="human_only")
    assert result["decision"] is Decision.REFUSE
    assert "mandatory-broken" in result["reason"]
    assert "RuntimeError" in result["reason"]


@pytest.mark.asyncio
async def test_every_decision_is_persisted():
    pdp = PDP()
    result = await pdp.decide("alice", "read", ["tbl"], autonomy="human_only")

    row = await sync_to_async(PolicyDecisionRow.objects.get, thread_sensitive=True)(
        principal="alice"
    )
    assert row.decision == result["decision"].value == "allow"
    assert row.reason == result["reason"]
    assert row.policy_version == DEFAULT_POLICY_VERSION
    assert row.resource_objects == ["tbl"]
    assert row.autonomy == "human_only"


@pytest.mark.asyncio
async def test_three_core_decision_values():
    pdp = PDP()

    allow = await pdp.decide("u", "read", ["tbl"], autonomy="human_only")
    confirm = await pdp.decide("u", "create", ["tbl"], autonomy="act_confirm")
    ask = await pdp.decide("u", "update", ["tbl"], autonomy="human_only")
    refuse = await pdp.decide("u", "unknown_action", ["tbl"], autonomy="auto")

    assert allow["decision"] is Decision.ALLOW
    assert confirm["decision"] is Decision.ALLOW_WITH_CONFIRMATION
    assert ask["decision"] is Decision.ASK
    assert refuse["decision"] is Decision.REFUSE


@pytest.mark.asyncio
async def test_autonomy_dial_changes_outcome():
    pdp = PDP()

    human = await pdp.decide("u", "create", ["tbl"], autonomy="human_only")
    confirm = await pdp.decide("u", "create", ["tbl"], autonomy="act_confirm")
    auto = await pdp.decide("u", "create", ["tbl"], autonomy="auto")

    assert human["decision"] is Decision.ASK
    assert confirm["decision"] is Decision.ALLOW_WITH_CONFIRMATION
    assert auto["decision"] is Decision.ALLOW


@pytest.mark.asyncio
async def test_module_level_decide_matches_protocol():
    from ai import pdp as pdp_module

    result = await pdp_module.decide("bob", "read", ["tbl"], autonomy="human_only")
    assert result["decision"] is Decision.ALLOW
    assert result["policy_version"] == DEFAULT_POLICY_VERSION
