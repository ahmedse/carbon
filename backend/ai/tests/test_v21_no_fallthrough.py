"""IRP-8 / IF-08 (V21-1) — no fallthrough on a v21 Chat turn.

On ``PULSE_UNDERSTAND=v21`` the Decision is the one pipeline (ADR-0056). A
Chat turn the Decision did not finish must not be answered by the legacy spine
(``runner_s2_plan`` / ``runner_s3_s5`` / ``runner_s6``); it returns the typed,
visible error (ADR-0053) and names the miss on the ledger so a live run
(IB-10) can count it. Agent keeps the planner path.

Covers the three deliverables:

* (a) a v21 Chat turn with no Decision finish never reaches ``runner_s6``;
* (b) the fallthrough marker is emitted when a legacy path would answer;
* (c) an absent-field bound read returns the typed unknown (IRP-5 / IF-04).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from ai.engine.agent.surface import Surface
from ai.engine.cognition.plan.export_bind import render_bound_catalog_read
from ai.engine.cognition.turn.catalog_render import render_catalog_read
from ai.engine.cognition.turn.runner import TurnPipelineRunner
from ai.engine.cognition.turn.runner_helpers import _signal
from ai.engine.cognition.turn.runner_pre_s1 import (
    _unfinished_v21_decision,
    _v21_chat_no_fallthrough,
)
from ai.engine.cognition.turn.understand import understand_mode
from ai.engine.cognition.turn.witnesses import TurnLedger
from ai.engine.pack_vocab import bind_pack


# ── (a) + (b): a Decision miss never reaches the legacy spine ────────────────

class _MissRunner(TurnPipelineRunner):
    """A Chat runner whose Decision records a miss and returns no exit.

    Every soft exit is stubbed to ``None`` so the only thing that can answer
    the turn is the pre-S1 boundary (the real code under test).
    """

    async def _try_plan_status_answer(self, **kwargs):
        return None

    async def _try_next_step_offer(self, **kwargs):
        return None

    async def _try_zero_llm_surface(self, **kwargs):
        return None

    async def _try_v21_understand(self, **kwargs):
        # The exact shape ``_try_v21_understand`` leaves when the Decision did
        # not finish: an un-fired signal and ``None``.
        _signal(kwargs["ledger"], "v21_understand", False, reason="fallthrough", ops=[])
        return None


def _v21_miss(ledger) -> str:
    """The same derivation ``engine_runtime`` uses for the ``v21_miss`` field."""
    return next(
        (
            str((s.get("detail") or {}).get("reason") or "")
            for s in (getattr(ledger, "decision_signals", None) or [])
            if isinstance(s, dict)
            and s.get("gate") == "v21_understand"
            and not s.get("fired")
        ),
        "",
    )


def _spy_stages(monkeypatch) -> list[str]:
    """Replace S1–S6 with spies that fail loudly if the spine is entered."""
    import ai.engine.cognition.turn.runner_s1 as s1
    import ai.engine.cognition.turn.runner_s2_plan as s2
    import ai.engine.cognition.turn.runner_s3_s5 as s3
    import ai.engine.cognition.turn.runner_s6 as s6

    calls: list[str] = []

    def boom(name):
        async def _stage(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"legacy spine reached after a v21 Decision miss: {name}")
        return _stage

    monkeypatch.setattr(s1, "run_s1_intent", boom("s1"))
    monkeypatch.setattr(s2, "run_s2_and_plan_gates", boom("s2"))
    monkeypatch.setattr(s3, "run_s3_through_s5", boom("s3"))
    monkeypatch.setattr(s6, "run_s6_finalize", boom("s6"))
    return calls


def _quiet_broadcast(monkeypatch):
    import ai.engine.cognition.notifier as notifier

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(notifier, "broadcast_run_event", _noop)
    import ai.engine.cognition.turn.process_brief as process_brief

    monkeypatch.setattr(process_brief, "try_process_briefing", lambda *a, **k: None)


def _run_turn(process_mode: str = "ask"):
    runner = _MissRunner(executor=object())
    return asyncio.run(runner._run_metered(
        instance_id="nibras",
        conversation_id="c-v21nofall",
        user_message="hello there",
        host_user_id="emp_1067",
        process_mode=process_mode,
        meter=None,
        state_ctx=None,
    ))


def test_v21_chat_miss_never_reaches_the_legacy_spine(monkeypatch):
    """(a): a Chat turn with no Decision finish never reaches ``runner_s6``."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    _quiet_broadcast(monkeypatch)
    calls = _spy_stages(monkeypatch)

    response, ledger = _run_turn(process_mode="ask")

    assert calls == [], "a v21 Chat miss fell through to the legacy spine"
    assert response is not None
    assert response.text, "the miss must be a visible, typed answer"


def test_v21_chat_miss_emits_the_fallthrough_marker(monkeypatch):
    """(b): the marker a live IB-10 run reads is on the ledger."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    _quiet_broadcast(monkeypatch)
    _spy_stages(monkeypatch)

    response, ledger = _run_turn(process_mode="ask")

    assert understand_mode() == "v21"
    assert ledger.fell_through is True
    assert ledger.fallthrough_reason == "fallthrough"
    # The field ``engine_runtime`` surfaces as ``v21_miss`` (IB-10's input).
    assert _v21_miss(ledger) == "fallthrough"
    assert _v21_miss(ledger) in ("fallthrough", "unrepairable", "committed_route_skipped")
    assert response is not None


def test_agent_surface_keeps_the_spine(monkeypatch):
    """Agent (Planner) is preserved: a non-Chat surface is never intercepted."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    _quiet_broadcast(monkeypatch)
    import ai.engine.cognition.turn.runner_s1 as s1
    import ai.engine.cognition.turn.runner_s2_plan as s2
    import ai.engine.cognition.turn.runner_s3_s5 as s3
    import ai.engine.cognition.turn.runner_s6 as s6

    entered: list[str] = []

    def spy(name):
        async def _stage(runner, st, **kwargs):
            entered.append(name)
            return SimpleNamespace(text=f"legacy {name}"), kwargs["ledger"]
        return _stage

    monkeypatch.setattr(s1, "run_s1_intent", spy("s1"))
    monkeypatch.setattr(s2, "run_s2_and_plan_gates", spy("s2"))
    monkeypatch.setattr(s3, "run_s3_through_s5", spy("s3"))
    monkeypatch.setattr(s6, "run_s6_finalize", spy("s6"))

    response, ledger = _run_turn(process_mode="agent")

    assert entered == ["s1"], "Agent fell out of its planner path"
    assert response.text == "legacy s1"
    assert not ledger.fell_through


# ── the boundary in isolation ────────────────────────────────────────────────

def _ledger_with(reason: str) -> TurnLedger:
    ledger = TurnLedger()
    _signal(ledger, "v21_understand", False, reason=reason, ops=[])
    return ledger


@pytest.mark.parametrize("reason", ["fallthrough", "unrepairable", "committed_route_skipped"])
def test_a_recorded_miss_is_read_off_the_ledger(reason):
    assert _unfinished_v21_decision(_ledger_with(reason)) == reason


@pytest.mark.parametrize("reason", ["plan_dial", "shadow_only", ""])
def test_a_deliberate_skip_is_not_a_miss(reason):
    assert _unfinished_v21_decision(_ledger_with(reason)) == ""


def test_a_fired_signal_is_not_a_miss():
    ledger = TurnLedger()
    _signal(ledger, "v21_understand", True, reason="fallthrough")
    assert _unfinished_v21_decision(ledger) == ""


def test_chat_plan_dial_skip_is_not_intercepted(monkeypatch):
    """The Plan drafter owns the Plan dial; its skip is not a fallthrough."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    ledger = _ledger_with("plan_dial")
    st = SimpleNamespace(user_message="a full report")
    assert _v21_chat_no_fallthrough(
        st, ledger=ledger, state=None, surface=Surface.CHAT_PLAN,
    ) is None
    assert not ledger.fell_through


def test_legacy_mode_is_never_intercepted(monkeypatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    ledger = _ledger_with("fallthrough")
    st = SimpleNamespace(user_message="hello")
    assert _v21_chat_no_fallthrough(
        st, ledger=ledger, state=None, surface=Surface.CHAT_ASK,
    ) is None
    assert not ledger.fell_through


# ── (c): an absent field in a bound read is an explicit unknown ──────────────

_PROFILE_ENTRY = {
    "name": "get_my_profile",
    "kind": "detail",
    "empty_render": "no_detail_row",
    "returns": ["full_name", "employee_no", "job_title", "basic_salary"],
    "sensitive_fields": ["basic_salary"],
    "field_labels": {
        "full_name": {"en": "Name", "ar": "الاسم"},
        "basic_salary": {"en": "Basic salary", "ar": "الراتب الأساسي"},
    },
}
# The host record carries no ``basic_salary`` line.
_PROFILE_RECORD = {
    "id": 17, "employee_no": "2378", "full_name": "Ali", "job_title": "Director",
}


def test_absent_field_bound_read_returns_the_typed_unknown():
    """(c): the pack's own empty render, never ``None`` / a raw record dump."""
    with bind_pack("nibras"):
        rendered = render_bound_catalog_read(
            {"result": _PROFILE_RECORD}, "get_my_profile", "en",
            catalog_entry=_PROFILE_ENTRY, fields=["basic_salary"],
        )
    assert rendered, "an absent asked field fell through to the writer"
    assert rendered == "That record was not found."
    assert "employee_no=" not in rendered and "id=" not in rendered


def test_undeclared_field_bound_read_is_an_explicit_unknown():
    with bind_pack("nibras"):
        rendered = render_bound_catalog_read(
            {"result": _PROFILE_RECORD}, "get_my_profile", "en",
            catalog_entry=_PROFILE_ENTRY, fields=["tes_score"],
        )
    assert rendered == "That record was not found."


def test_absent_field_unknown_follows_the_message_language():
    with bind_pack("nibras"):
        rendered = render_bound_catalog_read(
            {"result": _PROFILE_RECORD}, "get_my_profile", "ar",
            catalog_entry=_PROFILE_ENTRY, fields=["tes_score"],
        )
    assert rendered == "لم يُعثر على ذلك السجل."


def test_partial_absent_field_is_an_unknown_cell_not_a_blank():
    with bind_pack("nibras"):
        rendered = render_bound_catalog_read(
            {"result": _PROFILE_RECORD}, "get_my_profile", "en",
            catalog_entry=_PROFILE_ENTRY, fields=["full_name", "basic_salary"],
        )
    assert "Ali" in rendered
    assert "|  |" not in rendered, "an absent asked field was left blank"
    assert "That record was not found." in rendered


def test_direct_renderer_still_hands_an_unmatched_ask_to_the_writer():
    """The v21 bound-read contract does not change the direct renderer."""
    with bind_pack("nibras"):
        rendered = render_catalog_read(
            {"result": _PROFILE_RECORD}, "get_my_profile", "en",
            catalog_entry=_PROFILE_ENTRY, fields=["tes_score"],
        )
    assert rendered is None
