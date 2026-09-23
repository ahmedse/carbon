"""PV2-6A — G5 Coherence gate: stub-per-turn + threshold failures."""
from __future__ import annotations

import asyncio

import pytest

from ai.eval.multiturn.bank import Turn
from ai.eval.multiturn.runner import (
    BankReport,
    ScriptResult,
    TurnResult,
    _latency_histogram,
    _make_stub_llm_factory,
    exit_code_for,
    g5_failures,
)


pytestmark = pytest.mark.eval_multiturn


def test_stub_stays_on_the_same_turn_across_llm_calls():
    turns = [
        Turn(user="one", stub_reply="FIRST"),
        Turn(user="two", stub_reply="SECOND"),
    ]
    factory = _make_stub_llm_factory(turns)
    factory.set_turn(0)
    client = factory()

    async def twice():
        a = await client.chat.completions.create()
        b = await client.chat.completions.create()
        return a.choices[0].message.content, b.choices[0].message.content

    first, again = asyncio.run(twice())
    assert first == "FIRST"
    assert again == "FIRST"
    factory.set_turn(1)
    later = asyncio.run(client.chat.completions.create()).choices[0].message.content
    assert later == "SECOND"


def _report(*, router=1.0, slot=1.0, p50=1.0, over=0, measured=10, reask=True):
    expect = type("E", (), {
        "must_not_reask_slots": ["amount"] if reask else [],
        "language": "en",
        "decision_in": ["answer"],
        "mentions_any": [],
        "mentions_none": [],
        "max_llm_calls": 2,
    })()
    turns = []
    for i in range(measured):
        turns.append(
            TurnResult(
                user_input=f"t{i}",
                stub_reply="ok",
                expect=expect,
                decision="answer",
                decision_ok=router >= 1.0 or i > 0,
                llm_calls=int(p50),
                llm_calls_ok=over == 0,
                latency_ms=80.0,
                language_ok=True,
                mentions_ok=True,
                passed=True,
            )
        )
    if router < 1.0 and turns:
        turns[0].decision_ok = False
    sr = ScriptResult(script_id="g5", turns=turns, passed=True)
    report = BankReport(scripts_run=1, scripts_passed=1, scripts=[sr])
    report.router_agreement = router
    report.slot_carry_over = slot
    report.llm_calls_p50 = p50
    report.turns_over_budget = over
    report.total_turns = measured
    report.turns_passed = measured
    return report


def test_g5_passes_on_contract_thresholds():
    assert g5_failures(_report()) == []
    assert exit_code_for(_report(), gate=True) == 0


def test_g5_fails_on_intentional_router_break():
    report = _report(router=0.80)
    misses = g5_failures(report)
    assert any("router_agreement" in m for m in misses)
    assert exit_code_for(report, gate=True) == 1
    assert exit_code_for(report, gate=False) == 0


def test_g5_fails_on_llm_p50_and_over_budget():
    assert any("llm_calls_p50" in m for m in g5_failures(_report(p50=3)))
    assert any("over_budget" in m for m in g5_failures(_report(over=3)))


def test_g5_fails_when_latency_histogram_missing():
    report = _report()
    for turn in report.scripts[0].turns:
        turn.latency_ms = None
    misses = g5_failures(report)
    assert any("latency_histogram" in m for m in misses)


def test_latency_histogram_buckets_split_at_four_seconds():
    hist = _latency_histogram([10, 249, 250, 999, 2000, 3999, 4000, 8000])
    assert hist["0-250ms"] == 2
    assert hist["250-500ms"] == 1
    assert hist["500-1000ms"] == 1
    assert hist["1000-2000ms"] == 0
    assert hist["2000-4000ms"] == 2
    assert hist["4000ms+"] == 2
