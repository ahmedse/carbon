"""
Agentic Task Orchestration — plan lifecycle tests (Sprint 23 W3-A + W3-C).

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
  - edit (W3-C): PATCH /plans/{id}/ replans and returns {added, removed,
    changed}; non-pending plans drop to pending_approval (RULE_21) with
    ``replan_gate``; step deltas applied; PATCH /plans/{id}/steps/{step}/
    edits title (intent) / instructions / depends_on and resets execution
    state.
  - pause / resume (W3-C): running → paused (consent steps untouched);
    resume pre-flights _RUNNABLE_STATUSES and re-enters run_plan_stream (SSE).
  - fork (W3-C): clones plan_json + brief into a new pending_approval Run
    (``working_notes.forked_from`` provenance; copy, not a link).

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
    """Stand-in for SkillAwarePlanner — no LLM call.

    ``plan_specs`` maps an exact brief string → plan spec dict so tests can
    simulate replanning with a different decomposition; ``default_plan_spec``
    is used when no entry matches (standard 2-step plan otherwise). The
    fixture resets both before every test.
    """

    plan_specs: dict = {}
    default_plan_spec: dict | None = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def decompose(self, **kwargs):
        utterance = (kwargs.get("utterance") or "").strip()
        spec = self.plan_specs.get(utterance) or self.default_plan_spec or {
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
        return _plan_from_steps(spec)


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
        _FakePlanner.plan_specs = {}
        _FakePlanner.default_plan_spec = None
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


# ── W5-B: guided discovery conversation ─────────────────────────────────


@pytest.mark.django_db
def test_discovery_start_returns_question(
    user, patch_engine_seams, run_ids_cleanup, monkeypatch
):
    monkeypatch.setattr(
        "ai.engine.llm.provider.chat_completion",
        AsyncMock(
            return_value=(
                '{"action": "ask", "question": "Which data sources should I analyze?"}'
            )
        ),
    )
    service = PlansService()
    result = service.start_discovery(user, brief="Summarize our carbon footprint")

    assert result["status"] == "needs_input"
    assert result["run_status"] == "discovering"
    assert result["question"] == "Which data sources should I analyze?"
    assert result["turns"] == [
        {"question": "Which data sources should I analyze?", "reply": None}
    ]

    run = Run.objects.get(id=result["id"])
    assert run.status == "discovering"
    assert run.plan_json["discovery_turns"] == result["turns"]
    run_ids_cleanup.append(run.id)


@pytest.mark.django_db
def test_discovery_advance_continues_or_completes(
    user, patch_engine_seams, run_ids_cleanup, monkeypatch
):
    monkeypatch.setattr(
        "ai.engine.llm.provider.chat_completion",
        AsyncMock(
            side_effect=[
                '{"action": "ask", "question": "Which data sources?"}',
                '{"action": "ask", "question": "What time period?"}',
            ]
        ),
    )
    service = PlansService()
    started = service.start_discovery(user, brief="Summarize our carbon footprint")
    run_ids_cleanup.append(started["id"])

    advance = service.advance_discovery(
        user, started["id"], "Use the raw emissions ledger"
    )

    assert advance["status"] == "needs_input"
    assert advance["question"] == "What time period?"
    assert advance["turns"][0] == {
        "question": "Which data sources?",
        "reply": "Use the raw emissions ledger",
    }
    assert advance["turns"][1] == {
        "question": "What time period?",
        "reply": None,
    }

    run = Run.objects.get(id=started["id"])
    assert run.status == "discovering"


@pytest.mark.django_db
def test_discovery_complete_transitions_to_pending_approval(
    user, patch_engine_seams, run_ids_cleanup, monkeypatch
):
    _FakePlanner.default_plan_spec = {
        "pattern": "root_cause",
        "source": "llm_decompose",
        "steps": [
            {
                "step_id": 0,
                "intent": "Load the emissions totals",
                "tool_name": None,
                "tool_args": {},
                "depends_on": [],
            },
        ],
        "synthesis_instruction": "Summarize.",
    }
    monkeypatch.setattr(
        "ai.engine.llm.provider.chat_completion",
        AsyncMock(
            side_effect=[
                '{"action": "ask", "question": "Which data sources?"}',
                '{"action": "complete"}',
            ]
        ),
    )
    service = PlansService()
    started = service.start_discovery(user, brief="Summarize our carbon footprint")
    run_ids_cleanup.append(started["id"])

    advance = service.advance_discovery(
        user, started["id"], "Use the raw emissions ledger"
    )

    assert advance["status"] == "plan_ready"
    assert advance["run_status"] == "pending_approval"
    assert advance["plan"]["status"] == "pending_approval"
    assert len(advance["plan"]["steps"]) == 1

    run = Run.objects.get(id=started["id"])
    assert run.status == "pending_approval"
    assert run.plan_json["discovery_turns"][0]["reply"] == "Use the raw emissions ledger"
    assert RunStep.objects.filter(run_id=run.id).count() == 1


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


# ── W3-C: edit / pause / resume / fork ───────────────────────────────────

_REVISED_PLAN_SPEC = {
    "pattern": "comparative",
    "source": "llm_decompose",
    "steps": [
        {"step_id": 0, "intent": "Load the emissions totals",
         "tool_name": "query_table", "tool_args": {}, "depends_on": []},
        {"step_id": 1, "intent": "Tally the quarterly results",
         "tool_name": None, "tool_args": {}, "depends_on": [0]},
        {"step_id": 2, "intent": "Compute quarterly totals",
         "tool_name": None, "tool_args": {}, "depends_on": [1]},
    ],
    "synthesis_instruction": "Summarize.",
}


@pytest.mark.django_db
def test_edit_plan_replans_and_returns_diff(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user)
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)
    _FakePlanner.plan_specs = {
        "Revised brief: compute quarterly totals": _REVISED_PLAN_SPEC
    }

    service = PlansService()
    result = service.edit_plan(
        user, plan.id, brief="Revised brief: compute quarterly totals"
    )

    # Still pending_approval — editing never auto-approves (RULE_21).
    assert result["status"] == "pending_approval"
    assert result["replan_gate"] is False
    assert result["brief"] == "Revised brief: compute quarterly totals"

    diff = result["diff"]
    assert [s["intent"] for s in diff["added"]] == [
        "Tally the quarterly results", "Compute quarterly totals",
    ]
    assert [s["intent"] for s in diff["removed"]] == ["Compare against the baseline"]
    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["old"]["tool_name"] is None
    assert diff["changed"][0]["new"]["tool_name"] == "query_table"

    # Durable rows reflect the new plan.
    run = Run.objects.get(id=plan.id)
    assert run.user_message == "Revised brief: compute quarterly totals"
    assert len(run.plan_json["steps"]) == 3
    assert run.plan_json["steps"][1]["intent"] == "Tally the quarterly results"
    steps = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
    assert len(steps) == 3
    assert all(s.status == "pending" for s in steps)


@pytest.mark.django_db
def test_edit_plan_active_plan_drops_to_pending_approval(
    user, patch_engine_seams, run_ids_cleanup
):
    _FakePlanner.plan_specs = {
        "Revised brief: compute quarterly totals": _REVISED_PLAN_SPEC
    }
    service = PlansService()

    for status in ("approved", "running", "paused"):
        plan = _make_plan(user, status=status)
        run_ids_cleanup.append(plan.id)

        result = service.edit_plan(
            user, plan.id, brief="Revised brief: compute quarterly totals"
        )

        assert result["status"] == "pending_approval"
        assert result["replan_gate"] is True
        assert "diff" in result
        # The revised plan must be explicitly re-approved (RULE_21).
        service.approve_plan(user, plan.id)
        assert Run.objects.get(id=plan.id).status == "approved"


@pytest.mark.django_db
def test_edit_plan_applies_step_deltas(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user)
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.edit_plan(
        user, plan.id,
        brief=plan.user_message,  # same brief — pure delta edit
        step_deltas=[
            {"action": "remove", "step_id": 1},
            {"action": "add", "intent": "Archive the results", "depends_on": [0]},
        ],
    )

    intents = [s["intent"] for s in result["steps"]]
    assert "Archive the results" in intents
    assert "Compare against the baseline" not in intents
    assert len(result["steps"]) == 2


@pytest.mark.django_db
def test_edit_step_updates_title_and_depends_on(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user)
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.edit_step(
        user, plan.id, 1,
        title="Compare against the revised baseline",
        instructions="Ignore one-off outliers.",
        depends_on=[],
    )

    assert result["status"] == "pending_approval"
    assert result["replan_gate"] is False
    step = next(s for s in result["steps"] if s["step_id"] == 1)
    assert step["intent"] == "Compare against the revised baseline"
    assert step["depends_on"] == []
    assert step["instructions"] == "Ignore one-off outliers."
    assert len(result["diff"]["changed"]) == 1


@pytest.mark.django_db
def test_edit_step_active_plan_drops_to_pending_approval(
    user, patch_engine_seams, run_ids_cleanup
):
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="completed", token="tok-1")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.edit_step(user, plan.id, 0, title="Renamed step")

    assert result["status"] == "pending_approval"
    assert result["replan_gate"] is True
    # Execution/consent state reset — the edited plan must be re-approved.
    steps = list(RunStep.objects.filter(run_id=plan.id).order_by("step_index"))
    assert all(s.status == "pending" for s in steps)
    assert all(s.confirmation_token is None for s in steps)


@pytest.mark.django_db
def test_edit_step_rejects_unknown_step(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    with pytest.raises(PlanStepError):
        service.edit_step(user, plan.id, 99, title="Nope")


@pytest.mark.django_db
def test_pause_plan_only_from_running_keeps_consent_step(
    user, patch_engine_seams, run_ids_cleanup
):
    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="awaiting_approval", token="tok-1")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    result = service.pause_plan(user, plan.id)

    assert result["status"] == "paused"
    # Pause never corrupts a consent step (consent pause is separate).
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "awaiting_approval"
    assert step.confirmation_token == "tok-1"


@pytest.mark.django_db
def test_pause_plan_rejects_non_running(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="approved")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    with pytest.raises(PlanNotRunnableError):
        service.pause_plan(user, plan.id)


@pytest.mark.django_db
def test_resume_plan_preflights_runnable_statuses(user, patch_engine_seams, run_ids_cleanup):
    service = PlansService()

    paused = _make_plan(user, status="paused")
    run_ids_cleanup.append(paused.id)
    assert service.resume_plan(user, paused.id)["status"] == "resumed"

    approved = _make_plan(user, status="approved")
    run_ids_cleanup.append(approved.id)
    assert service.resume_plan(user, approved.id)["status"] == "resumed"

    pending = _make_plan(user)  # pending_approval — must approve first
    run_ids_cleanup.append(pending.id)
    with pytest.raises(PlanNotRunnableError):
        service.resume_plan(user, pending.id)


@pytest.mark.django_db(transaction=True)
def test_resume_paused_plan_reenters_run(user, patch_engine_seams, run_ids_cleanup):
    patch_engine_seams.outcomes = {0: "completed", 1: "completed"}
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    frames = list(service._run_plan_frames_sync(user, plan.id))

    assert frames[0]["type"] == "plan_start"
    assert frames[-1]["type"] == "done"
    assert frames[-1]["status"] == "completed"


@pytest.mark.django_db
def test_fork_plan_clones_into_new_run(user, patch_engine_seams, run_ids_cleanup):
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="awaiting_approval", token="tok-1")
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    fork = service.fork_plan(user, plan.id)

    assert fork["id"] != plan.id
    assert fork["status"] == "pending_approval"
    assert fork["forked_from"] == plan.id
    assert fork["brief"] == plan.user_message
    assert len(fork["steps"]) == 2
    assert all(s["status"] == "pending" for s in fork["steps"])

    fork_run = Run.objects.get(id=fork["id"])
    assert fork_run.host_user_id == str(user.pk)
    assert fork_run.working_notes == {"forked_from": plan.id}
    run_ids_cleanup.append(fork["id"])

    # Copy, not a link — the parent ledger is untouched.
    parent = Run.objects.get(id=plan.id)
    assert parent.status == "approved"
    parent_step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert parent_step.status == "awaiting_approval"
    assert parent_step.confirmation_token == "tok-1"


@pytest.mark.django_db
def test_fork_plan_rejects_other_users_plan(
    user, other_user, patch_engine_seams, run_ids_cleanup
):
    plan = _make_plan(other_user)
    run_ids_cleanup.append(plan.id)

    service = PlansService()
    with pytest.raises(PlanNotAccessibleError):
        service.fork_plan(user, plan.id)


# ── W3-C: REST API ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_api_patch_plan_returns_diff_for_review(
    api_client, get_token_for_user, user, patch_engine_seams, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)
    _FakePlanner.plan_specs = {
        "Revised brief: compute quarterly totals": _REVISED_PLAN_SPEC
    }

    resp = api_client.patch(
        f"/carbon-api/ai/plans/{plan.id}/",
        {"brief": "Revised brief: compute quarterly totals"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "pending_approval"
    assert body["replan_gate"] is True
    assert body["diff"]["added"] and body["diff"]["removed"]
    assert Run.objects.get(id=plan.id).status == "pending_approval"


@pytest.mark.django_db
def test_api_patch_step_applies_diff_review_rule(
    api_client, get_token_for_user, user, patch_engine_seams, run_ids_cleanup
):
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    resp = api_client.patch(
        f"/carbon-api/ai/plans/{plan.id}/steps/1/",
        {"title": "Renamed step", "depends_on": []},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "pending_approval"
    assert body["replan_gate"] is True
    assert body["steps"][1]["intent"] == "Renamed step"
    assert len(body["diff"]["changed"]) == 1


@pytest.mark.django_db(transaction=True)
def test_api_pause_resume_fork_lifecycle(
    api_client, get_token_for_user, user, patch_engine_seams, run_ids_cleanup
):
    patch_engine_seams.outcomes = {0: "completed", 1: "completed"}
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Pause only from running.
    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0)
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/pause/")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "paused"

    # Resume from paused → SSE stream re-enters execution.
    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/resume/")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/event-stream")
    body = b"".join(resp.streaming_content).decode()
    assert '"type": "plan_start"' in body
    assert '"type": "done"' in body
    assert '"status": "completed"' in body

    # Resume from pending_approval → 400 (must approve first).
    pending = _make_plan(user)
    run_ids_cleanup.append(pending.id)
    resp = api_client.post(f"/carbon-api/ai/plans/{pending.id}/resume/")
    assert resp.status_code == 400

    # Fork → new pending_approval copy.
    resp = api_client.post(f"/carbon-api/ai/plans/{plan.id}/fork/")
    assert resp.status_code == 201, resp.content
    fork = resp.json()
    assert fork["id"] != plan.id
    assert fork["status"] == "pending_approval"
    assert fork["forked_from"] == plan.id
    run_ids_cleanup.append(fork["id"])
