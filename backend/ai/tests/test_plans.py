"""
Agentic Task Orchestration — plan lifecycle tests (Sprint 23 W3-A).

Covers:
  - create: brief → pending_approval plan + RunStep rows (planning only,
    no execution — RULE_21).
  - owner scoping (CBAC): list/get/approve/run reject other users' plans.
  - plan-level consent: approve / decline transitions.
  - SSE run stream frame protocol: plan_start → step_start → step_result →
    step_end → done; step_confirm on a consent-gated (paused) step.
  - step-level consent: confirm executes the staged mutation (CarbonHostExecutor
    seam), decline skips it.
  - stop: cancels run + skips pending steps.
  - ledger: usage, confirmations, replans, provenance, actor.

Engine seams are patched at their lazy import points — the engine itself is
untouched (W3-A is a product wrapper, not an engine rewrite).
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from django.utils import timezone

from accounts.models import User
from ai.models.core import Run, RunStep
from ai.plans_service import (
    PlanNotAccessibleError,
    PlanNotRunnableError,
    PlanStepError,
    PlansService,
)


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="plan-worker", password="secret123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="plan-other", password="secret123")


def _make_plan(user, brief="Summarize the emissions data", status="pending_approval"):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message=brief,
        status=status,
        plan_json={
            "pattern": "root_cause",
            "source": "llm_decompose",
            "skill_name": None,
            "synthesis_instruction": "Summarize findings.",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Load the emissions totals",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [],
                },
                {
                    "step_id": 1,
                    "intent": "Compare against the baseline",
                    "tool_name": None,
                    "tool_args": {},
                    "depends_on": [0],
                },
            ],
        },
    )


def _make_step(run, step_index=0, status="pending", tool_output=None, token=None):
    return RunStep.objects.create(
        run_id=run.id,
        step_index=step_index,
        intent=f"Step {step_index}",
        tool_name=None,
        tool_args_json={},
        depends_on_json=[],
        status=status,
        tool_output_json=tool_output,
        confirmation_token=token,
    )


def _plan_from_steps(plan_json_steps):
    """Build a Plan object matching _make_plan's plan_json (for fake planner)."""
    from ai.engine.cognition.plan.planner import Plan, PlanStep

    return Plan(
        pattern=plan_json_steps.get("pattern", "custom"),
        steps=[
            PlanStep(
                step_id=int(s["step_id"]),
                intent=s["intent"],
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args") or {},
                depends_on=s.get("depends_on") or [],
            )
            for s in plan_json_steps.get("steps", [])
        ],
        synthesis_instruction=plan_json_steps.get("synthesis_instruction", ""),
        source=plan_json_steps.get("source", "custom"),
        skill_name=plan_json_steps.get("skill_name"),
    )


class _FakePlanner:
    """Stand-in for SkillAwarePlanner — no LLM call."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def decompose(self, **kwargs):
        return _plan_from_steps(
            {
                "pattern": "root_cause",
                "source": "llm_decompose",
                "steps": [
                    {"step_id": 0, "intent": "Load the emissions totals",
                     "tool_name": None, "tool_args": {}, "depends_on": []},
                    {"step_id": 1, "intent": "Compare against the baseline",
                     "tool_name": None, "tool_args": {}, "depends_on": [0]},
                ],
                "synthesis_instruction": "Summarize findings.",
            }
        )


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


class _FakeHostExecutor:
    """Stand-in for CarbonHostExecutor — records confirm/decline calls."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.confirmed = []
        self.declined = []

    async def confirm_execution(self, execution_id, expected_host_user_id=None):
        self.confirmed.append((execution_id, expected_host_user_id))
        return {"data": {"id": "rule-1", "name": "Test rule"}}

    async def decline_execution(self, execution_id, expected_host_user_id=None):
        self.declined.append((execution_id, expected_host_user_id))


class _FakeReActLoop:
    """Stand-in for ReActLoop — simulates durable step outcomes.

    ``outcomes`` maps step_index → status to write (completed | failed |
    awaiting_approval).  When a step lands on ``awaiting_approval`` the run
    pauses (engine P1.3 behaviour).  The fixture resets ``outcomes`` before
    every test.
    """

    outcomes: dict = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def _sync_run(self, run_id):
        """Sync body — executed through sync_to_async (same thread/connection)."""
        run = Run.objects.get(id=run_id)
        run.status = "running"
        run.save(update_fields=["status", "updated_at"])

        paused = False
        for step in RunStep.objects.filter(run_id=run_id).order_by("step_index"):
            outcome = self.outcomes.get(step.step_index, "completed")
            step.status = outcome
            step.critic_verdict = "pass"
            step.draft_text = f"Step {step.step_index} done"
            if outcome == "awaiting_approval":
                step.confirmation_token = f"tok-{step.step_index}"
                step.tool_output_json = {
                    "result": json.dumps(
                        {
                            "requires_confirmation": True,
                            "execution_id": f"exec-{step.step_index}",
                        }
                    )
                }
                paused = True
                step.save(
                    update_fields=[
                        "status", "critic_verdict", "draft_text",
                        "confirmation_token", "tool_output_json", "updated_at",
                    ]
                )
                break
            if outcome == "failed":
                step.error = "Step failed"
                step.critic_verdict = "veto"
            step.save(
                update_fields=[
                    "status", "critic_verdict", "draft_text", "error", "updated_at",
                ]
            )

        run.status = "paused" if paused else "completed"
        run.final_response = "All steps completed." if not paused else None
        run.total_llm_calls = 3
        run.total_latency_ms = 1234.5
        run.completed_at = timezone.now() if not paused else None
        run.save(
            update_fields=[
                "status", "final_response", "total_llm_calls",
                "total_latency_ms", "completed_at", "updated_at",
            ]
        )

    async def run(self, plan, **kwargs):
        from asgiref.sync import sync_to_async

        await sync_to_async(self._sync_run)(kwargs["resume_run_id"])
        return None


@pytest.fixture
def patch_engine_seams(monkeypatch):
    """Patch every lazy engine import point used by the service."""

    def _install():
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
        monkeypatch.setattr(
            "ai.engine_runtime._build_chat_user_info",
            lambda *a, **k: {"username": "plan-worker", "display_name": "Plan Worker", "roles": []},
        )
        monkeypatch.setattr(
            "ai.host_executor.CarbonHostExecutor", _FakeHostExecutor
        )

    _install()
    return _FakeReActLoop


@pytest.fixture
def run_ids_cleanup():
    ids: list[str] = []
    yield ids
    RunStep.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()


# ── Create ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_create_plan_persists_reviewable_plan(user, patch_engine_seams, run_ids_cleanup):
    service = PlansService()
    plan = service.create_plan(
        user, brief="Investigate the emissions spike and compare quarters"
    )

    assert plan["status"] == "pending_approval"
    assert plan["pattern"] == "root_cause"
    assert len(plan["steps"]) == 2
    assert [s["step_id"] for s in plan["steps"]] == [0, 1]
    assert all(s["status"] == "pending" for s in plan["steps"])

    run = Run.objects.get(id=plan["id"])
    assert run.host_user_id == str(user.pk)
    assert run.instance_id == "carbon"
    assert run.plan_json["source"] == "llm_decompose"
    assert RunStep.objects.filter(run_id=run.id).count() == 2
    run_ids_cleanup.append(run.id)


@pytest.mark.django_db
def test_create_plan_rejects_empty_brief(user, patch_engine_seams):
    service = PlansService()
    with pytest.raises(ValueError):
        service.create_plan(user, brief="   ")


# ── Owner scoping (CBAC) ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_list_plans_is_owner_scoped(user, other_user, patch_engine_seams, run_ids_cleanup):
    mine = _make_plan(user)
    _make_plan(other_user)
    run_ids_cleanup.extend([mine.id])

    service = PlansService()
    result = service.list_plans(user)

    assert result["count"] == 1
    assert result["plans"][0]["id"] == mine.id


@pytest.mark.django_db
def test_get_plan_rejects_other_users_plan(user, other_user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(other_user, status="approved")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    with pytest.raises(PlanNotAccessibleError):
        service.get_plan(user, plan.id)


# ── Plan-level consent ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_approve_plan_transitions_to_approved(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.approve_plan(user, plan.id)

    assert result["status"] == "approved"
    run = Run.objects.get(id=plan.id)
    assert run.status == "approved"


@pytest.mark.django_db
def test_approve_plan_rejects_non_pending(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="approved")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    with pytest.raises(PlanNotRunnableError):
        service.approve_plan(user, plan.id)


@pytest.mark.django_db
def test_decline_plan_cancels_and_skips_steps(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user)
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.decline_plan(user, plan.id)

    assert result["status"] == "cancelled"
    assert all(s["status"] == "skipped" for s in result["steps"])


# ── SSE run stream ───────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_run_stream_emits_step_frames_and_done(user, patch_engine_seams, run_ids_cleanup):
    patch_engine_seams.outcomes = {0: "completed", 1: "completed"}
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    frames = list(service._run_plan_frames_sync(user, plan.id))

    types = [f["type"] for f in frames]
    assert types[0] == "plan_start"
    assert types.count("step_start") == 2
    assert types.count("step_result") == 2
    assert types.count("step_end") == 2
    assert types[-1] == "done"

    done = frames[-1]
    assert done["status"] == "completed"
    assert done["final_response"] == "All steps completed."

    run = Run.objects.get(id=plan.id)
    assert run.status == "completed"
    assert run.total_llm_calls == 3
    assert run.total_latency_ms == 1234.5


@pytest.mark.django_db(transaction=True)
def test_run_stream_emits_step_confirm_on_consent_gate(
    user, patch_engine_seams, run_ids_cleanup
):
    # Step 1 pauses for consent (P1.3) — engine never auto-runs mutations.
    patch_engine_seams.outcomes = {0: "completed", 1: "awaiting_approval"}
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    frames = list(service._run_plan_frames_sync(user, plan.id))

    types = [f["type"] for f in frames]
    assert "step_confirm" in types
    confirm = next(f for f in frames if f["type"] == "step_confirm")
    assert confirm["step_id"] == 1

    done = frames[-1]
    assert done["type"] == "done"
    assert done["status"] == "paused"

    run = Run.objects.get(id=plan.id)
    assert run.status == "paused"
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "awaiting_approval"
    assert step.confirmation_token


@pytest.mark.django_db(transaction=True)
def test_run_stream_rejects_unrunnable_plan(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="completed")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    frames = list(service._run_plan_frames_sync(user, plan.id))

    assert frames[0]["type"] == "error"
    assert "not runnable" in frames[0]["error"]


# ── Step-level consent ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_confirm_step_executes_staged_mutation(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="paused")
    _make_step(
        plan,
        step_index=1,
        status="awaiting_approval",
        token="tok-1",
        tool_output={
            "result": json.dumps(
                {
                    "requires_confirmation": True,
                    "execution_id": "exec-1",
                }
            )
        },
    )
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.confirm_step(user, plan.id, 1)

    assert result == {"status": "confirmed", "plan_id": plan.id, "step_id": 1}
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "completed"


@pytest.mark.django_db
def test_decline_step_skips_without_executing(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="paused")
    _make_step(
        plan,
        step_index=1,
        status="awaiting_approval",
        token="tok-1",
        tool_output={
            "result": json.dumps(
                {
                    "requires_confirmation": True,
                    "execution_id": "exec-1",
                }
            )
        },
    )
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.decline_step(user, plan.id, 1)

    assert result["status"] == "declined"
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "skipped"


@pytest.mark.django_db
def test_confirm_step_rejects_wrong_owner(user, other_user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(other_user, status="paused")
    _make_step(
        plan,
        step_index=1,
        status="awaiting_approval",
        token="tok-1",
        tool_output={"result": json.dumps({"execution_id": "exec-1"})},
    )
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    with pytest.raises(PlanNotAccessibleError):
        service.confirm_step(user, plan.id, 1)


# ── Stop / ledger ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_stop_plan_cancels_and_skips_pending(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.stop_plan(user, plan.id)

    assert result["status"] == "cancelled"
    assert all(s["status"] == "skipped" for s in result["steps"])


@pytest.mark.django_db
def test_ledger_aggregates_usage_confirmations_provenance(
    user, patch_engine_seams, run_ids_cleanup
):
    plan = _make_plan(user, status="completed")
    _make_step(plan, step_index=0, status="completed", token="tok-0")
    _make_step(plan, step_index=1, status="completed", token="tok-1")
    run = Run.objects.get(id=plan.id)
    run.total_latency_ms = 900.5
    run.total_llm_calls = 4
    run.total_tokens = 1200
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            "total_latency_ms", "total_llm_calls", "total_tokens",
            "completed_at", "updated_at",
        ]
    )
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    ledger = service.get_ledger(user, plan.id)

    assert ledger["plan_id"] == plan.id
    assert ledger["provenance"]["pattern"] == "root_cause"
    assert ledger["provenance"]["source"] == "llm_decompose"
    assert ledger["usage"]["total_latency_ms"] == 900.5
    assert ledger["usage"]["total_llm_calls"] == 4
    assert ledger["usage"]["total_tokens"] == 1200
    assert ledger["actor"]["user_id"] == str(user.pk)
    assert len(ledger["steps"]) == 2
    assert any(c["step_id"] == 1 for c in ledger["confirmations"])


# ── REST API ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_api_requires_auth(api_client):
    resp = api_client.get("/carbon-api/ai/plans/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_api_create_and_approve_flow(
    api_client, get_token_for_user, user, patch_engine_seams, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.post(
        "/carbon-api/ai/plans/",
        {"brief": "Investigate the emissions spike and compare quarters"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    plan = resp.json()
    assert plan["status"] == "pending_approval"
    run_ids_cleanup.append(plan["id"])

    resp = api_client.post(f"/carbon-api/ai/plans/{plan['id']}/approve/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "approved"


@pytest.mark.django_db(transaction=True)
def test_api_run_returns_sse_stream(
    api_client, get_token_for_user, user, patch_engine_seams, run_ids_cleanup
):
    patch_engine_seams.outcomes = {0: "completed", 1: "completed"}
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/run/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/event-stream")

    body = b"".join(resp.streaming_content).decode()
    assert "data: " in body
    assert '"type": "plan_start"' in body
    assert '"type": "done"' in body
    assert '"status": "completed"' in body
