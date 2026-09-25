"""ADR-0055 — a Chat-drafted plan is stored only on the user's consent, exactly as reviewed."""
from __future__ import annotations

import uuid

import pytest

from ai.engine.cognition.plan.planner import Plan, PlanStep
from ai.engine.cognition.state_store import ConversationState
from ai.engine.cognition.turn.plan_proposal import KIND, revised_brief

pytestmark = pytest.mark.django_db


def _drafted() -> Plan:
    return Plan(
        pattern="custom",
        steps=[
            PlanStep(step_id=1, intent="Read the 20 lowest salaries", tool_name="call_host_api",
                     tool_args={"api_name": "list_payslip_lines", "body": {"limit": 20}}),
            PlanStep(step_id=2, intent="Read their positions", tool_name="call_host_api",
                     tool_args={"api_name": "list_employees"}, depends_on=[1]),
        ],
        synthesis_instruction="",
        source="llm_decompose",
    )


def _user(username="proposal_owner"):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(username=username, password="x")


def _run_count():
    from ai.models.core import Run

    return Run.objects.count()


def test_drafting_stores_nothing(monkeypatch):
    from ai.plans_service import PlansService

    service = PlansService()
    monkeypatch.setattr(service, "_decompose", lambda *a, **k: _drafted())
    before = _run_count()
    plan_json, proposal = service.propose_plan(_user(), "lowest 20 salaries and their jobs", "c1")
    assert proposal["kind"] == KIND
    assert [s["step_id"] for s in plan_json["steps"]] == [1, 2]
    assert _run_count() == before


def _seed_state(conversation_id: str, user, plan_json: dict | None):
    from ai.models import ConversationContextRecord

    state = ConversationState()
    if plan_json is not None:
        state.open_question = {"kind": KIND, "brief": "lowest 20 salaries", "plan_json": plan_json}
    ConversationContextRecord.objects.create(
        conversation_id=conversation_id,
        instance_id="nibras",
        host_user_id=str(user.pk),
        session_json=state.to_dict(),
    )


def test_commit_stores_the_reviewed_draft_and_closes_it():
    from ai.models import ConversationContextRecord
    from ai.plans_service import PlansService

    service = PlansService()
    user = _user()
    cid = str(uuid.uuid4())
    plan_json = service._plan_to_dict(_drafted())
    _seed_state(cid, user, plan_json)

    plan = service.commit_proposal(user, cid)

    assert plan["status"] == "pending_approval"
    assert [s["intent"] for s in plan["steps"]] == [
        "Read the 20 lowest salaries", "Read their positions",
    ]
    row = ConversationContextRecord.objects.get(conversation_id=cid)
    assert ConversationState.from_dict(row.session_json).open_question == {}


def test_commit_without_a_draft_creates_nothing():
    from ai.plans_service import PlansService

    user = _user()
    cid = str(uuid.uuid4())
    _seed_state(cid, user, None)
    before = _run_count()
    with pytest.raises(ValueError):
        PlansService().commit_proposal(user, cid)
    assert _run_count() == before


def test_another_user_cannot_commit_my_draft():
    from ai.plans_service import PlansService

    service = PlansService()
    owner = _user("owner_a")
    cid = str(uuid.uuid4())
    _seed_state(cid, owner, service._plan_to_dict(_drafted()))
    with pytest.raises(ValueError):
        service.commit_proposal(_user("intruder_b"), cid)


def test_a_change_revises_the_open_draft():
    assert revised_brief("lowest 20 salaries", "add department") == (
        "lowest 20 salaries\nRevision: add department"
    )
    assert revised_brief("", "new brief") == "new brief"


def test_format_revision_keeps_reads_and_widens_export():
    from ai.engine.cognition.turn.plan_proposal import apply_format_revision

    plan = {
        "steps": [
            {"step_id": 0, "tool_name": "call_host_api",
             "tool_args": {"api_name": "analyze_committed_pay", "dimension": "org_unit"}},
            {"step_id": 1, "tool_name": "call_host_api",
             "tool_args": {"api_name": "analyze_committed_pay", "dimension": "nationality"}},
            {"step_id": 2, "tool_name": "export_document",
             "tool_args": {"format": "xlsx", "title": "Pay"}},
        ]
    }
    out = apply_format_revision(
        plan, "add also a nice executive word or pdf report",
    )
    assert [s["tool_args"].get("api_name") for s in out["steps"][:2]] == [
        "analyze_committed_pay", "analyze_committed_pay",
    ]
    exports = [s for s in out["steps"] if s["tool_name"] == "export_document"]
    assert len(exports) == 1
    assert exports[0]["tool_args"]["format"] == "pack"


def test_format_revision_ignores_a_scope_change():
    from ai.engine.cognition.turn.plan_proposal import apply_format_revision

    plan = {
        "steps": [
            {"step_id": 0, "tool_name": "export_document", "tool_args": {"format": "xlsx"}},
        ]
    }
    assert apply_format_revision(plan, "add department") is None
