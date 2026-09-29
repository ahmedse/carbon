"""Tool names and slot codes follow the pack that catalogs them."""
from __future__ import annotations

import re
from pathlib import Path

from ai.engine.cognition.phrase_tables import T
from ai.engine.cognition.turn.ess_read import balance_apis
from ai.engine.host_ids import (
    ID_CAP_COMPENSATION,
    ID_ENUM_ANNUAL,
    ID_GET_CALCULATION_SUMMARY,
    ID_GET_MY_LEAVE_BALANCE,
    ID_LIST_MY_CAPABILITIES,
    ID_LIST_MY_PAYSLIPS,
    ID_SUBMIT_MY_LEAVE,
)
from ai.engine.pack_vocab import bind_pack, present_ids, same_id

_ENGINE = Path(__file__).resolve().parents[1] / "engine"
_QUOTED = (
    "get_my_leave_balance",
    "list_my_leave",
    "list_my_payslips",
    "submit_my_leave",
    "submit_my_loan",
    "people:view_compensation",
    "no_leave_requests",
    "leave_history",
)
_PHRASE = _ENGINE / "cognition" / "phrase_tables.yaml"


def test_quoted_host_ids_are_not_engine_literals():
    for path in sorted(_ENGINE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for fragment in _QUOTED:
            assert not re.search(
                r'["\']' + re.escape(fragment) + r'["\']', text
            ), f"{path.name} still quotes {fragment}"
    phrase = _PHRASE.read_text(encoding="utf-8")
    assert "turn/catalog_render.py::BALANCE_APIS:" not in phrase
    assert "turn/catalog_render.py::PAYSLIP_APIS:" not in phrase


def test_same_id_rejects_empty():
    assert same_id("", "") is False
    assert same_id("submit_my_leave", "") is False
    assert same_id("", "submit_my_leave") is False
    assert same_id("submit_my_leave", "submit_my_leave") is True


def test_nibras_ids_resolve():
    with bind_pack("nibras"):
        assert str(ID_GET_MY_LEAVE_BALANCE) == "get_my_leave_balance"
        assert str(ID_SUBMIT_MY_LEAVE) == "submit_my_leave"
        assert str(ID_LIST_MY_PAYSLIPS) == "list_my_payslips"
        assert str(ID_ENUM_ANNUAL) == "annual"
        assert str(ID_CAP_COMPENSATION) == "people:view_compensation"
        assert "get_my_leave_balance" in balance_apis()
        assert "get_my_leave_balance" in T("turn/catalog_render.py::BALANCE_APIS")
        assert "call_host_api" in T("dialogue/deixis.py::_KNOWN_TOOL_IDENTIFIERS")


def test_medicine_ids_are_absent():
    with bind_pack("aast-med"):
        assert str(ID_GET_MY_LEAVE_BALANCE) == ""
        assert str(ID_ENUM_ANNUAL) == ""
        assert same_id("get_my_leave_balance", ID_GET_MY_LEAVE_BALANCE) is False
        assert balance_apis() == frozenset()
        assert "get_my_leave_balance" not in T("turn/catalog_render.py::BALANCE_APIS")
        assert "get_my_leave_balance" not in T("dialogue/deixis.py::_KNOWN_TOOL_IDENTIFIERS")
        assert "call_host_api" in T("dialogue/deixis.py::_KNOWN_TOOL_IDENTIFIERS")


def test_carbon_keeps_its_own_names():
    with bind_pack("carbon"):
        assert str(ID_LIST_MY_CAPABILITIES) == "list_my_capabilities"
        assert str(ID_GET_CALCULATION_SUMMARY) == "get_calculation_summary"
        assert str(ID_GET_MY_LEAVE_BALANCE) == ""
        assert present_ids(ID_GET_MY_LEAVE_BALANCE, ID_LIST_MY_CAPABILITIES) == frozenset(
            {"list_my_capabilities"}
        )
