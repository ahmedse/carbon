"""PV2-4A/4B — Arbiter precedence, conflict pairs, on/shadow/legacy."""
from __future__ import annotations

import pytest

from ai.engine.cognition.state_store import ConversationState, update_state_from_turn
from ai.engine.cognition.turn.arbiter import Arbiter, TurnDecision, shadow_compare
from ai.engine.cognition.turn.runner import _finalize_meter
from ai.engine.cognition.turn.witnesses import TurnLedger


@pytest.fixture(autouse=True)
def _fresh_settings_cache():
    from ai.engine.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _sigs(*fired: str, extra: list[dict] | None = None) -> list[dict]:
    out = [{"gate": g, "fired": True} for g in fired]
    for g in ("off_limits", "pending_confirm", "process_brief", "chat_handoff",
              "nav_fast_path", "deixis", "weather_force", "ess_bound_self_read"):
        if g not in fired:
            out.append({"gate": g, "fired": False})
    if extra:
        out.extend(extra)
    return out


def test_precedence_refuse_beats_nav_and_handoff():
    arb = Arbiter()
    assert arb.decide(_sigs("off_limits", "nav_fast_path", "chat_handoff")) == TurnDecision.REFUSE
    assert arb.decide(_sigs("pending_confirm", "chat_handoff")) == TurnDecision.MEMORY_CONFIRM
    assert arb.decide(_sigs("process_brief", "nav_fast_path")) == TurnDecision.PROCESS_BRIEF
    assert arb.decide(_sigs("chat_handoff", "nav_fast_path")) == TurnDecision.HANDOFF_AGENT
    assert arb.decide(_sigs("nav_fast_path", "deixis")) == TurnDecision.NAVIGATE
    assert arb.decide(_sigs("deixis")) == TurnDecision.CLARIFY
    assert arb.decide(_sigs("weather_force")) == TurnDecision.TOOL_ANSWER
    assert arb.decide(_sigs("ess_bound_self_read")) == TurnDecision.TOOL_ANSWER
    assert arb.decide(_sigs()) == TurnDecision.ANSWER


def test_conflict_pair_topic_refuse_vs_nav():
    """Same utterance historically raced nav vs refuse — refuse wins."""
    signals = [
        {"gate": "nav_fast_path", "fired": True, "detail": {"action": "open_leave"}},
        {"gate": "off_limits", "fired": True, "detail": {"zone": "off_limits"}},
    ]
    assert Arbiter().decide(signals) == TurnDecision.REFUSE
    shadow = shadow_compare("navigate", signals)
    assert shadow["agree"] is False
    assert shadow["arbiter"] == "refuse"
    assert shadow["legacy"] == "navigate"


def test_conflict_pair_handoff_vs_process_brief():
    signals = _sigs("process_brief", "chat_handoff")
    assert Arbiter().decide(signals) == TurnDecision.PROCESS_BRIEF
    # Legacy Chat now hands off writes; Arbiter still ranks process_brief higher.
    shadow = shadow_compare("handoff_agent", signals)
    assert shadow["agree"] is False
    assert shadow["arbiter"] == "process_brief"


def test_shadow_agree_when_legacy_matches():
    signals = _sigs("chat_handoff")
    shadow = shadow_compare("handoff_agent", signals)
    assert shadow["agree"] is True
    assert shadow["arbiter"] == "handoff_agent"


def test_finalize_meter_records_shadow_without_changing_legacy():
    ledger = TurnLedger()
    ledger.decision_signals = _sigs("chat_handoff")
    _finalize_meter(ledger, meter=object(), decision="handoff_agent")
    assert ledger.turn_decision == "handoff_agent"
    assert isinstance(ledger.arbiter_shadow, dict)
    assert ledger.arbiter_shadow["legacy"] == "handoff_agent"
    assert ledger.arbiter_shadow["arbiter"] == "handoff_agent"
    assert ledger.arbiter_shadow["agree"] is True


def _arbiter_mode(monkeypatch, mode: str) -> None:
    from ai.engine.core.config import get_settings

    monkeypatch.setenv("PULSE_ARBITER", mode)
    get_settings.cache_clear()


def test_on_mode_records_arbiter_when_gates_conflict(monkeypatch):
    """4B: several fired gates → recorded decision is Arbiter precedence."""
    _arbiter_mode(monkeypatch, "on")
    ledger = TurnLedger()
    ledger.decision_signals = _sigs("off_limits", "nav_fast_path")
    _finalize_meter(ledger, meter=object(), decision="navigate")
    assert ledger.turn_decision == "refuse"
    assert ledger.arbiter_shadow["agree"] is False
    assert ledger.arbiter_shadow["arbiter"] == "refuse"


def test_legacy_kill_switch_keeps_caller_decision(monkeypatch):
    _arbiter_mode(monkeypatch, "legacy")
    ledger = TurnLedger()
    ledger.decision_signals = _sigs("off_limits", "nav_fast_path")
    _finalize_meter(ledger, meter=object(), decision="navigate")
    assert ledger.turn_decision == "navigate"
    assert ledger.arbiter_shadow is None


def test_shadow_keeps_caller_label(monkeypatch):
    _arbiter_mode(monkeypatch, "shadow")
    ledger = TurnLedger()
    ledger.decision_signals = _sigs("off_limits", "nav_fast_path")
    _finalize_meter(ledger, meter=object(), decision="navigate")
    assert ledger.turn_decision == "navigate"
    assert ledger.arbiter_shadow["arbiter"] == "refuse"


def test_clarify_and_tools_stay_themselves_when_on():
    clarify = TurnLedger()
    clarify.decision_signals = [{"gate": "chat_clarify", "fired": True}]
    _finalize_meter(clarify, meter=object(), decision="clarify")
    assert clarify.turn_decision == "clarify"

    tools = TurnLedger()
    tools.decision_signals = [{"gate": "tools_executed", "fired": True}]
    _finalize_meter(tools, meter=object(), decision="tool_answer")
    assert tools.turn_decision == "tool_answer"


def test_state_persists_legacy_and_arbiter():
    state = ConversationState()
    update_state_from_turn(
        state,
        decision="navigate",
        fired_gates=["nav_fast_path"],
        arbiter_shadow={"legacy": "navigate", "arbiter": "refuse", "agree": False},
    )
    row = state.decisions[-1]
    assert row["decision"] == "navigate"
    assert row["arbiter"] == "refuse"
    assert row["agree"] is False
