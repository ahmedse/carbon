"""Needles the domain meter misses follow the bound pack."""
from __future__ import annotations

from pathlib import Path

from ai.engine.cognition.phrase_tables import T
from ai.engine.cognition.turn.ess_read_i18n import LEAVE_TOPIC_AR, any_needle
from ai.engine.host_ids import ID_GET_CALCULATION_SUMMARY
from ai.engine.pack_vocab import bind_pack

_PHRASE = (
    Path(__file__).resolve().parents[1] / "engine" / "cognition" / "phrase_tables.yaml"
)
_GONE = (
    "إجازاتي",
    "راتبي",
    "loan_installment",
    "employee_id",
    "employee_no",
    "Pay distribution by band",
    "pifss",
    "time off",
    "absence rate",
    "net pay",
)


def test_core_phrase_file_dropped_host_needles():
    text = _PHRASE.read_text(encoding="utf-8")
    for fragment in _GONE:
        assert fragment not in text, fragment
    assert "سأ" in text or "سوف أ" in text


def test_nibras_needles_still_match():
    with bind_pack("nibras"):
        assert any_needle("إجازاتي", LEAVE_TOPIC_AR)
        assert "راتبي" in T("turn/navigation_i18n.py::SELF_READ_POSSESSIVE_AR")
        assert "employee_id" in T("turn/execute.py::_CATALOG_PATH_KEYS")
        assert "loan_installment" in T("turn/zero_llm.py::_PAYSLIP_LINE_CODES")
        assert "time off" in T("scope_route.py::_BARE_LEAVE_EN")
        assert "page" in T("turn/execute.py::_CATALOG_QUERY_KEYS")


def test_medicine_needles_are_absent():
    with bind_pack("aast-med"):
        assert tuple(LEAVE_TOPIC_AR) == ()
        assert any_needle("إجازاتي", LEAVE_TOPIC_AR) is False
        assert "راتبي" not in T("turn/navigation_i18n.py::SELF_READ_POSSESSIVE_AR")
        assert "employee_id" not in T("turn/execute.py::_CATALOG_PATH_KEYS")
        assert "loan_installment" not in T("turn/zero_llm.py::_PAYSLIP_LINE_CODES")
        assert "time off" not in T("scope_route.py::_BARE_LEAVE_EN")
        assert any_needle("what courses are on this page", LEAVE_TOPIC_AR) is False


def test_carbon_keeps_generic_query_keys():
    with bind_pack("carbon"):
        keys = T("turn/execute.py::_CATALOG_QUERY_KEYS")
        assert "page" in keys
        assert "employee_no" not in keys
        assert str(ID_GET_CALCULATION_SUMMARY) == "get_calculation_summary"


def test_empty_needle_matches_nothing():
    assert any_needle("إجازاتي", ()) is False
    assert any_needle("", ("",)) is False
