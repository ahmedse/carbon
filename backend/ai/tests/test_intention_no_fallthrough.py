"""IB-09 — no-fallthrough unit (PULSE-INTENTION-CONTRACT Phase 1 + Phase 2).

A committed route under ``PULSE_UNDERSTAND=v21`` must not be answered by the
legacy spine while the Decision is skipped *silently*. The one committed route
whose v21 exit is superseded — ``REPORT_CLARIFY`` (V21-2) — is no longer emitted
by the router on v21 (Phase 2), so a broad-report Ask flows to the Decision.
The guard ``_superseded_committed_exit`` stays defensive: if that committed
shape is ever constructed, its skip is recorded with a reason so the
fallthrough counter sees it, never a silent S3–S6 answer.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from ai.engine.cognition.turn.exit_policy import may_stage
from ai.engine.cognition.turn.router import (
    ProcessMode,
    RouteDecision,
    RouteKind,
    TurnRouter,
)
from ai.engine.cognition.turn.runner_metered_state import MeteredTurnState
from ai.engine.cognition.turn.runner_pre_s1 import (
    _superseded_committed_exit,
    run_pre_s1_gates,
)
from ai.engine.cognition.turn.witnesses import TurnLedger

_BROAD_REPORT = "I need a full report about salaries in the company"


class _Runner:
    """Pre-S1 soft surfaces must not run on a committed route.

    ``executor`` is set so the v21 understand call is skipped *only* because the
    route is committed — the assertion would fire if that gate were removed.
    """

    executor = SimpleNamespace()

    async def _try_v21_understand(self, **kwargs):
        raise AssertionError("Decision ran on a committed route with a superseded exit")


async def _noop(*args, **kwargs):
    return None


def _route(message: str, mode: str = "ask"):
    return TurnRouter().decide(message=message, process_mode=mode, state=None)


def _committed_report_route() -> RouteDecision:
    """The V21-2 shape as a fixture — a committed ``REPORT_CLARIFY`` route.

    On v21 the router no longer emits it (Phase 2), so the test builds it
    directly. ``_superseded_committed_exit`` must still recognize and record it
    so a silent skip cannot return.
    """
    return RouteDecision(
        kind=RouteKind.REPORT_CLARIFY,
        mode=ProcessMode.ASK,
        message=_BROAD_REPORT,
        committed=True,
        reason="broad_report",
    )


def _run_pre_s1(turn_route, runner=None):
    from ai.engine.core.config import get_settings

    ledger = TurnLedger()
    st = MeteredTurnState(user_message=turn_route.message, dense_thinking=False)
    out = asyncio.run(run_pre_s1_gates(
        runner or _Runner(),
        st,
        instance_id="nibras",
        conversation_id="c-ib09",
        host_user_id="emp_1067",
        process_mode="ask",
        surface=None,
        page_context="",
        conversation_history=[],
        instance_config=None,
        user_info=None,
        progress_callback=None,
        stream_callback=None,
        model=None,
        temperature=None,
        knowledge_items=None,
        scope=None,
        process_state=None,
        meter=None,
        state_ctx=None,
        budget=None,
        turn_id="t-ib09",
        t0=0.0,
        ledger=ledger,
        staged=[],
        settings=get_settings(),
        turn_route=turn_route,
        original_user_message=turn_route.message,
        state=None,
        _broadcast_run=_noop,
    ))
    return out, ledger, st


def _recorded_fallthroughs(ledger):
    return [
        s for s in (ledger.decision_signals or [])
        if s.get("gate") == "v21_understand" and not s.get("fired")
        and s.get("detail", {}).get("reason") == "committed_route_skipped"
    ]


def test_v21_report_clarify_is_not_committed(monkeypatch):
    """The V21-2 fix: a broad-report Ask is not commit-typed on v21.

    The recorded shape stays recognized so the guard cannot regress silently:
    if a committed ``REPORT_CLARIFY`` is ever constructed, its superseded exit
    is still named.
    """
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    route = _route(_BROAD_REPORT)
    assert route.kind is RouteKind.NORMAL
    assert route.committed is False
    assert may_stage("typed_router") is False
    assert _superseded_committed_exit(_committed_report_route()) == "typed_router"


def test_report_clarify_still_commits_on_legacy(monkeypatch):
    """Legacy is unchanged: the typed report-focus question still commits."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    route = _route(_BROAD_REPORT)
    assert route.kind is RouteKind.REPORT_CLARIFY
    assert route.committed is True
    assert route.open_question is not None
    assert _superseded_committed_exit(route) == ""


def test_a_superseded_committed_route_is_recorded_not_silent(monkeypatch):
    """IB-09 core: the skip is recorded with a reason, never a silent S3–S6 answer.

    Phase 2 stops the router from emitting this committed shape on v21, so the
    test builds it directly. The recording hook stays defensive; this keeps the
    IB-09 coverage now that the shape is unreachable through routing.
    """
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    out, ledger, _ = _run_pre_s1(_committed_report_route())

    assert out is None
    recorded = _recorded_fallthroughs(ledger)
    assert recorded, "a committed route skipped the Decision with no recorded reason"
    detail = recorded[0]["detail"]
    assert detail["reason"] == "committed_route_skipped"
    assert detail["route"] == "report_clarify"
    assert detail["exit_gate"] == "typed_router"


def test_a_kept_or_normal_route_is_not_recorded_as_a_fallthrough(monkeypatch):
    """Only a superseded committed exit is a fallthrough."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    # Phase 2: the broad-report ask is NORMAL on v21, so nothing is skipped.
    assert _superseded_committed_exit(_route(_BROAD_REPORT)) == ""
    assert _superseded_committed_exit(_route("hello there")) == ""
    # A committed route whose exit is owned (Plan process) is not a fallthrough.
    plan = _route("راجع قروضي المفتوحة", mode="plan")
    assert plan.kind is RouteKind.PLAN_PROCESS and plan.committed
    assert _superseded_committed_exit(plan) == ""

    ledger = TurnLedger()
    assert _recorded_fallthroughs(ledger) == []


def test_v21_2_report_clarify_reaches_the_decision(monkeypatch):
    """The Phase 2 target: a broad-report Ask on v21 reaches the Decision."""
    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    route = _route(_BROAD_REPORT)
    assert route.committed is False
    called: dict = {}

    class _RecordingRunner(_Runner):
        async def _try_v21_understand(self, **kwargs):
            called["ran"] = True
            return SimpleNamespace(text="answer"), kwargs["ledger"]

    out, ledger, _ = _run_pre_s1(route, runner=_RecordingRunner())
    assert called.get("ran") is True, "v21 broad-report fell through to the legacy spine"
    assert out is not None
    # The V21-2 skip is gone: not recorded as a committed route skipped.
    assert _recorded_fallthroughs(ledger) == []
