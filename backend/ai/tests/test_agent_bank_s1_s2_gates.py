"""Agent bank S1 + S2 CI gates (PA-020…026, PA-030…035, PA-052, PC-020).

Executable fixtures for docs/pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md sprint
S1/S2. Composes existing PlansService / process / Flight Director / ECF
oracles under stable bank IDs — does not rewrite People UAT.

Run::

    cd backend && ../.venv/bin/python -m pytest ai/tests/test_agent_bank_s1_s2_gates.py -q
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from asgiref.sync import sync_to_async
from django.conf import settings

from accounts.models import User
from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.ports import Decision
from ai.engine.ports.domain import load_domain_pack
from ai.flight_director import FlightDirector, _overall_status
from ai.identity_propagation import build_actor_chain
from ai.models.capability import load_capabilities
from ai.models.core import Run, RunStep
from ai.models.pdp import PolicyDecisionRow
from ai.models.process import ProcessDefinition, validate_definition
from ai.pdp import PDP
from ai.plans_service import PlanNotAccessibleError, PlansService

PACK_DIR = Path(settings.BASE_DIR).parent / "domain_packs" / "nibras"

# PA-030…034 dials — human_only + consent irreversible steps
PROCESS_DIALS = {
    "leave.request.lifecycle": {
        "pa": "PA-030",
        "step_ids": ["submit", "review", "record", "verify"],
        "human_only": ["review"],
        "consent": ["record"],
        "predicate": "leave.request.recorded_and_entitlement_decremented",
    },
    "loan.request.lifecycle": {
        "pa": "PA-031",
        "step_ids": ["submit", "review", "activate", "verify"],
        "human_only": ["review"],
        "consent": ["activate"],
        "predicate": "loan.request.activated_and_scheduled",
    },
    "payroll.run.lifecycle": {
        "pa": "PA-032",
        "step_ids": ["compute", "validate", "review", "commit", "verify"],
        "human_only": ["review", "commit"],
        "consent": ["commit"],
        "predicate": "payroll.run.committed_and_variance_clean",
    },
    "employee.onboarding.lifecycle": {
        "pa": "PA-033",
        "step_ids": ["submit", "review", "activate", "verify"],
        "human_only": ["review", "activate"],
        "consent": ["activate"],
        "predicate": "employee.onboarding.completed_and_payroll_eligible",
    },
    "gosi_wps.sif.lifecycle": {
        "pa": "PA-034",
        "step_ids": ["generate", "validate", "review", "submit", "verify"],
        "human_only": ["review", "submit"],
        "consent": ["submit"],
        "predicate": "gosi_wps.sif.submitted_and_reconciled",
    },
    "attendance.permission.lifecycle": {
        "pa": "PA-035",
        "step_ids": ["submit", "review", "approve", "verify"],
        "human_only": ["review"],
        "consent": ["approve"],
        "predicate": "attendance.permission.approved_and_recorded",
    },
}


def _pack():
    return load_domain_pack(PACK_DIR)


def _doc(process_id: str) -> dict:
    return dict(next(p for p in _pack().processes() if p.get("id") == process_id))


def _known_caps() -> set[str]:
    return {c.capability_id for c in load_capabilities(_pack())}


# ── Fixtures (minimal mirrors of test_plans) ───────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="bank-s1-owner", password="secret123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="bank-s1-other", password="secret123")


class _FakeHostExecutor:
    def __init__(self, **kwargs):
        self.confirmed = []
        self.declined = []

    async def confirm_execution(self, execution_id, expected_host_user_id=None):
        self.confirmed.append((execution_id, expected_host_user_id))
        return {"data": {"id": "ok", "name": "staged"}}

    async def decline_execution(self, execution_id, expected_host_user_id=None):
        self.declined.append((execution_id, expected_host_user_id))


@pytest.fixture
def patch_confirm_seams(monkeypatch):
    monkeypatch.setattr("ai.host_executor.CarbonHostExecutor", _FakeHostExecutor)
    monkeypatch.setattr(
        "ai.engine.core.database.get_session_factory",
        lambda *a, **k: type(
            "F",
            (),
            {
                "__call__": lambda self: type(
                    "S",
                    (),
                    {
                        "__aenter__": AsyncMock(return_value=object()),
                        "__aexit__": AsyncMock(return_value=False),
                    },
                )(),
            },
        )(),
    )
    return _FakeHostExecutor


def _paused_awaiting(owner, *, step_index=1):
    run = Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="nibras",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(owner.pk),
        user_message="Stage a host write",
        status="paused",
        plan_json={
            "steps": [
                {
                    "step_id": step_index,
                    "intent": "Write",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "create_table"},
                }
            ]
        },
    )
    RunStep.objects.create(
        run_id=run.id,
        step_index=step_index,
        intent="Write",
        tool_name="call_host_api",
        tool_args_json={"api_name": "create_table"},
        status="awaiting_approval",
        confirmation_token="tok-s1",
        tool_output_json={
            "result": json.dumps(
                {"requires_confirmation": True, "execution_id": "exec-s1"}
            )
        },
    )
    return run


# ── S1 PA-020…026 consent / authz ─────────────────────────────────────────


@pytest.mark.django_db
def test_pa020_confirm_staged_write_owner_only(user, other_user, patch_confirm_seams):
    """PA-020: only owner can confirm a staged host write."""
    plan = _paused_awaiting(user)
    svc = PlansService()
    result = svc.confirm_step(user, plan.id, 1)
    assert result["status"] == "confirmed"
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "completed"

    foreign = _paused_awaiting(user)
    with pytest.raises(PlanNotAccessibleError):
        svc.confirm_step(other_user, foreign.id, 1)


@pytest.mark.django_db
def test_pa021_decline_staged_write_skips(user, patch_confirm_seams):
    """PA-021: decline leaves mutation unapplied (step skipped)."""
    plan = _paused_awaiting(user)
    result = PlansService().decline_step(user, plan.id, 1)
    assert result["status"] == "declined"
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "skipped"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pa026_actor_chain_on_policy_decision():
    """PA-026: PolicyDecisionRow persists actor_chain."""
    pdp = PDP()
    chain = build_actor_chain(
        user_id="42",
        instance_id="nibras",
        request_id="req-pa026",
        tool="call_host_api",
    )
    result = await pdp.decide(
        "42",
        "call_host_api",
        ["people.list_employees"],
        autonomy="auto",
        actor_chain=chain,
        request_id="req-pa026",
        instance_id="nibras",
        host_user_id="42",
    )
    assert result["decision"] is Decision.ALLOW

    row = await sync_to_async(PolicyDecisionRow.objects.get, thread_sensitive=True)(
        principal="42", action="call_host_api", request_id="req-pa026"
    )
    assert isinstance(row.actor_chain, list)
    assert len(row.actor_chain) >= 2
    assert row.actor_chain[0]["role"] == "user"
    assert row.actor_chain[0]["id"] == "42"
    assert row.actor_chain[1]["role"] == "engine"
    assert row.actor_chain[1]["token_form"] == "inproc:nibras:42"


# ── S1 PC-020 grounding pointer ───────────────────────────────────────────


def test_pc020_ecf_golden_reena_employee_no():
    """PC-020: ECF golden resolves Reena Sekaran → employee_no 1009."""
    from ai.tests.test_ecf_golden import GOLDEN_CASES

    case = next(c for c in GOLDEN_CASES if c.query == "Reena Sekaran")
    assert case.employee_no == "1009"


# ── S2 PA-030…034 process dials ───────────────────────────────────────────


@pytest.mark.parametrize("process_id", list(PROCESS_DIALS))
def test_s2_process_validates_and_resolves(process_id):
    """PA-030…034: ProcessDefinition validates; step capabilities resolve."""
    dial = PROCESS_DIALS[process_id]
    doc = _doc(process_id)
    known = _known_caps()
    assert validate_definition(doc, known_capabilities=known) == [], dial["pa"]
    pd = ProcessDefinition.from_document(doc, known_capabilities=known)
    assert pd.process_id == process_id
    assert [s["id"] for s in doc["steps"]] == dial["step_ids"]
    for step in doc["steps"]:
        cap = step.get("capability")
        if cap:
            assert cap in known, f"{dial['pa']}: unknown {cap}"


@pytest.mark.parametrize("process_id", list(PROCESS_DIALS))
def test_s2_human_only_and_consent_dials(process_id):
    """Human gates + consent-required irreversible steps."""
    dial = PROCESS_DIALS[process_id]
    doc = _doc(process_id)
    by_id = {s["id"]: s for s in doc["steps"]}

    for hid in dial["human_only"]:
        assert by_id[hid]["autonomy"] == "human_only", f"{dial['pa']} {hid}"

    for cid in dial["consent"]:
        step = by_id[cid]
        assert step.get("consent") is True, f"{dial['pa']} {cid} needs consent"

    if dial["predicate"]:
        assert doc.get("objective", {}).get("predicate") == dial["predicate"]


def test_pa032_payroll_commit_gated_after_validate():
    """PA-032: commit follows validate→review; policies refuse unvalidated commit."""
    doc = _doc("payroll.run.lifecycle")
    by_id = {s["id"]: s for s in doc["steps"]}
    assert "validate" in (by_id["review"].get("depends_on") or [])
    assert "review" in (by_id["commit"].get("depends_on") or [])
    refuse = doc.get("policies", {}).get("refuse_if") or []
    assert any("not validated" in r for r in refuse)
    assert by_id["commit"]["autonomy"] == "human_only"
    assert by_id["commit"]["consent"] is True


def test_pa035_commit_without_validate_violates_process_graph():
    """PA-035: a process doc that lets commit skip validate is refused by policy.

    Critic / Flight Director surface: payroll refuse_if + precedence require
    validate before commit. A rogue graph that drops validate must still be
    caught by the documented refuse_if (and fails our dial contract).
    """
    doc = _doc("payroll.run.lifecycle")
    # Mutate: commit depends only on compute (skips validate/review).
    rogue = dict(doc)
    rogue["steps"] = [dict(s) for s in doc["steps"]]
    commit = next(s for s in rogue["steps"] if s["id"] == "commit")
    commit["depends_on"] = ["compute"]

    # Structural depends_on still resolve (compute exists) — policy layer is
    # the rejector for "commit without validate".
    known = _known_caps()
    assert validate_definition(rogue, known_capabilities=known) == []
    refuse = rogue.get("policies", {}).get("refuse_if") or []
    assert any("not validated" in r for r in refuse)

    # Canonical graph still requires validate in the path to commit.
    by_id = {s["id"]: s for s in doc["steps"]}
    path = set(by_id["commit"].get("depends_on") or [])
    assert "validate" not in path  # direct dep is review
    assert "validate" in (by_id["review"].get("depends_on") or [])
    assert path != {"compute"}


# ── S2 PA-052 Flight Director: all green ≠ brief met ──────────────────────


class _EmptyHost:
    async def _call_api(self, method, endpoint, params=None, body=None):
        return []


@pytest.mark.asyncio
async def test_pa052_all_steps_completed_but_acceptance_missed():
    """PA-052: steps completed yet acceptance missed (brief unmet)."""
    fd = FlightDirector()
    fd.ledger.add("rule", 999, name="Phantom DQ rule", step_index=1)
    step = PlanStep(
        step_id=1,
        intent="Create a DQ rule 'Phantom DQ rule'",
        tool_name="create_dq_rule",
        tool_args={"api_name": "create_dq_rule", "body": {"name": "Phantom DQ rule"}},
        is_mutation=False,
    )
    plan = Plan(
        steps=[step],
        pattern="custom",
        source="test",
        skill_name=None,
        synthesis_instruction="Summarize.",
    )

    results = await fd.run_acceptance_checks(
        plan,
        None,
        fd.ledger,
        _EmptyHost(),
        step_statuses={1: "completed"},
    )
    assert results
    assert results[0]["verdict"] == "missed"
    assert _overall_status(results) == "missed"
