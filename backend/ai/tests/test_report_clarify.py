"""Broad salary/payroll report asks must clarify before dumping data."""
from __future__ import annotations

from ai.engine.cognition.turn.report_clarify import (
    is_broad_report_ask,
    try_report_clarify,
)
from ai.engine.cognition.turn.zero_llm import try_zero_llm_answer


def test_broad_full_report_is_detected():
    assert is_broad_report_ask("i need full report about salaries in the company")
    assert is_broad_report_ask("Give me a comprehensive payroll report")
    assert is_broad_report_ask("تقرير كامل عن الرواتب")


def test_scoped_report_skips_clarify():
    assert not is_broad_report_ask(
        "salary distribution by band for the board"
    )
    assert not is_broad_report_ask("payroll run health — committed vs failed")
    assert not is_broad_report_ask("GOSI deductions overview")
    # "charts" (plural) must count as scoped — the bug that re-asked clarify.
    assert not is_broad_report_ask("ok. give me full report with charts and visuals")


def test_try_report_clarify_returns_options():
    hit = try_report_clarify("i need full report about salaries in the company")
    assert hit is not None
    assert hit["gate"] == "report_clarify"
    assert hit["decision"] == "clarify"
    assert "this report" in hit["text"].lower()
    assert "Pay distribution" in hit["text"]
    assert "Board-ready" in hit["text"]
    # Pronoun "it" must not appear — entity linker chips OrgUnit "IT" onto it.
    assert " should it " not in hit["text"].lower()


def test_zero_llm_surfaces_report_clarify():
    hit = try_zero_llm_answer("i need full report about salaries in the company")
    assert hit is not None
    assert hit["gate"] == "report_clarify"
    assert "audience" in hit["text"].lower() or "focus" in hit["text"].lower()


def test_aspect_reply_after_clarify_passes_through():
    history = [
        {"role": "user", "content": "full report about salaries"},
        {
            "role": "assistant",
            "content": (
                "Happy to help with a salary report — what should "
                "this report focus on?"
            ),
        },
    ]
    assert try_report_clarify("Pay distribution by band", history=history) is None
    assert try_report_clarify("all the 4 aspects", history=history) is None
    hit = try_zero_llm_answer("Pay distribution by band", history=history)
    assert hit is None or hit.get("gate") != "report_clarify"


def test_charts_followup_never_reclarifies_after_report_answer():
    """Transcript bug: after a payroll answer, 'full report with charts' re-asked."""
    history = [
        {"role": "user", "content": "all the 4 aspects"},
        {
            "role": "assistant",
            "content": (
                "Your organization has 555 active employees. "
                "### Payroll Run Status Summary\n| Status | Count |"
            ),
        },
    ]
    assert (
        try_report_clarify(
            "ok. give me full report with charts and visuals",
            history=history,
        )
        is None
    )


def test_prior_clarify_in_thread_blocks_repeat():
    history = [
        {"role": "user", "content": "full report about salaries"},
        {
            "role": "assistant",
            "content": (
                "Happy to help with a salary report — what should "
                "[[org-unit:15:IT]] focus on?"
            ),
        },
        {"role": "user", "content": "all the 4 aspects"},
        {
            "role": "assistant",
            "content": "Payroll Run Status Summary — Committed 17.",
        },
    ]
    assert try_report_clarify(
        "i need full report about salaries in the company",
        history=history,
    ) is None


def test_last_results_payroll_skips_clarify():
    last_results = [
        {
            "tool": "call_host_api",
            "api": "list_payroll_runs",
            "digest": "call_host_api list_payroll_runs: count=20",
        },
    ]
    assert try_report_clarify(
        "i need full report about salaries in the company",
        last_results=last_results,
    ) is None


def test_numbered_pick_expands_after_topic_menu():
    from ai.engine.cognition.turn.report_clarify import expand_numbered_report_pick

    history = [
        {
            "role": "assistant",
            "content": (
                "I'd like to focus this report for you. **What's the main topic?**\n"
                "1. **Headcount & Organization**\n"
                "2. **Payroll & Compensation**"
            ),
        },
    ]
    expanded = expand_numbered_report_pick("1", history=history)
    assert expanded is not None
    assert "Headcount" in expanded
    assert "charts" in expanded.lower()
    assert try_report_clarify("1", history=history) is None


def test_numbered_pick_expands_after_salary_clarify():
    from ai.engine.cognition.turn.report_clarify import expand_numbered_report_pick

    history = [
        {
            "role": "assistant",
            "content": (
                "Happy to help with a salary report — what should "
                "this report focus on?"
            ),
        },
    ]
    expanded = expand_numbered_report_pick("1", history=history)
    assert expanded is not None
    assert "distribution" in expanded.lower() or "band" in expanded.lower()
    assert expand_numbered_report_pick("1", history=[]) is None
