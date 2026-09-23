"""ESS self-read contract — balance vs history + empty honesty."""
from __future__ import annotations

import yaml
from pathlib import Path

from ai.engine.cognition.turn.ess_read import (
    LEAVE_BALANCE_API,
    LEAVE_HISTORY_API,
    LOAN_HISTORY_API,
    PAYSLIP_API,
    empty_history_misread,
    ess_self_read_topic,
    leave_history_asked,
    leave_topic_asked,
    loan_topic_asked,
    preferred_self_api,
)
from ai.engine.cognition.turn.intent import (
    IntentCandidate,
    IntentResolution,
    _apply_ess_self_read_override,
    _apply_named_leave_override,
)
from ai.engine.cognition.turn.navigation import resolve_navigation


def _nibras_cfg() -> dict:
    path = (
        Path(__file__).resolve().parents[1]
        / "engine"
        / "instances"
        / "nibras"
        / "instance.yaml"
    )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_preferred_api_leave_balance_ar_en():
    for msg in (
        "عن الإجازات",
        "ماشي، طيب عن الإجازات",
        "رصيد الإجازات",
        "What is my leave balance?",
        "How much leave do I have left?",
    ):
        assert preferred_self_api(msg) == LEAVE_BALANCE_API, msg
        assert ess_self_read_topic(msg) == "leave", msg


def test_preferred_api_leave_history():
    for msg in (
        "Show my leave requests",
        "What is my leave history?",
        "طلبات الإجازة",
    ):
        assert leave_history_asked(msg), msg
        assert preferred_self_api(msg) == LEAVE_HISTORY_API, msg


def test_preferred_api_loan_and_payslip():
    assert preferred_self_api("What are my loans?") == LOAN_HISTORY_API
    assert preferred_self_api("قروضي") == LOAN_HISTORY_API
    assert preferred_self_api("What was my last payslip?") == PAYSLIP_API
    assert preferred_self_api("قسيمة راتبي") == PAYSLIP_API


def test_nav_skips_ess_topic_reads_keeps_how_where():
    cfg = _nibras_cfg()
    for msg in (
        "عن الإجازات",
        "What is my leave balance?",
        "What are my loans?",
        "What was my net pay last month?",
    ):
        assert resolve_navigation(msg, cfg).action == "none", msg
    # How/where still grounds the place.
    where = resolve_navigation("Where can I find my leave balance?", cfg)
    assert where.action in ("navigate", "disambiguate")
    # Explicit nav verb still navigates.
    assert resolve_navigation("Show my payslips", cfg).action in (
        "navigate",
        "disambiguate",
    )
    assert resolve_navigation("Go to leave", cfg).action in (
        "navigate",
        "disambiguate",
    )
    # Bare module nouns still navigate (destination, not data ask).
    assert resolve_navigation("leave", cfg).action in ("navigate", "disambiguate")
    assert resolve_navigation("payroll", cfg).action in ("navigate", "disambiguate")


def test_intent_leave_balance_not_history():
    labels = [
        {"name": "list_my_leave"},
        {"name": "get_my_leave_balance"},
    ]
    resolution = IntentResolution(
        action="answer",
        candidates=[IntentCandidate(name="list_my_leave", confidence=0.8)],
        confidence=0.8,
    )
    out = _apply_named_leave_override(
        resolution,
        user_message="عن الإجازات",
        labels=labels,
    )
    assert out.candidates[0].name == LEAVE_BALANCE_API


def test_intent_leave_history_prefers_list():
    labels = [
        {"name": "list_my_leave"},
        {"name": "get_my_leave_balance"},
    ]
    resolution = IntentResolution(
        action="answer",
        candidates=[IntentCandidate(name="get_my_leave_balance", confidence=0.8)],
        confidence=0.8,
    )
    out = _apply_named_leave_override(
        resolution,
        user_message="Show my leave requests",
        labels=labels,
    )
    assert out.candidates[0].name == LEAVE_HISTORY_API


def test_intent_loan_self_read():
    labels = [
        {"name": "list_my_loans"},
        {"name": "get_my_profile"},
    ]
    resolution = IntentResolution(
        action="answer",
        candidates=[IntentCandidate(name="get_my_profile", confidence=0.7)],
        confidence=0.7,
    )
    out = _apply_ess_self_read_override(
        resolution,
        user_message="What are my loans?",
        labels=labels,
    )
    assert out.candidates[0].name == LOAN_HISTORY_API


def test_empty_leave_history_honesty_not_zero_balance():
    tools = [
        {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "list_my_leave"},
            "result": {"count": 0, "results": []},
        }
    ]
    hit = empty_history_misread(tools, user_message="عن الإجازات")
    assert hit is not None
    assert hit["gate"] == "ess_empty_leave_history"
    assert "صفر" in hit["text"] or "zero" in hit["text"].lower() or "رصيد" in hit["text"]
    assert "0" not in hit["text"] or "صفر" in hit["text"]
    # Must not claim remaining days are zero as a number dump.
    assert "remaining 0" not in hit["text"].lower()
    assert "المتبقي 0" not in hit["text"]


def test_empty_loan_history_honesty():
    tools = [
        {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "list_my_loans"},
            "result": {"count": 0, "results": []},
        }
    ]
    hit = empty_history_misread(tools, user_message="What are my loans?")
    assert hit is not None
    assert hit["gate"] == "ess_empty_loan_history"
    assert "invent" in hit["text"].lower() or "أقساط" in hit["text"]


def test_empty_payslip_honesty_via_ess_read():
    tools = [
        {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": "list_my_payslips"},
            "result": {"count": 0, "results": []},
        }
    ]
    hit = empty_history_misread(
        tools, user_message="What was my net pay last month?"
    )
    assert hit is not None
    assert hit["gate"] == "ess_empty_payslip"


def test_leave_topic_not_named_employee():
    assert leave_topic_asked("عن الإجازات")
    assert preferred_self_api("annual leave remaining for emp_1001") is None
    assert loan_topic_asked("قروضي")
