"""Utterance matchers follow the pack bound for the turn."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ai.engine.agent.tools import compensation_intent_asked, payslip_specific_ask
from ai.engine.cognition.plan.planner import _plan_domain
from ai.engine.cognition.plan.process_dial import _attendance_brief
from ai.engine.cognition.turn.ess_read import (
    _LEAVE_HISTORY_RE,
    _LEAVE_TOPIC_RE,
    _NAMED_EMP_RE,
    _PAYSLIP_TOPIC_RE,
    _attendance_topic,
)
from ai.engine.pack_vocab import LV, V, bind_pack, live_alt

_ENGINE = Path(__file__).resolve().parents[1] / "engine"
_VOCAB = (
    Path(__file__).resolve().parents[3] / "domain_packs" / "nibras" / "vocab.yaml"
)

_REGEX_FRAGMENTS = (
    r"\bleav",
    r"\bvacation",
    r"\bpto",
    r"time[\s-]?off",
    r"\bpayslips?",
    r"net\s+pay",
    r"net\s*pay",
    r"take[\s-]?home",
    r"take[\s_-]*home",
    r"\bemployee\s*",
    "deductions? were",
    r"\bloan\b",
    r"\bpermission\b",
)

_QUOTED_NEEDLES = (
    '"compensation"',
    '"basic pay"',
    '"clock in"',
    '"short hours"',
    '"pay distribution"',
    '"wps"',
    '"sif"',
    '"onboard"',
)


def test_moved_fragments_are_not_engine_literals():
    for path in sorted(_ENGINE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fragment in _REGEX_FRAGMENTS:
            assert fragment not in text, f"{path.name} still has {fragment}"


def test_quoted_needles_left_the_matcher_files():
    for path in sorted(_ENGINE.rglob("*.py")):
        if "workflow" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in _QUOTED_NEEDLES:
            assert needle not in text, f"{path.name} still has {needle}"


def test_nibras_matchers_still_hit():
    with bind_pack("nibras"):
        assert _LEAVE_TOPIC_RE.search("how much leave do I have")
        assert _LEAVE_TOPIC_RE.search("vacation days")
        assert _LEAVE_TOPIC_RE.search("pto")
        assert _LEAVE_TOPIC_RE.search("time off tomorrow")
        assert _LEAVE_HISTORY_RE.search("show my leave requests")
        assert _PAYSLIP_TOPIC_RE.search("my payslip")
        assert _PAYSLIP_TOPIC_RE.search("net pay")
        assert _PAYSLIP_TOPIC_RE.search("take-home")
        assert _NAMED_EMP_RE.search("emp_1067")
        assert compensation_intent_asked("what is my compensation")
        assert compensation_intent_asked("my pay")
        assert compensation_intent_asked("wage")
        assert compensation_intent_asked("basic pay")
        assert payslip_specific_ask("what deductions were applied")
        assert _attendance_topic("clock in")
        assert _attendance_topic("8 hour this month")
        assert _attendance_brief("I need permission")
        assert _attendance_brief("short hours yesterday")
        assert _plan_domain("I need a loan") == V("t_loan_2")
        assert _plan_domain("onboard the new hire") == V("t_rx_w_onboarding")
        assert _plan_domain("send the wps file") == V("t_gosi")
        assert _plan_domain("where is the sif") == V("t_gosi")
        from ai.engine.cognition.turn.runner_util import _ess_topic

        assert _ess_topic("I was marked absence")
        assert _ess_topic("time-off next week")


def test_other_pack_does_not_inherit_the_matchers():
    with bind_pack("aast-med"):
        assert _LEAVE_TOPIC_RE.search("how much leave do I have") is None
        assert _LEAVE_TOPIC_RE.search("what courses are here") is None
        assert _LEAVE_TOPIC_RE.search("vacation") is None
        assert _LEAVE_TOPIC_RE.search("time off") is None
        assert _PAYSLIP_TOPIC_RE.search("net pay") is None
        assert _PAYSLIP_TOPIC_RE.search("take-home") is None
        assert _NAMED_EMP_RE.search("emp_1067") is None
        assert not compensation_intent_asked("what is my compensation")
        assert not compensation_intent_asked("basic pay")
        assert not payslip_specific_ask("what deductions were applied")
        assert not _attendance_topic("clock in")
        assert not _attendance_topic("8 hour this month")
        assert not _attendance_brief("I need permission")
        assert not _attendance_brief("short hours yesterday")
        assert _plan_domain("I need a loan") == ""
        assert _plan_domain("onboard the new hire") == ""
        assert _plan_domain("send the wps file") == ""


def test_empty_alternative_matches_nothing():
    with bind_pack("aast-med"):
        pattern = live_alt(LV("t_rx_leave_topic_en"), LV("t_rx_payslip_topic_en"))
        assert pattern.search("leave") is None
        assert pattern.search("") is None
        assert pattern.search("a course page") is None
        assert re.compile(pattern.pattern).pattern == r"(?!)"


def test_escape_does_not_load_matcher_text():
    with bind_pack("../nibras"):
        assert V("t_rx_leave_word") == ""
        assert _LEAVE_TOPIC_RE.search("leave") is None


def test_pack_pattern_text_compiles_to_the_vocab_row():
    rows = yaml.safe_load(_VOCAB.read_text(encoding="utf-8"))
    loan = rows["t_rx_loan_submit"]
    assert "loan" in loan
    assert re.compile(loan, re.IGNORECASE | re.DOTALL).search("I'd like a loan")
    payslip = rows["t_rx_payslip_specific_en"]
    assert re.compile(payslip, re.IGNORECASE).search("last month's net pay")
