"""PEC-2A — Prove learning-reuse on a realistic HRMS fixture arc.

Full arc (fixture-based, no live LLM):

  1. Draft an HRMS procedure skill (payroll variance check).
  2. Gate-only admit/promote → ``instance_promoted`` + ``SkillAdmissionLog``.
  3. ``SkillAwarePlanner.decompose`` matches a later HRMS utterance
     → ``source="skill"`` plan citing the skill.
  4. Terminal skill-sourced plan run → ``feed_run_feedback`` bumps
     ``usage_count`` 0→1 and writes an ``AuditLog`` row
     (``action=ai.skill_reused``) citing the skill.

Evidence companion: ``docs/pulse/evidence/PEC-2A-reuse.md``.
"""
from __future__ import annotations

import asyncio
import uuid
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.feedback.skill_flywheel import feed_run_feedback
from ai.models.core import AuditLog, Run, RunStep, Skill, SkillAdmissionLog
from ai.store import reset_store

# HRMS-realistic fixture — name tokens appear in the later utterance so
# ``_score_skill`` clears the 0.5 match threshold without an LLM.
SKILL_NAME = "payroll_run_variance_check"
SKILL_DESCRIPTION = (
    "Check unresolved variance on a Nibras payroll run before commit."
)
HRMS_UTTERANCE = (
    "Please run payroll_run_variance_check for payroll run 12 — "
    "flag any unresolved variance before we commit."
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(
        username=f"pec2a-reuse-{uuid4().hex[:8]}", password="secret123"
    )


# ── Helpers ───────────────────────────────────────────────────────────────


async def _seed_draft_hrms_skill(instance_name: str) -> tuple[str, str]:
    """Seed an active instance + one pending HRMS draft Skill.

    Returns ``(instance_id, skill_id)``.
    """
    from ai.engine.core.models import Instance, Skill as EngineSkill, generate_uuid
    from ai.store import get_store

    instance_id = generate_uuid()
    skill_id = generate_uuid()
    factory = get_store().get_session_factory()
    async with factory() as db:
        db.add(
            Instance(
                id=instance_id,
                name=instance_name,
                display_name=instance_name,
                host_db_url="postgres://db",
                host_api_url="https://host",
                status="active",
            )
        )
        db.add(
            EngineSkill(
                id=skill_id,
                instance_id=instance_id,
                name=SKILL_NAME,
                description=SKILL_DESCRIPTION,
                signature="{}",
                body='{"steps":[{"intent":"Inspect payroll run variance","tool_name":null}]}',
                kind="procedure",
                status="draft",
                author_user_id="system",
                gate_status="pending",
            )
        )
        await db.commit()
    return instance_id, skill_id


def _run_admission(instance_id: str) -> dict:
    from ai.engine.skills.gate import run_skill_admission
    from ai.store import get_store

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await run_skill_admission(db, instance_id)

    return asyncio.run(_go())


def _decompose(instance_id: str, utterance: str):
    from ai.engine.cognition.plan.planner import SkillAwarePlanner
    from ai.engine.skills.registry import SkillRegistry
    from ai.store import get_store

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await SkillAwarePlanner().decompose(
                utterance=utterance,
                skill_registry=SkillRegistry(db),
                instance_id=instance_id,
                user_id="payroll-clerk-1",
            )

    return asyncio.run(_go())


def _make_terminal_skill_run(user, *, skill_name: str, instance_id: str) -> Run:
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id=instance_id,
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message=HRMS_UTTERANCE,
        status="completed",
        total_latency_ms=420.0,
        plan_json={
            "pattern": "custom",
            "source": "skill",
            "skill_name": skill_name,
            "synthesis_instruction": "Present the variance check result.",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Inspect payroll run variance",
                    "tool_name": "invoke_skill",
                    "tool_args": {"skill_name": skill_name},
                    "depends_on": [],
                }
            ],
        },
    )


# ── Integration: draft → admit → plan match → counter + ledger ───────────


@pytest.mark.django_db(transaction=True)
def test_pec2a_hrms_learning_reuse_arc(django_store, cfg, user, monkeypatch):
    """End-to-end PEC-2A proof: promoted HRMS skill reused with counter + ledger."""
    # Marginal-gain critic needs evals.stream (absent) — disable for fixture gate.
    monkeypatch.setenv("SKILL_GATE_MARGINAL_GAIN_ENABLED", "false")
    get_settings.cache_clear()

    instance_id, skill_id = asyncio.run(
        _seed_draft_hrms_skill(f"pec2a-hrms-{uuid4().hex[:8]}")
    )

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.usage_count == 0
    usage_before = skill.usage_count

    # ── 1. Admit / promote (gate-only) ────────────────────────────────────
    summary = _run_admission(instance_id)
    assert summary == {"evaluated": 1, "promoted": 1, "rejected": 0}

    skill.refresh_from_db()
    assert skill.status == "instance_promoted"
    assert skill.gate_status == "admitted"

    admission_logs = list(SkillAdmissionLog.objects.filter(skill_id=skill_id))
    assert len(admission_logs) == 1
    assert admission_logs[0].verdict == "admitted"

    # ── 2. Later plan matches the promoted skill ──────────────────────────
    plan = _decompose(instance_id, HRMS_UTTERANCE)
    assert plan.source == "skill"
    assert plan.skill_name == SKILL_NAME
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "invoke_skill"
    assert plan.steps[0].tool_args["skill_name"] == SKILL_NAME

    # ── 3. Terminal skill-sourced run → flywheel counter + AuditLog ───────
    run = _make_terminal_skill_run(
        user, skill_name=SKILL_NAME, instance_id=instance_id
    )
    RunStep.objects.create(
        run_id=run.id,
        step_index=0,
        intent="Inspect payroll run variance",
        tool_name="invoke_skill",
        tool_args_json={"skill_name": SKILL_NAME},
        depends_on_json=[],
        status="completed",
        critic_verdict="pass",
        critic_flags_json=[],
    )

    result = feed_run_feedback(str(run.id), instance_id=instance_id)
    assert result is not None
    assert result["skill_id"] == skill_id
    assert result["skill_name"] == SKILL_NAME
    assert result["success"] is True
    assert result["updated"] is True

    skill.refresh_from_db()
    usage_after = skill.usage_count
    assert usage_before == 0
    assert usage_after == usage_before + 1
    assert skill.success_rate == 1.0
    assert skill.last_executed_at is not None
    # RULE_21 — flywheel never mutates promotion status
    assert skill.status == "instance_promoted"

    ledger = list(
        AuditLog.objects.filter(action="ai.skill_reused", target=skill_id)
    )
    assert len(ledger) == 1
    detail = ledger[0].detail or {}
    assert detail.get("skill_name") == SKILL_NAME
    assert detail.get("skill_id") == skill_id
    assert detail.get("run_id") == str(run.id)
    assert detail.get("usage_count") == usage_after
