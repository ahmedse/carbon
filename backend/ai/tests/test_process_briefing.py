"""Process briefing ≠ navigate — Chat concept lane regression tests."""
from __future__ import annotations

from ai.engine.cognition.turn.process_brief import (
    extract_process_id,
    format_process_briefing,
    is_process_briefing,
    try_process_briefing,
)


def test_process_id_ask_is_briefing_not_nav():
    en = (
        "Explain the Nibras governed process `leave.request.lifecycle` end-to-end. "
        "List every step in order and say which need human approval."
    )
    assert is_process_briefing(en)
    assert extract_process_id(en) == "leave.request.lifecycle"
    ar = "اشرح عملية `loan.request.lifecycle` في نبراس خطوة بخطوة بالعربية"
    assert is_process_briefing(ar)
    assert extract_process_id(ar) == "loan.request.lifecycle"


def test_open_app_is_not_process_briefing():
    assert not is_process_briefing("take me to payroll")
    assert not is_process_briefing("open People & Payroll")
    assert not is_process_briefing("روح لتطبيق الموظفين")


def test_process_briefing_would_nav_without_guard():
    """Regression lock: leave lifecycle text matches Leave nav aliases.

    Without the process-briefing skip, NAV-GATE returns disambiguate —
    the P0 Chat PARTIAL. Guard must short-circuit briefing first.
    """
    from pathlib import Path

    import yaml
    from ai.engine.cognition.turn.navigation import resolve_navigation

    cfg = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "engine/instances/nibras/instance.yaml")
        .read_text(encoding="utf-8")
    )
    msg = (
        "Explain the Nibras governed process `leave.request.lifecycle` "
        "end-to-end. List every step in order and say which need human approval."
    )
    assert is_process_briefing(msg)
    nav = resolve_navigation(msg, cfg)
    assert nav.action in ("navigate", "disambiguate")


def test_format_leave_briefing_lists_steps_and_human_gate():
    text = format_process_briefing("leave.request.lifecycle", lang="en")
    assert text is not None
    assert "submit" in text
    assert "review" in text
    assert "record" in text
    assert "verify" in text
    assert "human_only" in text.lower() or "human approval" in text.lower()
    assert "People & Payroll" in text  # clarifying it is NOT nav
    ar = format_process_briefing("leave.request.lifecycle", lang="ar")
    assert ar is not None
    assert "submit" in ar
    assert "موافقة" in ar


def test_try_process_briefing_round_trip():
    got = try_process_briefing(
        "Explain payroll.run.lifecycle steps and human approval gates."
    )
    assert got is not None
    pid, reply = got
    assert pid == "payroll.run.lifecycle"
    assert "compute" in reply
    assert "commit" in reply
