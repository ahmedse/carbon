"""Chat-native plan confirm workflow (``edit_plan`` / ``approve_plan``) — G-D.

Covers the chat bridges that complete the agentic orchestration lifecycle
inside the chat (no bounce to the Tasks panel for the *planning* half):

    discuss → decompose → propose → (edit_plan) → "settled?" → (approve_plan)

F6 exit gate assertions:
  * F6-01 — ``plan_task`` produces a ``pending_approval`` plan, never inline
    execution (``plan_created``, "Nothing has executed").
  * F6-02/F6-06 — editing/approval never fabricates completion: statuses are
    ``pending_approval`` → ``approved``, and the plan step statuses reflect
    reality (``pending`` until run).
  * F6-03/F6-05 — plan-level consent gate: ``approve_plan`` is the explicit
    settle gate; execution is a separate, explicit ``run`` action.
  * provenance — outcome copy is in product terms and names the audit ledger
    (RULE_23, no engine leakage).

The ``edit_plan``/``approve_plan`` plugins delegate every state transition to
``ai.plans_service.PlansService`` (RULE_20/RULE_21) — the same owner-scoped,
CBAC service the plans API views use.
"""
from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from django.utils import timezone

from accounts.models import User
from ai.engine.agent.plugins import ToolContext
from ai.models.core import Run, RunStep
from ai.plans_service import PlansService
from ai.plugins.plan_lifecycle import ApprovePlan, EditPlan
from ai.plugins.plan_task import PlanTask


# ── Engine seam fakes (mirror ai/tests/test_plans.py) ────────────────────


def _plan_from_steps(spec: dict):
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    return Plan(
        pattern=spec.get("pattern", "custom"),
        steps=[
            PlanStep(
                step_id=int(s["step_id"]),
                intent=s["intent"],
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args") or {},
                depends_on=s.get("depends_on") or [],
            )
            for s in spec.get("steps", [])
        ],
        synthesis_instruction=spec.get("synthesis_instruction", ""),
        source=spec.get("source", "custom"),
        skill_name=spec.get("skill_name"),
    )


class _FakePlanner:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def decompose(self, **kwargs):
        return _plan_from_steps({
            "pattern": "root_cause",
            "source": "llm_decompose",
            "steps": [
                {"step_id": 0, "intent": "Load the emissions totals",
                 "tool_name": None, "tool_args": {}, "depends_on": []},
                {"step_id": 1, "intent": "Compare against the baseline",
                 "tool_name": None, "tool_args": {}, "depends_on": [0]},
            ],
            "synthesis_instruction": "Summarize findings.",
        })


class _FakeSession:
    def __init__(self):
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeFactory:
    def __call__(self):
        return _FakeSession()


class _FakeReActLoop:
    outcomes: dict = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def _sync_run(self, run_id):
        from asgiref.sync import sync_to_async

        run = Run.objects.get(id=run_id)
        run.status = "running"
        run.save(update_fields=["status", "updated_at"])
        for step in RunStep.objects.filter(run_id=run_id).order_by("step_index"):
            step.status = self.outcomes.get(step.step_index, "completed")
            step.draft_text = f"Step {step.step_index} done"
            step.critic_verdict = "pass"
            step.save(update_fields=["status", "draft_text", "critic_verdict", "updated_at"])
        run.status = "completed"
        run.final_response = "All steps completed."
        run.total_llm_calls = 3
        run.total_latency_ms = 1234.5
        run.completed_at = timezone.now()
        run.save(update_fields=[
            "status", "final_response", "total_llm_calls",
            "total_latency_ms", "completed_at", "updated_at",
        ])

    async def run(self, plan, **kwargs):
        from asgiref.sync import sync_to_async

        await sync_to_async(self._sync_run)(kwargs["resume_run_id"])
        return None


@pytest.fixture
def patch_engine_seams(monkeypatch):
    monkeypatch.setattr(
        "ai.engine.cognition.plan.planner.SkillAwarePlanner", _FakePlanner
    )
    monkeypatch.setattr(
        "ai.engine.cognition.plan.loop.ReActLoop", _FakeReActLoop
    )
    _FakeReActLoop.outcomes = {0: "completed", 1: "completed"}
    monkeypatch.setattr(
        "ai.engine.llm.prompts.build_chat_prompt",
        AsyncMock(return_value="You are Carbon."),
    )
    monkeypatch.setattr(
        "ai.engine.core.database.get_session_factory",
        lambda *a, **k: _FakeFactory(),
    )
    monkeypatch.setattr(
        "ai.engine_runtime._carbon_instance_config",
        lambda *a, **k: {
            "display_name": "Carbon",
            "description": "Carbon Data Trust",
            "persona": {},
            "api_catalog": [],
            "navigation_routes": [],
            "domain_topics": [],
        },
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="plan-lifecycle", password="secret123")


@pytest.fixture
def run_ids_cleanup():
    ids: list[str] = []
    yield ids
    RunStep.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()


def _ctx(host_user_id: str | None, conversation_id: str = "conv-lc") -> ToolContext:
    return ToolContext(conversation_id=conversation_id, host_user_id=host_user_id)


def _run_plugin(plugin, args, *, host_user_id="42"):
    return asyncio.run(plugin.execute(args, ctx=_ctx(host_user_id)))


def _create_plan(user, run_ids_cleanup) -> str:
    plan = PlansService().create_plan(
        user,
        brief="Audit the emissions uploads for completeness",
        conversation_id="conv-lc",
    )
    run_ids_cleanup.append(plan["id"])
    return plan["id"]


# ── Registration + metadata ──────────────────────────────────────────────


def test_plan_lifecycle_plugins_registered():
    from ai.plugins import register_builtin_plugins
    from ai.engine.agent.plugins import registered_plugins

    register_builtin_plugins()
    names = {p.name for p in registered_plugins()}
    assert {"plan_task", "edit_plan", "approve_plan"} <= names


def test_edit_plan_metadata():
    plugin = EditPlan()
    assert plugin.requires_confirmation is False
    assert {"plan_id", "brief", "step_deltas"} <= set(plugin.input_schema["properties"])


def test_approve_plan_metadata():
    plugin = ApprovePlan()
    assert plugin.requires_confirmation is False
    assert "plan_id" in plugin.input_schema["properties"]


# ── Auth gating ──────────────────────────────────────────────────────────


def test_edit_plan_requires_authenticated_session():
    result = _run_plugin(EditPlan(), {"brief": "revise"}, host_user_id=None)
    assert "error" in result
    assert "authenticated session" in result["error"]


def test_approve_plan_requires_authenticated_session():
    result = _run_plugin(ApprovePlan(), {}, host_user_id=None)
    assert "error" in result
    assert "authenticated session" in result["error"]


# ── Validation ───────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_edit_plan_requires_brief_or_deltas(user):
    result = _run_plugin(EditPlan(), {}, host_user_id=str(user.pk))
    assert "error" in result
    assert "brief" in result["error"].lower()


@pytest.mark.django_db
def test_approve_plan_unknown_user_is_graceful():
    result = _run_plugin(ApprovePlan(), {}, host_user_id="does-not-exist")
    assert "error" in result


# ── Chat-native confirm workflow (F6) ────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_edit_plan_revises_and_never_auto_approves(
    user, patch_engine_seams, run_ids_cleanup
):
    plan_id = _create_plan(user, run_ids_cleanup)
    result = _run_plugin(
        EditPlan(),
        {"plan_id": plan_id, "brief": "Audit emissions AND compare quarters"},
        host_user_id=str(user.pk),
    )

    assert result["action"] == "plan_edited"
    assert result["plan_id"] == plan_id
    # Editing NEVER auto-approves: still pending_approval for re-review.
    assert result["status"] == "pending_approval"
    assert "diff" in result
    run = Run.objects.get(id=plan_id)
    assert run.status == "pending_approval"


@pytest.mark.django_db(transaction=True)
def test_approve_plan_settles_plan(
    user, patch_engine_seams, run_ids_cleanup
):
    plan_id = _create_plan(user, run_ids_cleanup)
    result = _run_plugin(
        ApprovePlan(), {"plan_id": plan_id}, host_user_id=str(user.pk)
    )

    assert result["action"] == "plan_approved"
    assert result["plan_id"] == plan_id
    assert result["status"] == "approved"
    # Provenance in product terms — names the audit ledger, no engine leakage.
    assert "audit ledger" in result["message"]
    assert "Pulse" not in result["message"]
    assert "ReActLoop" not in result["message"]

    run = Run.objects.get(id=plan_id)
    assert run.status == "approved"


@pytest.mark.django_db(transaction=True)
def test_approve_plan_rejects_non_pending(
    user, patch_engine_seams, run_ids_cleanup
):
    plan_id = _create_plan(user, run_ids_cleanup)
    _run_plugin(ApprovePlan(), {"plan_id": plan_id}, host_user_id=str(user.pk))
    # Second approval of an already-approved plan → graceful error.
    result = _run_plugin(
        ApprovePlan(), {"plan_id": plan_id}, host_user_id=str(user.pk)
    )
    assert "error" in result
    assert "pending" in result["error"].lower()


@pytest.mark.django_db(transaction=True)
def test_plan_task_does_not_fabricate_completion(
    user, patch_engine_seams, run_ids_cleanup
):
    """F6-06: plan_task drafts a plan — step statuses are pending, not done."""
    result = _run_plugin(
        PlanTask(),
        {"brief": "Plan the monthly DQ audit"},
        host_user_id=str(user.pk),
    )
    run_ids_cleanup.append(result["plan_id"])

    assert result["action"] == "plan_created"
    assert result["status"] == "pending_approval"
    assert "Nothing has executed" in result["message"]

    run = Run.objects.get(id=result["plan_id"])
    assert run.status == "pending_approval"
    statuses = set(RunStep.objects.filter(run_id=run.id).values_list("status", flat=True))
    assert statuses == {"pending"}


# ── End-to-end: plan_task → approve_plan → run → completed ───────────────


@pytest.mark.django_db(transaction=True)
def test_full_chat_confirm_workflow_end_to_end(
    user, patch_engine_seams, run_ids_cleanup
):
    """The full agentic loop settles and runs with an audit ledger.

    plan_task (pending_approval) → approve_plan (approved) → run (completed).
    Step statuses reflect reality at each gate — no fabricated completion.
    """
    # 1. plan_task — plans are plans (F6-01).
    planned = _run_plugin(
        PlanTask(),
        {"brief": "Plan the emissions completeness audit"},
        host_user_id=str(user.pk),
    )
    plan_id = planned["plan_id"]
    run_ids_cleanup.append(plan_id)
    assert planned["action"] == "plan_created"
    assert planned["status"] == "pending_approval"

    # 2. approve_plan — the explicit settle gate (F6-03).
    approved = _run_plugin(
        ApprovePlan(), {"plan_id": plan_id}, host_user_id=str(user.pk)
    )
    assert approved["action"] == "plan_approved"
    assert approved["status"] == "approved"

    # 3. run — execution is a separate, explicit action; steps complete with
    #    the audit ledger intact (ledger: usage + final_response).
    service = PlansService()
    frames = list(service._run_plan_frames_sync(user, plan_id))
    types = [f["type"] for f in frames]
    assert types[0] == "plan_start"
    assert types[-1] == "done"
    assert frames[-1]["status"] == "completed"

    run = Run.objects.get(id=plan_id)
    assert run.status == "completed"
    assert run.total_llm_calls == 3
    step_statuses = set(
        RunStep.objects.filter(run_id=run.id).values_list("status", flat=True)
    )
    assert step_statuses == {"completed"}
