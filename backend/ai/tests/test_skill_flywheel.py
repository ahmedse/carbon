"""
Phase W4-D — Learning flywheel tests.

Covers ``ai/feedback/skill_flywheel.py`` (``feed_run_feedback`` +
``promote_on_success``) and the planner's learnt-signal boost in
``ai/engine/cognition/plan/planner._score_skill``.

Mirrors the seeding pattern of ``test_catalog.py`` (engine store → Django
backend, ``AI_STORE_BACKEND="django"``) and the Run/RunStep helpers of
``test_plans.py``.
"""
from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from django.test import override_settings

from ai.feedback.skill_flywheel import feed_run_feedback, promote_on_success
from ai.models.core import Run, RunStep
from ai.plans_service import PLAN_INSTANCE_ID
from ai.store import reset_store


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _django_store():
    """Run against the real Django-ORM store backend (durable writes)."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="flywheel-user", password="secret123")


def _seed_skill(name: str, *, status: str = "draft", kind: str = "multi_step_plan") -> str:
    """Create one engine Skill row through the Django store seam."""
    from ai.engine.core.database import get_session_factory
    from ai.engine.core.models import Skill

    async def _seed():
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            skill = Skill(
                instance_id=PLAN_INSTANCE_ID,
                name=name,
                description=f"{name} description",
                signature={"type": "object", "properties": {}},
                body={"steps": []},
                kind=kind,
                status=status,
                author_user_id="u-1",
            )
            db.add(skill)
            await db.commit()
            await db.refresh(skill)
            return skill.id

    return asyncio.run(_seed())


def _skill_from_store(skill_id: str):
    """Read one Skill row back through the engine store (Django backend)."""
    from ai.engine.core.database import get_session_factory
    from ai.engine.core.models import Skill

    async def _get():
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            return await db.get(Skill, skill_id)

    return asyncio.run(_get())


def _make_run(
    user,
    *,
    status: str = "completed",
    source: str = "skill",
    skill_name: str | None = "weekly_load_report",
    latency_ms: float = 1234.5,
) -> Run:
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id=PLAN_INSTANCE_ID,
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Summarize the weekly load",
        status=status,
        total_latency_ms=latency_ms,
        plan_json={
            "pattern": "custom",
            "source": source,
            "skill_name": skill_name,
            "synthesis_instruction": "Summarize findings.",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Load the weekly report",
                    "tool_name": "invoke_skill",
                    "tool_args": {"skill_name": skill_name},
                    "depends_on": [],
                }
            ],
        },
    )


def _make_step(run, *, verdict: str = "pass", status: str = "completed", error: str | None = None):
    return RunStep.objects.create(
        run_id=run.id,
        step_index=0,
        intent="Load the weekly report",
        tool_name="invoke_skill",
        tool_args_json={"skill_name": run.plan_json.get("skill_name")},
        depends_on_json=[],
        status=status,
        critic_verdict=verdict,
        critic_flags_json=[] if verdict in ("pass", "pass_with_flag", "veto") else None,
        error=error,
    )


# ── feed_run_feedback: no-op guard ───────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_flywheel_noop_without_skill_source(user):
    """Non-skill plans (or skill plans without skill_name) return None."""
    # source="single_step", no skill_name
    run = _make_run(user, source="single_step", skill_name=None)
    assert feed_run_feedback(str(run.id)) is None

    # source="skill" but missing skill_name
    run2 = _make_run(user, source="skill", skill_name="   ")
    assert feed_run_feedback(str(run2.id)) is None

    # unknown run id
    assert feed_run_feedback(str(uuid.uuid4())) is None


@pytest.mark.django_db(transaction=True)
def test_flywheel_does_not_fire_mid_flight(user):
    """A non-terminal (running) run never feeds the ledger (retry safety)."""
    skill_id = _seed_skill("weekly_load_report")
    run = _make_run(user, status="running")
    assert feed_run_feedback(str(run.id)) is None
    skill = _skill_from_store(skill_id)
    assert skill.usage_count == 0


# ── feed_run_feedback: promote on success ────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_flywheel_promotes_successful_run(user):
    """All-pass completed run → success=True, usage_count==1, rate==1.0."""
    skill_id = _seed_skill("weekly_load_report")
    run = _make_run(user, status="completed")
    _make_step(run, verdict="pass", status="completed")

    result = feed_run_feedback(str(run.id))

    assert result is not None
    assert result["skill_id"] == skill_id
    assert result["skill_name"] == "weekly_load_report"
    assert result["success"] is True
    assert result["vetoed"] == 0
    assert result["latency_ms"] == 1234.5
    assert result["updated"] is True

    skill = _skill_from_store(skill_id)
    assert skill.usage_count == 1
    assert skill.success_rate == 1.0
    assert skill.last_executed_at is not None
    # RULE_21 — status is never mutated by the flywheel
    assert skill.status == "draft"


@pytest.mark.django_db(transaction=True)
def test_flywheel_depresses_vetoed_run(user):
    """A vetoed/failed run → success=False, rate < 1.0, vetoed == 1."""
    skill_id = _seed_skill("weekly_load_report")
    run = _make_run(user, status="failed")
    _make_step(run, verdict="veto", status="completed")

    result = feed_run_feedback(str(run.id))

    assert result is not None
    assert result["success"] is False
    assert result["vetoed"] == 1

    skill = _skill_from_store(skill_id)
    assert skill.usage_count == 1
    assert skill.success_rate == 0.0


@pytest.mark.django_db(transaction=True)
def test_flywheel_depresses_failed_step(user):
    """A step with an error (even in a completed run) counts as failure."""
    skill_id = _seed_skill("weekly_load_report")
    run = _make_run(user, status="completed")
    _make_step(run, verdict="pass", status="completed", error="Tool failed")

    result = feed_run_feedback(str(run.id))

    assert result is not None
    assert result["success"] is False

    skill = _skill_from_store(skill_id)
    assert skill.usage_count == 1
    assert skill.success_rate == 0.0


@pytest.mark.django_db(transaction=True)
def test_flywheel_accumulates_ema_and_usage(user):
    """Two feeds → usage_count==2, rate==1.0, EMA avg latency applied."""
    skill_id = _seed_skill("weekly_load_report")
    run1 = _make_run(user, status="completed", latency_ms=1000.0)
    _make_step(run1, verdict="pass")
    feed_run_feedback(str(run1.id))

    run2 = _make_run(user, status="completed", latency_ms=2000.0)
    _make_step(run2, verdict="pass_with_flag")
    feed_run_feedback(str(run2.id))

    skill = _skill_from_store(skill_id)
    assert skill.usage_count == 2
    assert skill.success_rate == 1.0
    # EMA: first obs sets avg=1000, then 0.7*1000 + 0.3*2000 = 1300
    assert skill.avg_latency_ms == 1300.0


# ── promote_on_success: read-only readiness report ───────────────────────


@pytest.mark.django_db(transaction=True)
def test_promote_on_success_never_mutates(user):
    """Crossing the bar reports True but never writes status (RULE_21)."""
    skill_id = _seed_skill("weekly_load_report")

    # Below the bar → False
    assert promote_on_success(skill_id) is False

    # Three proven successes push usage_count=3, success_rate=1.0
    for _ in range(3):
        run = _make_run(user, status="completed")
        _make_step(run, verdict="pass")
        feed_run_feedback(str(run.id))

    assert promote_on_success(skill_id) is True

    skill = _skill_from_store(skill_id)
    assert skill.usage_count == 3
    assert skill.status == "draft"  # never auto-promoted

    # Already promoted skills are not reported as promote-ready
    skill_id2 = _seed_skill("already_promoted", status="instance_promoted")
    assert promote_on_success(skill_id2, threshold_successes=0) is False


# ── planner _score_skill: learnt-signal boost ────────────────────────────


def _fake_skill(name="weekly_load_report", desc="weekly load report", rate=0.0, usage=0):
    return SimpleNamespace(
        name=name,
        description=desc,
        success_rate=rate,
        usage_count=usage,
    )


def test_score_skill_consumes_learnt_signal():
    """Equal keyword overlap → proven skill outscores cold skill."""
    from ai.engine.cognition.plan.planner import _score_skill

    utterance = "load weekly report"
    proven = _score_skill(
        _fake_skill(rate=1.0, usage=5), utterance
    )
    cold = _score_skill(_fake_skill(rate=0.0, usage=0), utterance)
    assert proven > cold


def test_score_skill_boost_capped_at_099():
    """Direct name match (0.95) + max boost never crosses 0.99."""
    from ai.engine.cognition.plan.planner import _score_skill

    skill = _fake_skill(name="load", desc="load", rate=1.0, usage=10)
    assert _score_skill(skill, "load weekly") <= 0.99


def test_score_skill_zero_usage_unchanged():
    """Zero-usage skills score exactly as before the boost (golden-safe)."""
    from ai.engine.cognition.plan.planner import _score_skill

    a = _fake_skill(name="foo", desc="bar", rate=0.0, usage=0)
    b = _fake_skill(name="foo", desc="bar", rate=0.5, usage=0)  # no usage → no boost
    assert _score_skill(a, "baz qux") == _score_skill(b, "baz qux") == 0.0
