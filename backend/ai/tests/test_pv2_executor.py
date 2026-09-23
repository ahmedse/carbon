"""L3 — staged gates: Arbiter picks the body, the loser does not speak."""
from __future__ import annotations

from types import SimpleNamespace

from ai.engine.cognition.turn.executor import StagedExit, pick_staged


def _resp(text: str):
    return SimpleNamespace(text=text)


def test_refuse_beats_nav_when_both_staged():
    signals = [
        {"gate": "nav_fast_path", "fired": True},
        {"gate": "off_limits", "fired": True},
    ]
    staged = [
        StagedExit("navigate", "nav_fast_path", _resp("open Leave")),
        StagedExit("refuse", "off_limits", _resp("out of scope")),
    ]
    picked = pick_staged(signals, staged)
    assert picked is not None
    assert picked.decision == "refuse"
    assert picked.response.text == "out of scope"


def test_only_nav_returns_nav():
    signals = [{"gate": "nav_fast_path", "fired": True}]
    staged = [StagedExit("navigate", "nav_fast_path", _resp("open Leave"))]
    picked = pick_staged(signals, staged)
    assert picked is not None
    assert picked.decision == "navigate"


def test_empty_stage_continues_pipeline():
    assert pick_staged([{"gate": "nav_fast_path", "fired": False}], []) is None


def test_handoff_beats_nav_when_both_staged():
    signals = [
        {"gate": "nav_fast_path", "fired": True},
        {"gate": "chat_handoff", "fired": True},
    ]
    staged = [
        StagedExit("navigate", "nav_fast_path", _resp("open Loans")),
        StagedExit("handoff_agent", "chat_handoff", _resp("switch to Agent")),
    ]
    picked = pick_staged(signals, staged)
    assert picked is not None
    assert picked.decision == "handoff_agent"
