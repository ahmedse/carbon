"""
Durable execution tests (Phase W3-E) — crash-resume / replay / timeline.

Covers:
  - timeline: ordered event log derived from ``Run`` + ``RunStep`` rows +
    ``working_notes`` provenance + audit trail; fail-visible when the run is
    missing or belongs to another user (CBAC).
  - crash-resume: stale ``running`` steps re-queued, ``failed`` steps
    re-queued, completed/skipped preserved, consent steps never
    auto-confirmed (RULE_21); interrupted runs made resumable; the W3-C
    pre-flight (``resume_plan``) is reused — response shape
    ``{status: "resumed", plan_id, plan, ...}``.
  - replay: RULE_21 consent gate (``{"confirm": true}``); steps reset to
    ``pending`` with ``confirmation_token``/outputs/verdicts cleared while
    ``step_index`` order and ``depends_on`` are preserved; run marked
    ``replaying``; STAGING ONLY — no engine call, nothing executes.
  - REST API: 401 without auth, CBAC 404 on other users' runs, consent gate
    → 400.

Reuses the W3-A/W3-C fixtures (``_make_plan``, ``_make_step``, ``user``,
``other_user``, ``run_ids_cleanup``, ``api_client``, ``get_token_for_user``).
"""

from __future__ import annotations

import uuid

import pytest
from django.utils import timezone

from accounts.models import User
from ai.durable_service import DurableExecutionService, PlanConsentError
from ai.models.core import Run, RunStep
from ai.plans_service import (
    PlanNotAccessibleError,
    PlanNotRunnableError,
)

from ai.tests.test_plans import _make_plan, _make_step


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(username="durable-worker", password="secret123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="durable-other", password="secret123")


@pytest.fixture
def run_ids_cleanup():
    ids: list[str] = []
    yield ids
    RunStep.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()


def _kinds(timeline: dict) -> list[str]:
    return [e["kind"] for e in timeline["events"]]


def _timestamps(timeline: dict) -> list:
    return [e["t"] for e in timeline["events"]]


# ── Timeline ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_timeline_returns_ordered_events(user, run_ids_cleanup):
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed", tool_output={"ok": True})
    _make_step(plan, step_index=1)
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    timeline = service.timeline(user, plan.id)

    assert timeline["run_id"] == plan.id
    assert timeline["status"] == "paused"

    kinds = _kinds(timeline)
    assert kinds[0] == "plan_created"
    assert "step_pending" in kinds
    assert "step_completed" in kinds
    assert "plan_paused" in kinds

    # Sorted ascending by timestamp (stable — ties keep derivation order).
    stamps = _timestamps(timeline)
    assert stamps == sorted(stamps)

    created = next(e for e in timeline["events"] if e["kind"] == "plan_created")
    assert created["detail"]["brief"] == plan.user_message
    completed = next(
        e for e in timeline["events"] if e["kind"] == "step_completed"
    )
    assert completed["step_id"] == 0
    assert completed["detail"]["verdict"] == "pass"


@pytest.mark.django_db
def test_timeline_fail_visible_when_run_missing(user, run_ids_cleanup):
    service = DurableExecutionService()
    with pytest.raises(PlanNotAccessibleError):
        service.timeline(user, str(uuid.uuid4()))


@pytest.mark.django_db
def test_timeline_rejects_other_users_run(user, other_user, run_ids_cleanup):
    plan = _make_plan(other_user, status="completed")
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    with pytest.raises(PlanNotAccessibleError):
        service.timeline(user, plan.id)


@pytest.mark.django_db
def test_timeline_includes_fork_and_replay_provenance(user, run_ids_cleanup):
    plan = _make_plan(user, status="replaying")
    _make_step(plan, step_index=0)
    run = Run.objects.get(id=plan.id)
    run.working_notes = {
        "forked_from": "parent-123",
        "replay": {"of": "completed", "at": "2026-08-20T10:00:00+02:00"},
    }
    run.save(update_fields=["working_notes", "updated_at"])
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    timeline = service.timeline(user, plan.id)

    kinds = _kinds(timeline)
    assert "plan_forked" in kinds
    assert "plan_replayed" in kinds
    assert "plan_replaying" in kinds
    forked = next(e for e in timeline["events"] if e["kind"] == "plan_forked")
    assert forked["detail"]["from_plan_id"] == "parent-123"
    replayed = next(e for e in timeline["events"] if e["kind"] == "plan_replayed")
    assert replayed["detail"]["of"] == "completed"


@pytest.mark.django_db
def test_timeline_merges_audit_trail(user, run_ids_cleanup):
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    run = Run.objects.get(id=plan.id)
    run.working_notes = {
        "audit": [
            {
                "t": timezone.now().isoformat(),
                "kind": "run_resumed",
                "detail": {"crash_recovery": True, "re_queued_steps": [1]},
            }
        ]
    }
    run.save(update_fields=["working_notes", "updated_at"])
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    timeline = service.timeline(user, plan.id)

    kinds = _kinds(timeline)
    assert "run_resumed" in kinds
    resumed = next(e for e in timeline["events"] if e["kind"] == "run_resumed")
    assert resumed["detail"]["crash_recovery"] is True


# ── Crash-safe resume ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_resume_reconciles_interrupted_running_steps(user, run_ids_cleanup):
    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="running")  # stale — server died
    _make_step(plan, step_index=2)
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    result = service.resume_run(user, plan.id)

    # W3-C pre-flight reused — response status is the product term.
    assert result["status"] == "resumed"
    assert result["plan_id"] == plan.id
    assert result["crash_recovery"] is True
    assert result["reconciled_steps"]["re_queued"] == [1]
    assert 0 in result["reconciled_steps"]["preserved"]

    # Durable state: stale step re-queued, run armed for re-entry (paused).
    run = Run.objects.get(id=plan.id)
    assert run.status == "paused"
    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "pending"
    assert step.error is None
    assert RunStep.objects.get(run_id=plan.id, step_index=0).status == "completed"

    # Audit trail written + new timeline returned.
    assert "run_resumed" in _kinds(result["timeline"])
    assert (run.working_notes or {}).get("audit")


@pytest.mark.django_db
def test_resume_requeues_failed_keeps_consent_step(user, run_ids_cleanup):
    plan = _make_plan(user, status="paused")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="failed", tool_output=None)
    _make_step(
        plan, step_index=2, status="awaiting_approval", token="tok-2",
        tool_output={"result": '{"execution_id": "exec-2"}'},
    )
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    result = service.resume_run(user, plan.id)

    assert result["status"] == "resumed"
    assert result["crash_recovery"] is False
    assert result["reconciled_steps"]["re_queued"] == [1]

    steps = {
        s.step_index: s for s in RunStep.objects.filter(run_id=plan.id)
    }
    # failed → pending (re-runnable); completed stays done.
    assert steps[0].status == "completed"
    assert steps[1].status == "pending"
    # Consent step untouched — resume never auto-confirms (RULE_21).
    assert steps[2].status == "awaiting_approval"
    assert steps[2].confirmation_token == "tok-2"

    run = Run.objects.get(id=plan.id)
    assert run.status == "paused"


@pytest.mark.django_db
def test_resume_from_approved_preflights(user, run_ids_cleanup):
    plan = _make_plan(user, status="approved")
    _make_step(plan, step_index=0)
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    result = service.resume_run(user, plan.id)

    assert result["status"] == "resumed"
    assert result["crash_recovery"] is False
    assert result["reconciled_steps"]["re_queued"] == []
    assert Run.objects.get(id=plan.id).status == "approved"


@pytest.mark.django_db
def test_resume_rejects_non_resumable_statuses(user, run_ids_cleanup):
    service = DurableExecutionService()
    for status in ("pending_approval", "completed", "failed", "cancelled",
                   "replaying"):
        plan = _make_plan(user, status=status)
        run_ids_cleanup.append(plan.id)
        with pytest.raises(PlanNotRunnableError):
            service.resume_run(user, plan.id)


@pytest.mark.django_db
def test_resume_rejects_other_users_run(user, other_user, run_ids_cleanup):
    plan = _make_plan(other_user, status="paused")
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    with pytest.raises(PlanNotAccessibleError):
        service.resume_run(user, plan.id)


# ── Replay (consent-gated, staging only) ─────────────────────────────────


@pytest.mark.django_db
def test_replay_requires_explicit_consent(user, run_ids_cleanup):
    plan = _make_plan(user, status="completed")
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    with pytest.raises(PlanConsentError):
        service.replay_run(user, plan.id)
    with pytest.raises(PlanConsentError):
        service.replay_run(user, plan.id, confirm=False)


@pytest.mark.django_db
def test_replay_stages_reset_and_marks_replaying(user, run_ids_cleanup):
    plan = _make_plan(user, status="completed")
    _make_step(plan, step_index=0, status="completed", token="tok-0",
               tool_output={"result": "data"})
    _make_step(plan, step_index=1, status="completed", token="tok-1",
               tool_output={"result": "data"})
    run = Run.objects.get(id=plan.id)
    run.final_response = "All steps completed."
    run.completed_at = timezone.now()
    run.save(update_fields=["final_response", "completed_at", "updated_at"])
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    result = service.replay_run(user, plan.id, confirm=True)

    assert result["status"] == "replaying"
    assert result["plan_id"] == plan.id
    assert result["replay"]["staged"] is True
    assert result["replay"]["of"] == "completed"
    assert result["replay"]["re_run_steps"] == [0, 1]
    assert result["replay"]["reset_count"] == 2

    run = Run.objects.get(id=plan.id)
    assert run.status == "replaying"
    assert run.final_response is None
    assert run.completed_at is None
    assert run.working_notes["replay"]["of"] == "completed"
    assert "run_replayed" in _kinds(result["timeline"])

    # Every step reset to pending, consent tokens cleared.
    steps = list(RunStep.objects.filter(run_id=plan.id).order_by("step_index"))
    assert all(s.status == "pending" for s in steps)
    assert all(s.confirmation_token is None for s in steps)
    assert all(s.tool_output_json is None for s in steps)


@pytest.mark.django_db
def test_replay_preserves_step_order_and_depends_on(user, run_ids_cleanup):
    plan = _make_plan(user, status="failed")
    _make_step(plan, step_index=0, status="completed")
    step1 = _make_step(plan, step_index=1, status="failed")
    step1.depends_on_json = [0]
    step1.save(update_fields=["depends_on_json", "updated_at"])
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    result = service.replay_run(user, plan.id, confirm=True)

    assert result["replay"]["re_run_steps"] == [0, 1]

    steps = {
        s.step_index: s for s in RunStep.objects.filter(run_id=plan.id)
    }
    assert list(steps.keys()) == [0, 1]  # step_index order preserved
    assert steps[1].depends_on_json == [0]  # depends_on preserved


@pytest.mark.django_db
def test_replay_rejects_running_run(user, run_ids_cleanup):
    # Never reset a live run underneath the loop (RULE_21 — mutations could
    # double-execute).
    plan = _make_plan(user, status="running")
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    with pytest.raises(PlanNotRunnableError):
        service.replay_run(user, plan.id, confirm=True)


@pytest.mark.django_db
def test_replay_rejects_unexecuted_plans(user, run_ids_cleanup):
    service = DurableExecutionService()
    for status in ("pending_approval", "approved", "replaying"):
        plan = _make_plan(user, status=status)
        run_ids_cleanup.append(plan.id)
        with pytest.raises(PlanNotRunnableError):
            service.replay_run(user, plan.id, confirm=True)


@pytest.mark.django_db
def test_replay_rejects_other_users_run(user, other_user, run_ids_cleanup):
    plan = _make_plan(other_user, status="completed")
    run_ids_cleanup.append(plan.id)

    service = DurableExecutionService()
    with pytest.raises(PlanNotAccessibleError):
        service.replay_run(user, plan.id, confirm=True)


# ── REST API ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_api_requires_auth(api_client):
    assert api_client.get(
        "/carbon-api/ai/runs/whatever/timeline/"
    ).status_code == 401
    assert api_client.post("/carbon-api/ai/runs/whatever/resume/").status_code == 401
    assert api_client.post("/carbon-api/ai/runs/whatever/replay/").status_code == 401


@pytest.mark.django_db
def test_api_timeline(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    plan = _make_plan(user, status="completed")
    _make_step(plan, step_index=0, status="completed")
    run_ids_cleanup.append(plan.id)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.get(f"/carbon-api/ai/runs/{plan.id}/timeline/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["run_id"] == plan.id
    assert body["events"][0]["kind"] == "plan_created"
    assert any(e["kind"] == "step_completed" for e in body["events"])


@pytest.mark.django_db
def test_api_timeline_owner_scoped(
    api_client, get_token_for_user, user, other_user, run_ids_cleanup
):
    plan = _make_plan(other_user, status="completed")
    run_ids_cleanup.append(plan.id)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.get(f"/carbon-api/ai/runs/{plan.id}/timeline/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_api_resume(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    plan = _make_plan(user, status="running")
    _make_step(plan, step_index=0, status="completed")
    _make_step(plan, step_index=1, status="running")
    run_ids_cleanup.append(plan.id)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.post(f"/carbon-api/ai/runs/{plan.id}/resume/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "resumed"
    assert body["crash_recovery"] is True
    assert body["reconciled_steps"]["re_queued"] == [1]
    assert "timeline" in body

    step = RunStep.objects.get(run_id=plan.id, step_index=1)
    assert step.status == "pending"


@pytest.mark.django_db
def test_api_replay_requires_consent_body(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    plan = _make_plan(user, status="completed")
    run_ids_cleanup.append(plan.id)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # No consent body → 400 (RULE_21 gate).
    resp = api_client.post(f"/carbon-api/ai/runs/{plan.id}/replay/")
    assert resp.status_code == 400

    # Explicit false → 400.
    resp = api_client.post(
        f"/carbon-api/ai/runs/{plan.id}/replay/",
        {"confirm": False},
        format="json",
    )
    assert resp.status_code == 400
    assert "confirm" in resp.json()["error"]

    # Nothing was staged.
    assert Run.objects.get(id=plan.id).status == "completed"


@pytest.mark.django_db
def test_api_replay_confirmed_stages_only(
    api_client, get_token_for_user, user, run_ids_cleanup
):
    plan = _make_plan(user, status="completed")
    _make_step(plan, step_index=0, status="completed", token="tok-0")
    _make_step(plan, step_index=1, status="completed", token="tok-1")
    run_ids_cleanup.append(plan.id)

    token = get_token_for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = api_client.post(
        f"/carbon-api/ai/runs/{plan.id}/replay/",
        {"confirm": True},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == "replaying"
    assert body["replay"]["re_run_steps"] == [0, 1]

    # Staged only — no execution started, no engine seams invoked.
    assert Run.objects.get(id=plan.id).status == "replaying"
    steps = list(RunStep.objects.filter(run_id=plan.id))
    assert all(s.status == "pending" for s in steps)
    assert all(s.confirmation_token is None for s in steps)


# ── Run comparison — GET /ai/runs/compare/ (F-W5-RUN-01 gate) ───────────


class CompareRunsTests:
    """Regression gate for ``compare_runs`` / ``RunViewSet.compare``.

    Proves ``GET /carbon-api/ai/runs/compare/?a=<id>&b=<id>`` is routed and
    live: aligned step diff with ``status_changed`` flags, 400 on missing
    params, and CBAC 404 when either run belongs to another user.
    """

    @pytest.mark.django_db
    def test_compare_runs_returns_aligned_diff(
        self, api_client, get_token_for_user, user, run_ids_cleanup
    ):
        # Two runs owned by the same user; step 1 diverges (completed vs failed).
        run_a = _make_plan(user, status="completed")
        _make_step(run_a, step_index=0, status="completed")
        _make_step(run_a, step_index=1, status="completed")
        run_b = _make_plan(user, status="completed")
        _make_step(run_b, step_index=0, status="completed")
        _make_step(run_b, step_index=1, status="failed")
        run_ids_cleanup.extend([run_a.id, run_b.id])

        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        resp = api_client.get(
            f"/carbon-api/ai/runs/compare/?a={run_a.id}&b={run_b.id}"
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()

        assert body["a"]["run_id"] == run_a.id
        assert body["b"]["run_id"] == run_b.id

        # Step 0 aligned — no status_changed flag on the entry.
        aligned = next(e for e in body["step_diff"] if e["step_index"] == 0)
        assert aligned["a_status"] == "completed"
        assert aligned["b_status"] == "completed"
        assert "status_changed" not in aligned

        # Step 1 diverged — status_changed flag present.
        diverged = next(e for e in body["step_diff"] if e["step_index"] == 1)
        assert diverged["a_status"] == "completed"
        assert diverged["b_status"] == "failed"
        assert diverged["status_changed"] is True
        assert body["diverged_steps"] == [diverged]

    @pytest.mark.django_db
    def test_compare_runs_rejects_missing_params(
        self, api_client, get_token_for_user, user
    ):
        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        resp = api_client.get("/carbon-api/ai/runs/compare/")
        assert resp.status_code == 400, resp.content
        assert "?a=<run_id>&b=<run_id>" in resp.json()["error"]

    @pytest.mark.django_db
    def test_compare_runs_cross_user_denied(
        self, api_client, get_token_for_user, user, other_user, run_ids_cleanup
    ):
        # Run b belongs to another user → CBAC 404 (owner scoping).
        run_a = _make_plan(user, status="completed")
        run_b = _make_plan(other_user, status="completed")
        run_ids_cleanup.extend([run_a.id, run_b.id])

        token = get_token_for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        resp = api_client.get(
            f"/carbon-api/ai/runs/compare/?a={run_a.id}&b={run_b.id}"
        )
        assert resp.status_code == 404, resp.content
