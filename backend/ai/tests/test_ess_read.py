"""ESS self-read contract — balance vs history + empty honesty."""
from __future__ import annotations

import yaml
import pytest
from pathlib import Path

from ai.engine.cognition.turn.ess_read import (
    LEAVE_BALANCE_API,
    LEAVE_HISTORY_API,
    LOAN_HISTORY_API,
    PAYSLIP_API,
    domain_history_asked,
    domain_topic_asked,
    empty_history_misread,
    ess_self_read_topic,
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
        assert domain_history_asked("leave", msg), msg
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
    # First-person self-read stays on ESS even with a show-verb.
    assert resolve_navigation("Show my payslips", cfg).action == "none"
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


def test_bound_ess_self_api_single_vs_multi_domain(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    from ai.engine.cognition.turn.ess_read import (
        LEAVE_BALANCE_API,
        bound_ess_self_api,
        matching_self_domains,
    )

    assert bound_ess_self_api("اريد اعرف كل ما يتعلق باجازاتي") == LEAVE_BALANCE_API
    assert bound_ess_self_api("ما هو رصيد إجازاتي؟") == LEAVE_BALANCE_API
    assert bound_ess_self_api("عن الاجازلت") == LEAVE_BALANCE_API
    # Multi-domain utterance → no single bound GET (catalog rule, not leave+salary if).
    assert len(matching_self_domains("تقرير مفصل عن مرتبي و اجازاتي")) > 1
    assert bound_ess_self_api("تقرير مفصل عن مرتبي و اجازاتي") is None


def test_bound_ess_followup_uses_active_domain_not_leave_hardcode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    from ai.engine.cognition.turn.ess_read import (
        LEAVE_BALANCE_API,
        LOAN_HISTORY_API,
        bound_ess_self_api,
    )

    leave_hist = [
        {"role": "user", "content": "اريد اعرف كل ما يتعلق باجازاتي"},
        {"role": "assistant", "content": "اطلب رصيد الإجازات"},
    ]
    assert bound_ess_self_api("ما هو الرصيد", history=leave_hist) == LEAVE_BALANCE_API
    assert bound_ess_self_api("كل الانواع", history=leave_hist) == LEAVE_BALANCE_API

    loan_hist = [
        {"role": "user", "content": "قروضي"},
        {"role": "assistant", "content": "لا توجد قروض"},
    ]
    assert bound_ess_self_api("ما هو الرصيد", history=loan_hist) == LOAN_HISTORY_API


def test_answer_bound_ess_leave_balance_restates_host():
    from ai.engine.cognition.turn.ess_read import (
        LEAVE_BALANCE_API,
        answer_bound_ess_tools,
    )

    tools = [
        {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": LEAVE_BALANCE_API},
            "result": [
                {"leave_type": "annual", "entitled": 30, "remaining": 30, "used": 0, "pending": 0},
            ],
        }
    ]
    text = answer_bound_ess_tools(
        tools, api_name=LEAVE_BALANCE_API, user_message="رصيد الإجازات"
    )
    assert "30" in text
    assert "annual" in text.lower() or "متبقي" in text
    assert "HR" not in text and "موارد" not in text


def test_answer_bound_ess_empty_balance_no_speculation():
    from ai.engine.cognition.turn.ess_read import (
        LEAVE_BALANCE_API,
        answer_bound_ess_tools,
    )

    tools = [
        {
            "tool_name": "call_host_api",
            "tool_args": {"api_name": LEAVE_BALANCE_API},
            "result": [],
        }
    ]
    text = answer_bound_ess_tools(
        tools, api_name=LEAVE_BALANCE_API, user_message="ما هو الرصيد"
    )
    assert "0 يوم" not in text
    assert "new" not in text.lower()
    assert "join" not in text.lower()


def test_arabic_typo_اجازلت_is_leave_balance():
    """Transcript typo «الاجازلت» must still force balance, not invent 0."""
    from ai.engine.agent.tools import leave_balance_intent_asked
    from ai.engine.cognition.turn.ess_read import (
        domain_topic_asked,
        preferred_self_api,
        LEAVE_BALANCE_API,
    )
    from ai.engine.cognition.turn.force_tool import ensure_forced_call
    from ai.engine.cognition.turn.intent import IntentCandidate, IntentResolution
    from ai.engine.cognition.turn.witnesses import DraftResult

    msg = "ماشي, طيب عن الاجازلت"
    assert domain_topic_asked("leave", msg), msg
    assert leave_balance_intent_asked(msg), msg
    assert preferred_self_api(msg) == LEAVE_BALANCE_API
    resolution = IntentResolution(
        action="answer",
        needs_host_data=True,
        confidence=0.95,
        candidates=[IntentCandidate(name=LEAVE_BALANCE_API, confidence=0.95)],
    )
    out = ensure_forced_call(
        DraftResult(tool_calls=[], text="remaining 0"),
        resolution,
        "t1",
        set(),
    )
    assert out.tool_calls
    assert LEAVE_BALANCE_API in str(out.tool_calls)


def test_comprehensive_pick_binds_only_when_single_domain_in_thread(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    from ai.engine.cognition.turn.ess_read import (
        LEAVE_BALANCE_API,
        bound_ess_self_api,
    )

    # Multi-domain prior brief → no single bound GET.
    multi = [
        {"role": "user", "content": "تقرير مفصل عن مرتبي و اجازاتي"},
        {"role": "assistant", "content": "ما هو التركيز؟"},
    ]
    assert bound_ess_self_api("تقرير شامل", history=multi) is None

    # Single leave thread → comprehensive pick binds leave balance.
    leave_only = [
        {"role": "user", "content": "عن الإجازات"},
        {"role": "assistant", "content": "رصيد الإجازة…"},
    ]
    assert bound_ess_self_api("تقرير شامل", history=leave_only) == LEAVE_BALANCE_API


def test_calendar_questions_are_not_a_leave_balance_read(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    from ai.engine.cognition.turn.ess_read import LEAVE_BALANCE_API, bound_ess_self_api

    assert bound_ess_self_api("How many days from now until my leave?") is None
    assert bound_ess_self_api("When does my leave start?") is None
    assert bound_ess_self_api("How many leave days do I have left?") == LEAVE_BALANCE_API


def test_vacation_synonym_is_not_a_topic_regex(monkeypatch: pytest.MonkeyPatch):
    """P11: under v21 'my vacations' is a catalog example, not a routing synonym.

    The legacy kill switch keeps its old binding, so the vacation golden holds.
    """
    from ai.engine.cognition.turn.ess_read import bound_ess_self_api

    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    assert bound_ess_self_api("tell me more about my vacations") is None
    monkeypatch.setenv("PULSE_UNDERSTAND", "legacy")
    assert bound_ess_self_api("tell me more about my vacations") == "get_my_leave_balance"
    assert bound_ess_self_api("How many leave days do I have left?") == "get_my_leave_balance"


def test_v21_fresh_read_is_not_chosen_by_topic_regex(monkeypatch: pytest.MonkeyPatch):
    """P2: the catalog routes a fresh read. P9: a follow-up binds state, not history."""
    from ai.engine.cognition.turn.ess_read import LEAVE_BALANCE_API, bound_ess_self_api

    monkeypatch.setenv("PULSE_UNDERSTAND", "v21")
    assert bound_ess_self_api("How many leave days do I have left?") is None
    leave_only = [
        {"role": "user", "content": "عن الإجازات"},
        {"role": "assistant", "content": "رصيد الإجازة…"},
    ]
    assert bound_ess_self_api("تقرير شامل", history=leave_only) is None
    assert bound_ess_self_api(
        "تقرير شامل", history=leave_only, prior_api=LEAVE_BALANCE_API,
    ) == LEAVE_BALANCE_API
    # P10: the same continuation binds in either language, with no needle list.
    assert bound_ess_self_api(
        "with the details", prior_api=LEAVE_BALANCE_API,
    ) == LEAVE_BALANCE_API
    assert bound_ess_self_api(
        "مع التفاصيل", prior_api=LEAVE_BALANCE_API,
    ) == LEAVE_BALANCE_API
