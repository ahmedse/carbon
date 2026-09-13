"""P2-01 — ``engine/ports/`` Protocol surface exists and is importable.

These are structural (typing.Protocol) contracts: the engine depends on their
shape, and P2-02 host adapters must satisfy them.  This test is the terminal
proof that the ten Protocols are defined with their required methods — it does
not test behaviour (there is no implementation yet).
"""
from __future__ import annotations

from typing import Protocol, get_type_hints

import pytest

from ai.engine import ports


EXPECTED_PROTOCOLS = {
    "Clock": {"utcnow"},
    "EpisodicStore": {"record_event", "search", "get_chain", "decay"},
    "LongTermStore": {"store_fact", "retrieve", "supersede_fact", "forget"},
    "OrgMemory": {"get_org_memory_seeds"},
    "SkillStore": {"add", "get", "list_by_user", "list_promoted", "search", "update_status"},
    "LedgerSink": {"record_stage"},
    "EventBus": {"publish", "subscribe"},
    "ProcessRegistry": {"get_process", "register_process", "create_run", "resume_run", "record_event", "get_active_run"},
    "PolicyDecisionPoint": {"decide"},
    "HostActions": {"propose_action", "execute_action"},
}


@pytest.mark.parametrize("name", sorted(EXPECTED_PROTOCOLS))
def test_protocol_is_exported_and_typed(name):
    proto = getattr(ports, name, None)
    assert proto is not None, f"{name} is not exported from ai.engine.ports"
    assert isinstance(proto, type), f"{name} must be a class"
    # typing.Protocol instances have _is_protocol True
    assert getattr(proto, "_is_protocol", False) is True, f"{name} must be a typing.Protocol"


@pytest.mark.parametrize("name,methods", sorted(EXPECTED_PROTOCOLS.items()))
def test_protocol_declares_required_methods(name, methods):
    proto = getattr(ports, name)
    missing = methods - set(dir(proto))
    assert not missing, f"{name} is missing methods: {sorted(missing)}"


def test_pdp_decision_values_match_plan():
    # P2-07 fixes exactly these five outcomes.
    assert {d.value for d in ports.Decision} == {
        "allow",
        "allow_with_confirmation",
        "ask",
        "defer",
        "refuse",
    }


def test_pdp_decide_signature_has_seven_params():
    hints = get_type_hints(ports.PolicyDecisionPoint.decide)
    assert list(hints) == [
        "principal",
        "action",
        "objects",
        "process_state",
        "autonomy",
        "budget",
        "time",
        "return",
    ]
