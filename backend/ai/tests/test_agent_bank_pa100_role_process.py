"""Agent bank PA-100… — role × process matrix (Pulse dial oracles).

Maps QA-CHAT-AGENTIC-SCENARIO-BANK §B11 + canvas PN-* process oracles onto
existing ``ProcessDefinition`` dials (autonomy / SoD / refuse_if / consent).

This is the **Pulse coworker gate** for role×process: Agent must honor the
governed graph. It does **not** rewrite Nibras People multi-user UAT
(``docs/nibras/QA-DEEP-MULTI-USER-JOURNEY.md``) — that stays the host oracle.

Cells covered (happy / deny / SoD):

======= ======================= ============================
PA-ID   Process                 Role lens
======= ======================= ============================
PA-110  leave                   employee submit (happy)
PA-111  leave                   manager review (happy)
PA-112  leave                   SoD self-approve deny
PA-113  leave                   record gated after review
PA-120  loan                    employee apply (happy)
PA-121  loan                    review human gate (happy)
PA-122  loan                    SoD deny
PA-123  loan                    activate gated
PA-130  payroll                 employee/mgr deny auto-commit
PA-131  payroll                 HR/preparer compute+validate
PA-132  payroll                 commit after validate/review
PA-133  payroll                 SoD deny
PA-134  payroll                 commit consent (admin)
PA-140  onboarding              activate human_only (admin)
PA-141  onboarding              employee deny auto-activate
PA-142  onboarding              SoD deny
PA-150  gosi/wps                employee deny auto-submit
PA-151  gosi/wps                prepare generate/validate
PA-152  gosi/wps                SoD + validate-before-submit
======= ======================= ============================

Run::

    cd backend && ../.venv/bin/python -m pytest \\
        ai/tests/test_agent_bank_pa100_role_process.py -q
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings

from ai.engine.ports.domain import load_domain_pack
from ai.models.capability import load_capabilities
from ai.models.process import validate_definition

PACK_DIR = Path(settings.BASE_DIR).parent / "domain_packs" / "nibras"


def _pack():
    return load_domain_pack(PACK_DIR)


def _doc(process_id: str) -> dict:
    return dict(next(p for p in _pack().processes() if p.get("id") == process_id))


def _step(doc: dict, step_id: str) -> dict:
    return next(s for s in doc["steps"] if s["id"] == step_id)


def _refuse(doc: dict) -> list[str]:
    return list(doc.get("policies", {}).get("refuse_if") or [])


def _known() -> set[str]:
    return {c.capability_id for c in load_capabilities(_pack())}


# ── Shared: every process in the matrix still validates ───────────────────


@pytest.mark.parametrize(
    "process_id",
    [
        "leave.request.lifecycle",
        "loan.request.lifecycle",
        "payroll.run.lifecycle",
        "employee.onboarding.lifecycle",
        "gosi_wps.sif.lifecycle",
        "attendance.permission.lifecycle",
    ],
)
def test_pa100_matrix_process_still_validates(process_id):
    """Matrix baseline: ProcessDefinition remains valid (no dial drift)."""
    assert validate_definition(_doc(process_id), known_capabilities=_known()) == []


# ── Leave — PA-110…113 / PN-LV ────────────────────────────────────────────


def test_pa110_leave_employee_submit_happy():
    """Employee draft+submit: submit is staged (act_confirm), not silent auto."""
    submit = _step(_doc("leave.request.lifecycle"), "submit")
    assert submit["autonomy"] == "act_confirm"
    assert submit["consent"] is True
    assert submit["capability"] == "leave.request.submit"


def test_pa111_leave_manager_review_happy():
    """Manager approve: review is human_only + requester/approver SoD."""
    review = _step(_doc("leave.request.lifecycle"), "review")
    assert review["kind"] == "human_task"
    assert review["autonomy"] == "human_only"
    assert review["separation_of_duties"] == ["requester", "approver"]


def test_pa112_leave_sod_self_approve_deny():
    """SoD path: refuse when requester equals approver."""
    refuse = _refuse(_doc("leave.request.lifecycle"))
    assert any("requester equals approver" in r for r in refuse)


def test_pa113_leave_record_gated_after_review():
    """Record (effect) only after review; consent-required."""
    doc = _doc("leave.request.lifecycle")
    record = _step(doc, "record")
    assert "review" in (record.get("depends_on") or [])
    assert record["consent"] is True
    assert any("not reviewed before record" in r for r in _refuse(doc))


# ── Loan — PA-120…123 / PN-LN ─────────────────────────────────────────────


def test_pa120_loan_employee_apply_happy():
    submit = _step(_doc("loan.request.lifecycle"), "submit")
    assert submit["autonomy"] == "act_confirm"
    assert submit["consent"] is True


def test_pa121_loan_review_human_gate_happy():
    review = _step(_doc("loan.request.lifecycle"), "review")
    assert review["autonomy"] == "human_only"
    assert review["separation_of_duties"] == ["requester", "approver"]


def test_pa122_loan_sod_deny():
    refuse = _refuse(_doc("loan.request.lifecycle"))
    assert any("requester equals approver" in r for r in refuse)


def test_pa123_loan_activate_gated():
    doc = _doc("loan.request.lifecycle")
    activate = _step(doc, "activate")
    assert "review" in (activate.get("depends_on") or [])
    assert activate["consent"] is True
    assert any("not reviewed before activate" in r for r in _refuse(doc))


# ── Payroll — PA-130…134 / PN-PR ──────────────────────────────────────────


def test_pa130_payroll_employee_mgr_deny_auto_commit():
    """Employee/Manager cannot auto-commit: commit is human_only + consent."""
    commit = _step(_doc("payroll.run.lifecycle"), "commit")
    assert commit["autonomy"] == "human_only"
    assert commit["consent"] is True
    assert commit["autonomy"] != "auto"


def test_pa131_payroll_preparer_compute_validate_happy():
    """HR/preparer staging: compute + validate are act_confirm (not auto)."""
    doc = _doc("payroll.run.lifecycle")
    compute = _step(doc, "compute")
    validate = _step(doc, "validate")
    assert compute["autonomy"] == "act_confirm"
    assert validate["autonomy"] == "act_confirm"
    assert "compute" in (validate.get("depends_on") or [])


def test_pa132_payroll_commit_after_validate_and_review():
    """Admin commit path: validate → review → commit precedence."""
    doc = _doc("payroll.run.lifecycle")
    by_id = {s["id"]: s for s in doc["steps"]}
    assert "validate" in (by_id["review"].get("depends_on") or [])
    assert "review" in (by_id["commit"].get("depends_on") or [])
    refuse = _refuse(doc)
    assert any("not validated before commit" in r for r in refuse)
    assert any("review approval is missing before commit" in r for r in refuse)


def test_pa133_payroll_sod_deny():
    refuse = _refuse(_doc("payroll.run.lifecycle"))
    assert any("preparer equals approver" in r for r in refuse)
    review = _step(_doc("payroll.run.lifecycle"), "review")
    assert review["separation_of_duties"] == ["preparer", "approver"]


def test_pa134_payroll_commit_admin_consent():
    commit = _step(_doc("payroll.run.lifecycle"), "commit")
    assert commit["autonomy"] == "human_only"
    assert commit["consent"] is True
    assert commit["separation_of_duties"] == ["preparer", "approver"]


# ── Onboarding — PA-140…142 / PN-ON ───────────────────────────────────────


def test_pa140_onboarding_activate_admin_human_only():
    activate = _step(_doc("employee.onboarding.lifecycle"), "activate")
    assert activate["autonomy"] == "human_only"
    assert activate["consent"] is True
    assert len(activate.get("separation_of_duties") or []) >= 2


def test_pa141_onboarding_employee_deny_auto_activate():
    activate = _step(_doc("employee.onboarding.lifecycle"), "activate")
    assert activate["autonomy"] != "auto"
    assert activate["autonomy"] != "observe"


def test_pa142_onboarding_sod_deny():
    refuse = _refuse(_doc("employee.onboarding.lifecycle"))
    assert any("preparer equals approver" in r for r in refuse)
    assert any("not reviewed before activate" in r for r in refuse)


# ── GOSI/WPS — PA-150…152 / PN-GW ─────────────────────────────────────────


def test_pa150_gosi_employee_deny_auto_submit():
    submit = _step(_doc("gosi_wps.sif.lifecycle"), "submit")
    assert submit["autonomy"] == "human_only"
    assert submit["consent"] is True
    assert submit["autonomy"] != "auto"


def test_pa151_gosi_prepare_generate_validate_happy():
    doc = _doc("gosi_wps.sif.lifecycle")
    generate = _step(doc, "generate")
    validate = _step(doc, "validate")
    assert generate["autonomy"] == "act_confirm"
    assert validate["autonomy"] == "act_confirm"
    assert "generate" in (validate.get("depends_on") or [])


def test_pa152_gosi_sod_and_validate_before_submit():
    doc = _doc("gosi_wps.sif.lifecycle")
    refuse = _refuse(doc)
    assert any("preparer equals approver" in r for r in refuse)
    assert any("not validated before submit" in r for r in refuse)
    submit = _step(doc, "submit")
    assert "review" in (submit.get("depends_on") or [])
    review = _step(doc, "review")
    assert "validate" in (review.get("depends_on") or [])


# ── Attendance permission — PA-160…163 ─────────────────────────────────────


def test_pa160_attendance_submit_staged():
    submit = _step(_doc("attendance.permission.lifecycle"), "submit")
    assert submit["autonomy"] == "act_confirm"
    assert submit["consent"] is True
    assert submit["capability"] == "attendance.permission.submit"


def test_pa161_attendance_review_human_gate():
    review = _step(_doc("attendance.permission.lifecycle"), "review")
    assert review["kind"] == "human_task"
    assert review["autonomy"] == "human_only"
    assert review["separation_of_duties"] == ["requester", "approver"]


def test_pa162_attendance_sod_deny():
    refuse = _refuse(_doc("attendance.permission.lifecycle"))
    assert any("requester equals approver" in r for r in refuse)


def test_pa163_attendance_approve_gated_after_review():
    doc = _doc("attendance.permission.lifecycle")
    approve = _step(doc, "approve")
    assert "review" in (approve.get("depends_on") or [])
    assert approve["consent"] is True
    assert any("not reviewed before approve" in r for r in _refuse(doc))


# ── Cross-cutting: irreversible steps never auto (role-agnostic deny) ─────


@pytest.mark.parametrize(
    "process_id,step_id,pa_id",
    [
        ("leave.request.lifecycle", "review", "PA-111"),
        ("loan.request.lifecycle", "review", "PA-121"),
        ("payroll.run.lifecycle", "commit", "PA-130"),
        ("employee.onboarding.lifecycle", "activate", "PA-140"),
        ("gosi_wps.sif.lifecycle", "submit", "PA-150"),
        ("attendance.permission.lifecycle", "review", "PA-161"),
    ],
)
def test_pa100_irreversible_steps_never_auto(process_id, step_id, pa_id):
    """Any role via Agent: irreversible steps stay human_only (deny auto)."""
    step = _step(_doc(process_id), step_id)
    assert step["autonomy"] == "human_only", pa_id
    sod = step.get("separation_of_duties") or []
    assert len(sod) >= 2, f"{pa_id}: SoD required on {step_id}"


# ── Admin governance cell (Pulse CBAC) — leave "config only" ──────────────


@pytest.mark.django_db
def test_pa100_admin_config_operator_cannot_publish_process():
    """Admin/config cell: ai:operator cannot publish process definitions.

    Extends test_admin_cbac_matrix publish deny under a bank ID — Pulse
    governance "config only", not People payroll personas.
    """
    from uuid import uuid4

    from django.urls import reverse
    from rest_framework.test import APIClient

    from accounts.constants import AI_OPERATOR_GROUP, AI_PROCESS_OWNER_GROUP
    from ai.models.process import STATUS_REVIEW, ProcessDefinition
    from ai.tests.conftest import grant_role, make_user
    import ai.models.process as process_mod

    original = process_mod._default_known_capabilities
    process_mod._default_known_capabilities = lambda: {"noop.capability"}
    try:
        pid = f"proc.pa100.{uuid4().hex[:8]}"
        owner = make_user(f"pa100-owner-{uuid4().hex[:6]}")
        grant_role(owner, group_name=AI_PROCESS_OWNER_GROUP)
        ProcessDefinition.objects.create(
            process_id=pid,
            version="0.1.0",
            owner=owner.username,
            status=STATUS_REVIEW,
            definition={
                "id": pid,
                "version": "0.1.0",
                "owner": owner.username,
                "status": "review",
                "steps": [
                    {
                        "id": "s1",
                        "kind": "command",
                        "capability": "noop.capability",
                        "autonomy": "human_only",
                    }
                ],
                "objective": {"predicate": "pa100"},
            },
        )
        operator = make_user(f"pa100-op-{uuid4().hex[:6]}")
        grant_role(operator, group_name=AI_OPERATOR_GROUP)
        client = APIClient()
        client.force_authenticate(user=operator)
        resp = client.post(reverse("ai-registry-publish", kwargs={"pk": pid}))
        assert resp.status_code == 403, resp.content
    finally:
        process_mod._default_known_capabilities = original
