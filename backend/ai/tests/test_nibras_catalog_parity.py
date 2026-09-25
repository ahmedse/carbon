"""Pack tools: names must appear in Nibras instance.yaml api_catalog (SSOT)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
PACK = REPO / "domain_packs" / "nibras" / "api_catalog.yaml"
INSTANCE = REPO / "backend" / "ai" / "engine" / "instances" / "nibras" / "instance.yaml"

# Nav-only / self-service entries in instance that packs need not declare as tools.
INSTANCE_ONLY_OK = {
    "get_my_profile",
    "list_my_payslips",
    "list_attendance",
    "list_positions",
    "people_home",
    "employees",
    "employee_detail",
    "payroll",
    "leave",
    "loans",
    "attendance",
}


def _pack_tool_names() -> set[str]:
    data = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    return {t["name"] for t in (data.get("tools") or []) if t.get("name")}


def _instance_api_names() -> set[str]:
    data = yaml.safe_load(INSTANCE.read_text(encoding="utf-8"))
    catalog = data.get("api_catalog") or []
    return {e["name"] for e in catalog if isinstance(e, dict) and e.get("name")}


def test_nibras_pack_tools_subset_of_instance_catalog():
    pack = _pack_tool_names()
    inst = _instance_api_names()
    missing = sorted(pack - inst)
    assert not missing, (
        "domain_packs/nibras/api_catalog.yaml tools missing from "
        f"instance.yaml api_catalog: {missing}"
    )


def test_nibras_gosi_tools_present_in_both():
    required = {
        "generate_gosi_wps_sif",
        "validate_gosi_wps_sif",
        "submit_gosi_wps_sif",
        "get_gosi_wps_sif",
    }
    pack = _pack_tool_names()
    inst = _instance_api_names()
    assert required <= pack
    assert required <= inst


def test_nibras_attendance_tools_in_pack():
    pack = _pack_tool_names()
    for name in (
        "list_my_attendance_permissions",
        "submit_my_attendance_permission",
        "list_attendance_permissions",
        "create_attendance_permission",
        "approve_attendance_permission",
    ):
        assert name in pack, name
    inst = _instance_api_names()
    for name in (
        "list_my_attendance_permissions",
        "submit_my_attendance_permission",
        "list_attendance_permissions",
        "create_attendance_permission",
        "approve_attendance_permission",
    ):
        assert name in inst, name


def test_nibras_committed_pay_in_both():
    pack = _pack_tool_names()
    inst = _instance_api_names()
    assert "analyze_committed_pay" in pack
    assert "analyze_committed_pay" in inst
    assert "analyze_kuwaitization" in pack
    assert "analyze_kuwaitization" in inst


def test_nibras_closed_aggregates_in_both():
    required = {
        "analyze_leave_utilization",
        "analyze_loan_book",
        "analyze_gosi_committed",
        "analyze_cert_expiry",
        "analyze_leave_presence",
    }
    pack = _pack_tool_names()
    inst = _instance_api_names()
    assert required <= pack
    assert required <= inst


def test_nibras_item1_host_reads_in_both():
    required = {
        "analyze_employees",
        "list_my_direct_reports",
        "list_team_leave",
        "list_correspondence_inbox",
        "list_correspondence_history",
    }
    pack = _pack_tool_names()
    inst = _instance_api_names()
    assert required <= pack
    assert required <= inst


def test_nibras_loan_onboarding_tools_in_pack():
    pack = _pack_tool_names()
    for name in (
        "submit_my_loan",
        "list_my_loans",
        "create_employee",
        "update_employee",
        "list_employees",
        "submit_my_leave",
        "get_my_leave_balance",
    ):
        assert name in pack, name
