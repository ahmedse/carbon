"""
W6-E — F-28 step steering while paused + F-29 plan scheduling.

F-28 (step steering): editing a not-yet-executed (``pending``) step's
service-owned metadata (``instructions``/``intent``) on a PAUSED run keeps
the plan paused and is honored on resume — no re-approval, no ledger wipe
(RULE_21 still applies: editing an executed or consent-awaiting step drops
back to review).

F-29 (scheduling): ``RunSchedule`` (cron_expr / one-off run_at) +
``materialize_due_schedules`` — idempotent, atomic claim on ``next_run_at``,
materializes due schedules into fresh ``pending_approval`` Runs owned by the
schedule owner (RULE_21 — nothing executes without approval).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from unittest.mock import AsyncMock

from accounts.models import User
from ai.models.core import PlanTemplate, Run, RunSchedule, RunStep
from ai.plans_service import (
    PlanNotAccessibleError,
    PlansService,
)

_STEPS_2 = [
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
]

_PLAN_JSON_2 = {
    "pattern": "root_cause",
    "source": "llm_decompose",
    "skill_name": None,
    "synthesis_instruction": "Summarize findings.",
    "steps": json.loads(json.dumps(_STEPS_2)),
}


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="w6e-worker", password="secret123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="w6e-other", password="secret123")


def _make_plan(user, brief="Summarize the emissions data", status="pending_approval"):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message=brief,
        status=status,
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
    )


def _make_step(run, step_index=0, status="pending", token=None):
    return RunStep.objects.create(
        run_id=run.id,
        step_index=step_index,
        intent=f"Step {step_index}",
        tool_name=None,
        tool_args_json={},
        depends_on_json=[],
        status=status,
        confirmation_token=token,
    )


@pytest.fixture
def cleanup():
    ids: list[str] = []
    schedule_ids: list[str] = []
    yield ids, schedule_ids
    RunStep.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()
    RunSchedule.objects.filter(id__in=schedule_ids).delete()


# ── F-28: step steering while paused ─────────────────────────────────────


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
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeReActLoop:
    """Stand-in for ReActLoop — simulates the durable resume write-back."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def _sync_run(self, run_id):
        from django.utils import timezone as tz

        run = Run.objects.get(id=run_id)
        run.status = "running"
        run.save(update_fields=["status", "updated_at"])
        for step in RunStep.objects.filter(run_id=run_id).order_by("step_index"):
            if step.status == "completed":
                continue  # already executed — resume skips it
            step.status = "completed"
            step.critic_verdict = "pass"
            step.draft_text = f"Step {step.step_index} done"
            step.save(
                update_fields=["status", "critic_verdict", "draft_text", "updated_at"]
            )
        run.status = "completed"
        run.final_response = "All steps completed."
        run.completed_at = tz.now()
        run.save(
            update_fields=["status", "final_response", "completed_at", "updated_at"]
        )

    async def run(self, plan, **kwargs):
        from asgiref.sync import sync_to_async

        await sync_to_async(self._sync_run)(kwargs["resume_run_id"])
        return None


@pytest.fixture
def patch_resume_seams(monkeypatch):
    """Patch the lazy engine imports used by the resume path only."""
    monkeypatch.setattr(
        "ai.engine.cognition.plan.loop.ReActLoop", _FakeReActLoop
    )
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
        lambda *a, **k: {"username": "w6e-worker", "display_name": "W6E", "roles": []},
    )
    monkeypatch.setattr("ai.host_executor.CarbonHostExecutor", _FakeHostExecutor)
    return _FakeReActLoop


@pytest.mark.django_db(transaction=True)
def test_paused_steer_resume_reruns_edited_step(user, cleanup, patch_resume_seams):
    """F-28 end-to-end: pause → edit a pending step → resume honors the edit."""
    ids, _ = cleanup
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="pending")
    ids.append(plan.id)

    service = PlansService()
    result = service.edit_step(
        user, plan.id, 1, instructions="Steering: net of offsets."
    )
    assert result["status"] == "paused"
    assert result["replan_gate"] is False

    # Resume through the real service frames path (paused is runnable).
    frames = list(service._run_plan_frames_sync(user, plan.id))
    assert any(f["type"] == "done" for f in frames)

    run = Run.objects.get(id=plan.id)
    assert run.status == "completed"
    steps = {s.step_index: s for s in RunStep.objects.filter(run_id=plan.id)}
    assert steps[0].status == "completed"
    assert steps[1].status == "completed"
    # The edit survived the resume round-trip.
    assert run.plan_json["steps"][1]["instructions"] == "Steering: net of offsets."


# ── F-29: scheduling / triggers ──────────────────────────────────────────


@pytest.mark.django_db
def test_edit_step_paused_pending_step_steers_in_place(user, cleanup):
    ids, _ = cleanup
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="pending")
    ids.append(plan.id)

    service = PlansService()
    result = service.edit_step(
        user, plan.id, 1,
        instructions="Use the 2026 baseline and ignore one-off outliers.",
    )

    # Stays paused — no re-approval, no ledger wipe (F-28).
    assert result["status"] == "paused"
    assert result["replan_gate"] is False
    step1 = next(s for s in result["steps"] if s["step_id"] == 1)
    assert step1["instructions"] == "Use the 2026 baseline and ignore one-off outliers."

    # Durable rows: executed step untouched, edited step stays pending.
    run = Run.objects.get(id=plan.id)
    assert run.status == "paused"
    assert run.plan_json["steps"][1]["instructions"] == (
        "Use the 2026 baseline and ignore one-off outliers."
    )
    s0 = RunStep.objects.get(run_id=plan.id, step_index=0)
    s1 = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert s0.status == "completed"
    assert s1.status == "pending"
    # Durable row intent mirrors plan_json (source of truth) — synced, not wiped.
    assert s1.intent == "Compare against the baseline"


@pytest.mark.django_db
def test_edit_step_paused_awaiting_approval_drops_to_review(user, cleanup):
    ids, _ = cleanup
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="awaiting_approval", token="tok-0")
    _make_step(plan, step_index=1, status="pending")
    ids.append(plan.id)

    service = PlansService()
    # Editing the consent-awaiting step itself invalidates the live gate.
    result = service.edit_step(user, plan.id, 0, title="Renamed step")

    # RULE_21: back to review — the pending consent token must not survive.
    assert result["status"] == "pending_approval"
    assert result["replan_gate"] is True
    steps = list(RunStep.objects.filter(run_id=plan.id).order_by("step_index"))
    assert all(s.status == "pending" for s in steps)
    assert all(s.confirmation_token is None for s in steps)


@pytest.mark.django_db
def test_edit_step_paused_other_awaiting_approval_steers_in_place(user, cleanup):
    """A live consent gate on ANOTHER step does not block steering a pending one."""
    ids, _ = cleanup
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="awaiting_approval", token="tok-0")
    _make_step(plan, step_index=1, status="pending")
    ids.append(plan.id)

    service = PlansService()
    result = service.edit_step(
        user, plan.id, 1, instructions="Steer the pending step only."
    )

    assert result["status"] == "paused"
    assert result["replan_gate"] is False
    # The consent gate is untouched.
    s0 = RunStep.objects.get(run_id=plan.id, step_index=0)
    assert s0.status == "awaiting_approval"
    assert s0.confirmation_token == "tok-0"


@pytest.mark.django_db
def test_edit_step_paused_executed_step_drops_to_review(user, cleanup):
    ids, _ = cleanup
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="pending")
    ids.append(plan.id)

    service = PlansService()
    result = service.edit_step(user, plan.id, 0, title="Retitle executed step")

    # Editing an executed step invalidates prior work — review gate.
    assert result["status"] == "pending_approval"
    assert result["replan_gate"] is True


@pytest.mark.django_db
def test_edit_step_instructions_flow_into_rebuild_and_prompt(user, cleanup):
    ids, _ = cleanup
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="pending")
    ids.append(plan.id)

    service = PlansService()
    service.edit_step(
        user, plan.id, 1, instructions="Steering: compute net of offsets."
    )
    run = Run.objects.get(id=plan.id)

    # _rebuild_plan carries the steering metadata into the engine PlanStep.
    rebuilt = PlansService._rebuild_plan(run)
    assert rebuilt.steps[1].instructions == "Steering: compute net of offsets."
    assert rebuilt.steps[0].instructions is None

    # The step prompt feeds the instructions to the agent (honored on resume).
    from ai.engine.cognition.plan.loop import ReActLoop

    loop = ReActLoop.__new__(ReActLoop)
    prompt = loop._build_step_prompt(
        rebuilt.steps[1], run.user_message, "sys", {}
    )
    assert "Step instructions: Steering: compute net of offsets." in prompt
    prompt0 = loop._build_step_prompt(
        rebuilt.steps[0], run.user_message, "sys", {}
    )
    assert "Step instructions:" not in prompt0


# ── F-29: scheduling / triggers ──────────────────────────────────────────


@pytest.mark.django_db
def test_due_schedule_materializes_pending_approval_run(user, cleanup):
    ids, schedule_ids = cleanup
    service = PlansService()
    schedule = service.create_schedule(
        user, "Nightly emissions digest",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=timezone.now() - timedelta(minutes=5),
    )
    schedule_ids.append(schedule["id"])

    result = service.materialize_due_schedules()
    assert result["dry_run"] is False
    assert result["materialized"] == 1
    run_id = result["runs"][0]["run_id"]
    ids.append(run_id)

    run = Run.objects.get(id=run_id)
    assert run.status == "pending_approval"  # RULE_21 — review before run
    assert run.host_user_id == str(user.pk)
    assert len(run.plan_json["steps"]) == 2
    assert run.working_notes["schedule_id"] == schedule["id"]
    steps = list(RunStep.objects.filter(run_id=run_id).order_by("step_index"))
    assert len(steps) == 2
    assert all(s.status == "pending" for s in steps)
    assert steps[1].depends_on_json == [0]

    # One-off schedule fired: disabled, no next fire.
    sched = RunSchedule.objects.get(id=schedule["id"])
    assert sched.last_run_at is not None
    assert sched.enabled is False
    assert sched.next_run_at is None

    # Idempotent — a second invocation materializes nothing new.
    result2 = service.materialize_due_schedules()
    assert result2["materialized"] == 0
    assert Run.objects.filter(id=run_id).count() == 1


@pytest.mark.django_db
def test_future_schedule_not_materialized(user, cleanup):
    _, schedule_ids = cleanup
    service = PlansService()
    schedule = service.create_schedule(
        user, "Tomorrow",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=timezone.now() + timedelta(days=1),
    )
    schedule_ids.append(schedule["id"])

    result = service.materialize_due_schedules()
    assert result["materialized"] == 0
    # No run references this schedule (provenance-scoped — transaction=True
    # tests may leave unrelated committed rows behind).
    assert not Run.objects.filter(
        working_notes__schedule_id=schedule["id"]
    ).exists()
    assert RunSchedule.objects.get(id=schedule["id"]).enabled is True


@pytest.mark.django_db
def test_dry_run_creates_nothing(user, cleanup):
    ids, schedule_ids = cleanup
    service = PlansService()
    schedule = service.create_schedule(
        user, "Dry run me",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=timezone.now() - timedelta(minutes=1),
    )
    schedule_ids.append(schedule["id"])

    result = service.materialize_due_schedules(dry_run=True)
    assert result["dry_run"] is True
    assert result["materialized"] == 1
    assert result["runs"][0]["run_id"] is None
    # Nothing materialized for THIS schedule (transaction=True tests may
    # leave unrelated committed Run rows behind).
    assert not Run.objects.filter(
        working_notes__schedule_id=schedule["id"]
    ).exists()
    sched = RunSchedule.objects.get(id=schedule["id"])
    assert sched.last_run_at is None  # untouched
    assert sched.enabled is True


@pytest.mark.django_db
def test_cron_schedule_advances_next_run_at(user, cleanup):
    ids, schedule_ids = cleanup
    service = PlansService()
    schedule = service.create_schedule(
        user, "Hourly digest",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        cron_expr="0 * * * *",
    )
    schedule_ids.append(schedule["id"])
    assert schedule["next_run_at"] is not None  # computed eagerly

    # Not yet due → nothing materialized.
    assert service.materialize_due_schedules()["materialized"] == 0

    # Force due and fire.
    RunSchedule.objects.filter(id=schedule["id"]).update(
        next_run_at=timezone.now() - timedelta(minutes=1)
    )
    result = service.materialize_due_schedules()
    assert result["materialized"] == 1
    ids.append(result["runs"][0]["run_id"])

    # Cron schedules stay enabled and advance to the next occurrence.
    sched = RunSchedule.objects.get(id=schedule["id"])
    assert sched.enabled is True
    assert sched.next_run_at is not None
    assert sched.next_run_at > timezone.now()


@pytest.mark.django_db
def test_template_based_schedule_materializes_template_plan(user, cleanup):
    ids, schedule_ids = cleanup
    tpl = PlanTemplate.objects.create(
        name="Emissions review pack",
        host_user_id=str(user.pk),
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
    )
    service = PlansService()
    schedule = service.create_schedule(
        user, "From template", template_id=tpl.id, cron_expr="*/30 * * * *"
    )
    schedule_ids.append(schedule["id"])
    assert schedule["template_id"] == tpl.id

    RunSchedule.objects.filter(id=schedule["id"]).update(
        next_run_at=timezone.now() - timedelta(seconds=30)
    )
    result = service.materialize_due_schedules()
    assert result["materialized"] == 1
    run = Run.objects.get(id=result["runs"][0]["run_id"])
    ids.append(run.id)
    assert len(run.plan_json["steps"]) == 2


@pytest.mark.django_db
def test_schedule_owner_scoping_and_template_check(user, other_user, cleanup):
    ids, schedule_ids = cleanup
    service = PlansService()
    tpl = PlanTemplate.objects.create(
        name="Owner's pack",
        host_user_id=str(user.pk),
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
    )

    # Using another user's template → rejected (CBAC).
    with pytest.raises(PlanNotAccessibleError):
        service.create_schedule(
            other_user, "Sneak", template_id=tpl.id, cron_expr="0 * * * *"
        )

    # list/delete are owner-scoped.
    schedule = service.create_schedule(
        user, "Owner schedule",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=timezone.now() - timedelta(minutes=2),
    )
    schedule_ids.append(schedule["id"])
    assert service.list_schedules(user)["count"] == 1
    assert service.list_schedules(other_user)["count"] == 0
    with pytest.raises(PlanNotAccessibleError):
        service.delete_schedule(other_user, schedule["id"])
    assert RunSchedule.objects.filter(id=schedule["id"]).exists()

    # Materialized run carries the SCHEDULE owner, not the caller.
    result = service.materialize_due_schedules()
    run = Run.objects.get(id=result["runs"][0]["run_id"])
    ids.append(run.id)
    assert run.host_user_id == str(user.pk)
    assert run.host_user_id != str(other_user.pk)


@pytest.mark.django_db
def test_create_schedule_validates_inputs(user, cleanup):
    _, schedule_ids = cleanup
    service = PlansService()
    with pytest.raises(ValueError):
        service.create_schedule(user, "", plan_json={})  # no name
    with pytest.raises(ValueError):
        service.create_schedule(user, "X", plan_json={})  # no trigger
    with pytest.raises(ValueError):
        service.create_schedule(
            user, "X", plan_json={}, cron_expr="0 * * * *",
            run_at=timezone.now(),  # both triggers
        )
    with pytest.raises(ValueError):
        service.create_schedule(
            user, "X",
            plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
            template_id="nope",  # both sources
            cron_expr="0 * * * *",
        )


# ── W7-A: schedules REST contract (F-29) ─────────────────────────────────


@pytest.mark.django_db
def test_schedule_list_create_edit_pause_delete(user, other_user, cleanup):
    _, schedule_ids = cleanup
    service = PlansService()

    s1 = service.create_schedule(
        user, "Alpha",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=timezone.now() + timedelta(days=2),
    )
    s2 = service.create_schedule(
        user, "Beta",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=timezone.now() + timedelta(days=1),
    )
    schedule_ids += [s1["id"], s2["id"]]

    # List is owner-scoped and soonest-first.
    listed = service.list_schedules(user)
    assert [s["id"] for s in listed["schedules"]] == [s2["id"], s1["id"]]

    # Edit name + description (PATCH semantics — only supplied fields change).
    edited = service.edit_schedule(
        user, s1["id"], name="Alpha edited", description="Nightly"
    )
    assert edited["name"] == "Alpha edited"
    assert edited["description"] == "Nightly"
    assert edited["run_at"] == s1["run_at"]  # untouched
    # F-29: owner resolves to a display name (design-doc acceptance), never
    # a raw host_user_id.
    assert edited["owner"] == "w6e-worker"

    # Switching to a recurring trigger recomputes next_run_at.
    edited2 = service.edit_schedule(user, s1["id"], cron_expr="0 9 * * *")
    assert edited2["cron_expr"] == "0 9 * * *"
    assert edited2["run_at"] is None
    assert edited2["next_run_at"] is not None
    assert edited2["preview"] == "Every day at 9:00 AM"

    # Pause toggles enabled (does not delete).
    paused = service.pause_schedule(user, s1["id"])
    assert paused["enabled"] is False
    resumed = service.pause_schedule(user, s1["id"])
    assert resumed["enabled"] is True

    # Owner scoping on edit/pause.
    with pytest.raises(PlanNotAccessibleError):
        service.edit_schedule(other_user, s1["id"], name="hack")
    with pytest.raises(PlanNotAccessibleError):
        service.pause_schedule(other_user, s1["id"])

    # Delete removes the row (owner-scoped).
    service.delete_schedule(user, s1["id"])
    assert not RunSchedule.objects.filter(id=s1["id"]).exists()
    assert service.list_schedules(user)["count"] == 1


@pytest.mark.django_db
def test_schedule_preview_one_off_and_recurring(user, cleanup):
    """F-29: server-side ``preview`` is plain-language outcome copy."""
    _, schedule_ids = cleanup
    service = PlansService()

    oneoff = service.create_schedule(
        user, "One-off",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        # 14:00 Cairo (the platform's admin-configured display timezone).
        run_at=datetime(2026, 8, 25, 14, 0, tzinfo=ZoneInfo("Africa/Cairo")),
    )
    schedule_ids.append(oneoff["id"])
    assert oneoff["preview"] == "Once on 2026-08-25 at 2:00 PM"

    daily = service.create_schedule(
        user, "Daily",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        cron_expr="0 9 * * *",
    )
    schedule_ids.append(daily["id"])
    assert daily["preview"] == "Every day at 9:00 AM"

    weekly = service.create_schedule(
        user, "Weekly",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        cron_expr="0 9 * * 1",
    )
    schedule_ids.append(weekly["id"])
    assert weekly["preview"] == "Every Monday at 9:00 AM"

    monthly = service.create_schedule(
        user, "Monthly",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        cron_expr="0 9 1 * *",
    )
    schedule_ids.append(monthly["id"])
    assert monthly["preview"] == "Every 1st of the month at 9:00 AM"

    # Raw cron stays available for power users (data, not user-facing text).
    assert monthly["cron_expr"] == "0 9 1 * *"


@pytest.mark.django_db
def test_schedule_preview_respects_admin_timezone(user, cleanup):
    """F-29: the preview renders in the admin-configurable display timezone.

    ``accounts.GeneralConfig.timezone`` (default ``Africa/Cairo``) drives the
    human-facing one-off preview; storage stays UTC.
    """
    from accounts.models import GeneralConfig

    _, schedule_ids = cleanup
    service = PlansService()

    cfg = GeneralConfig.load()
    cfg.timezone = "UTC"
    cfg.save()

    run_at = datetime(2026, 8, 25, 14, 0, tzinfo=ZoneInfo("UTC"))
    s_utc = service.create_schedule(
        user, "UTC-sched",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=run_at,
    )
    schedule_ids.append(s_utc["id"])
    assert s_utc["preview"] == "Once on 2026-08-25 at 2:00 PM"

    cfg.timezone = "Africa/Cairo"
    cfg.save()
    s_cairo = service.create_schedule(
        user, "Cairo-sched",
        plan_json=json.loads(json.dumps(_PLAN_JSON_2)),
        run_at=run_at,
    )
    schedule_ids.append(s_cairo["id"])
    # 14:00 UTC == 17:00 Africa/Cairo (UTC+3 — Egypt DST is active in August).
    assert s_cairo["preview"] == "Once on 2026-08-25 at 5:00 PM"


# ── W7-A: schedules REST contract (F-29) — HTTP surface ─────────────────


@pytest.mark.django_db
def test_schedule_rest_routes_lifecycle(api_client, get_token_for_user, user, cleanup):
    """F-29: the schedules REST surface the frontend composes against works
    end-to-end — list/create/edit/pause/delete over HTTP (owner-scoped)."""
    _, schedule_ids = cleanup
    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # POST /schedules/ — create (cron trigger, preview present server-side).
    resp = api_client.post(
        "/carbon-api/ai/plans/schedules/",
        {
            "name": "Nightly digest",
            "plan_json": json.loads(json.dumps(_PLAN_JSON_2)),
            "cron_expr": "0 9 * * *",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    created = resp.json()
    schedule_ids.append(created["id"])
    assert created["preview"] == "Every day at 9:00 AM"
    assert created["enabled"] is True

    # GET /schedules/ — list is owner-scoped and returns the created row.
    listed = api_client.get("/carbon-api/ai/plans/schedules/")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["schedules"][0]["id"] == created["id"]

    # PATCH /schedules/{id}/ — edit name, recompute preview/next_run_at.
    resp = api_client.patch(
        f"/carbon-api/ai/plans/schedules/{created['id']}/",
        {"name": "Renamed digest", "cron_expr": "0 9 * * 1"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["name"] == "Renamed digest"
    assert resp.json()["preview"] == "Every Monday at 9:00 AM"
    assert resp.json()["next_run_at"] is not None

    # POST /schedules/{id}/pause/ — toggle enabled (does not delete).
    resp = api_client.post(
        f"/carbon-api/ai/plans/schedules/{created['id']}/pause/"
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # DELETE /schedules/{id}/ — remove the row.
    resp = api_client.delete(
        f"/carbon-api/ai/plans/schedules/{created['id']}/"
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert api_client.get("/carbon-api/ai/plans/schedules/").json()["count"] == 0


@pytest.mark.django_db
def test_schedule_rest_requires_auth(api_client):
    """F-29: the schedules routes reject anonymous callers."""
    assert api_client.get("/carbon-api/ai/plans/schedules/").status_code == 401
    assert api_client.post("/carbon-api/ai/plans/schedules/", {}, format="json").status_code == 401
