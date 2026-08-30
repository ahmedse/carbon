"""Pulse 0.2 #3 — "Real Learning": prove a promoted skill is actually REUSED.

Covers the hot-path reuse + observable telemetry gap:

  1. ``SkillAwarePlanner.decompose`` routes a promoted NON-plan skill
     (procedure / prompt_template / …) to a single ``invoke_skill`` step with
     ``source="skill"`` — never ``single_step`` (which would skip the ReAct
     loop and never execute the skill).
  2. ``execute_invoke_skill`` records FULL telemetry via
     ``SkillsStore.update_stats`` (usage_count, success_rate, avg_latency_ms,
     last_executed_at) instead of a raw usage_count increment.
  3. A missing skill never increments any counters.
  4. The read-only ops surface ``GET /carbon-api/ai/pulse/skills/`` exposes
     the counters.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store

BASE = "/carbon-api/ai/pulse"
SKILLS_URL = f"{BASE}/skills/"


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def django_store():
    """Run the engine against the Django (PostgreSQL) Store backend."""
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


@pytest.fixture
def cfg():
    """Clear the settings cache around each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def superuser(db):
    from accounts.models import User
    u = User.objects.create_user(username="skill-reuse-admin", password="secret123")
    u.is_superuser = True
    u.is_staff = True
    u.save()
    return u


@pytest.fixture
def regular_user(db):
    from accounts.models import User
    return User.objects.create_user(username="skill-reuse-user", password="secret123")


@pytest.fixture
def admin_client(api_client, get_token_for_user, superuser):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(superuser)}")
    return api_client


@pytest.fixture
def user_client(api_client, get_token_for_user, regular_user):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(regular_user)}")
    return api_client


# ── Seeding helper ───────────────────────────────────────────────────────


async def _seed_promoted_skill(
    instance_name: str,
    *,
    kind: str = "procedure",
    status: str = "instance_promoted",
) -> tuple[str, str, str]:
    """Seed an active instance + one promoted skill via the Store.

    Returns ``(instance_id, skill_id, skill_name)``.
    """
    from ai.engine.core.models import Instance, Skill, generate_uuid
    from ai.store import get_store

    instance_id = generate_uuid()
    skill_id = generate_uuid()
    name = "seeded_procedure"
    factory = get_store().get_session_factory()
    async with factory() as db:
        db.add(Instance(
            id=instance_id,
            name=instance_name,
            display_name=instance_name,
            host_db_url="postgres://db",
            host_api_url="https://host",
            status="active",
        ))
        db.add(Skill(
            id=skill_id,
            instance_id=instance_id,
            name=name,
            description="Seeded promoted skill",
            signature="{}",
            body="{}",
            kind=kind,
            status=status,
            author_user_id="system",
        ))
        await db.commit()

    return instance_id, skill_id, name


class _FakeExecutor:
    """Minimal host executor exposing the AsyncSession + a non-empty token."""

    def __init__(self, db):
        self.db = db
        self.user_token = "test-token"


# ── 1. Planner routes non-plan skill to invoke_skill ─────────────────────


@pytest.mark.django_db(transaction=True)
def test_decompose_routes_promoted_non_plan_skill_to_invoke_skill(django_store, cfg):
    """A promoted procedure skill must produce an invoke_skill plan (source=skill)."""
    from ai.engine.cognition.plan.planner import SkillAwarePlanner
    from ai.engine.skills.registry import SkillRegistry
    from ai.store import get_store

    instance_id, _skill_id, name = asyncio.run(
        _seed_promoted_skill(f"reuse-plan-{uuid4().hex[:8]}", kind="procedure")
    )

    async def _decompose():
        factory = get_store().get_session_factory()
        async with factory() as db:
            registry = SkillRegistry(db)
            planner = SkillAwarePlanner()
            return await planner.decompose(
                utterance=f"use {name} for me",
                skill_registry=registry,
                instance_id=instance_id,
                user_id="user-1",
            )

    plan = asyncio.run(_decompose())

    assert plan.source == "skill"
    assert plan.skill_name == name
    assert len(plan.steps) == 1

    step = plan.steps[0]
    assert step.tool_name == "invoke_skill"
    assert step.tool_args["skill_name"] == name
    assert step.skill_name == name


# ── 2. invoke_skill records full telemetry ───────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_invoke_skill_records_full_telemetry(django_store, cfg):
    """A successful invoke updates usage_count, success_rate, latency, last_executed_at."""
    from ai.engine.agent.tools import execute_invoke_skill
    from ai.models.core import Skill as DjangoSkill
    from ai.store import get_store

    instance_id, skill_id, name = asyncio.run(
        _seed_promoted_skill(f"reuse-telemetry-{uuid4().hex[:8]}", kind="procedure")
    )

    async def _invoke():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await execute_invoke_skill(
                skill_name=name,
                instance_id=instance_id,
                executor=_FakeExecutor(db),
            )

    result = asyncio.run(_invoke())

    assert result["skill_name"] == name
    assert result["skill_id"] == skill_id
    assert "result" in result

    skill = DjangoSkill.objects.get(id=skill_id)
    assert skill.usage_count == 1
    assert skill.success_rate == 1.0
    assert skill.last_executed_at is not None
    assert skill.avg_latency_ms >= 0


# ── 3. Missing skill never increments ────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_invoke_skill_missing_skill_does_not_increment(django_store, cfg):
    """An unknown skill name returns an error and leaves counters untouched."""
    from ai.engine.agent.tools import execute_invoke_skill
    from ai.models.core import Skill as DjangoSkill
    from ai.store import get_store

    instance_id, skill_id, _name = asyncio.run(
        _seed_promoted_skill(f"reuse-missing-{uuid4().hex[:8]}", kind="procedure")
    )

    async def _invoke():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await execute_invoke_skill(
                skill_name="does_not_exist",
                instance_id=instance_id,
                executor=_FakeExecutor(db),
            )

    result = asyncio.run(_invoke())
    assert "error" in result

    skill = DjangoSkill.objects.get(id=skill_id)
    assert skill.usage_count == 0
    assert skill.success_rate == 0.0
    assert skill.last_executed_at is None


# ── 4. Ops surface exposes counters ──────────────────────────────────────


@pytest.mark.django_db
def test_ops_skills_endpoint_returns_counters(admin_client):
    """GET /skills/ returns the seeded skill with its usage counters."""
    from ai.models.core import Skill

    Skill.objects.create(
        instance_id="ops-instance",
        name="reused_skill",
        kind="procedure",
        status="instance_promoted",
        author_user_id="user-1",
        usage_count=7,
        success_rate=0.85,
        avg_latency_ms=12.5,
    )

    resp = admin_client.get(SKILLS_URL)
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    names = [s["name"] for s in data]
    assert "reused_skill" in names

    skill = next(s for s in data if s["name"] == "reused_skill")
    assert skill["kind"] == "procedure"
    assert skill["status"] == "instance_promoted"
    assert skill["usage_count"] == 7
    assert skill["success_rate"] == 0.85
    assert skill["avg_latency_ms"] == 12.5
    assert skill["last_executed_at"] is None
    assert skill["promoted_at"] is None


@pytest.mark.django_db
def test_ops_skills_endpoint_is_get_only(admin_client):
    """POST/PUT/DELETE must be rejected with 405 (read-only surface)."""
    assert admin_client.post(SKILLS_URL, {}, format="json").status_code == 405
    assert admin_client.put(SKILLS_URL, {}, format="json").status_code == 405
    assert admin_client.delete(SKILLS_URL).status_code == 405


@pytest.mark.django_db
def test_ops_skills_requires_auth(api_client):
    """Unauthenticated request must be rejected with 401."""
    assert api_client.get(SKILLS_URL).status_code == 401


@pytest.mark.django_db
def test_ops_skills_requires_admin(user_client):
    """Authenticated non-admin must be rejected with 403."""
    assert user_client.get(SKILLS_URL).status_code == 403
