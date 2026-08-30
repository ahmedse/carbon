"""P4.3 / Pulse 0.2 Phase B1 — skill admission gate activation tests.

Proves the sleep-time promotion arrow is wired and gated:

  * ``run_skill_admission`` promotes a clean pending draft to
    ``instance_promoted`` (all four critics pass with zero LLM calls —
    ``marginal_gain_check`` fails-open with ``marginal_gain_error`` because
    the evals infra is absent, which still counts as passed).
  * A draft whose body carries a dangerous SQL pattern is rejected by the
    harmlessness critic (rules phase, no LLM), left pending, and logged.
  * ``SKILL_ADMISSION_ENABLED=false`` short-circuits with zero evaluations
    and zero ``SkillAdmissionLog`` rows.

Every evaluation writes a ``SkillAdmissionLog`` row via ``admit_skill``.
"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


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


# ── Seeding helpers ──────────────────────────────────────────────────────


async def _seed_instance_with_skill(
    instance_name: str,
    *,
    kind: str = "procedure",
    signature: str = "{}",
    body: str = "{}",
) -> tuple[str, str]:
    """Seed an active instance + one pending draft Skill.

    Written via the Store so rows commit on the same connection the engine
    reads from.  Returns ``(instance_id, skill_id)``.
    """
    from ai.engine.core.models import Instance, Skill, generate_uuid
    from ai.store import get_store

    instance_id = generate_uuid()
    skill_id = generate_uuid()
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
            name="seeded_skill",
            description="Seeded pending draft",
            signature=signature,
            body=body,
            kind=kind,
            status="draft",
            author_user_id="system",
            gate_status="pending",
        ))
        await db.commit()

    return instance_id, skill_id


def _run_admission(instance_id: str) -> dict:
    """Run the skill admission gate for an instance inside a fresh session."""
    from ai.engine.skills.gate import run_skill_admission
    from ai.store import get_store

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await run_skill_admission(db, instance_id)

    return asyncio.run(_go())


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_admission_promotes_clean_draft(django_store, cfg):
    """A clean procedure draft passes all critics (zero LLM) and is promoted."""
    from ai.models.core import Skill, SkillAdmissionLog

    instance_id, skill_id = asyncio.run(
        _seed_instance_with_skill(f"gate-on-{uuid4().hex[:8]}")
    )

    summary = _run_admission(instance_id)

    assert summary == {"evaluated": 1, "promoted": 1, "rejected": 0}

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "instance_promoted"
    assert skill.gate_status == "admitted"
    assert skill.promoted_by == "system:gate"
    assert skill.promoted_at is not None

    logs = list(SkillAdmissionLog.objects.filter(skill_id=skill_id))
    assert len(logs) == 1
    assert logs[0].verdict == "admitted"
    assert logs[0].rejected_by is None
    assert logs[0].admitted_by == "system:gate"


@pytest.mark.django_db(transaction=True)
def test_admission_rejects_dangerous_sql(django_store, cfg):
    """A sql_macro body with DROP TABLE is rejected by harmlessness (rules)."""
    from ai.models.core import Skill, SkillAdmissionLog

    instance_id, skill_id = asyncio.run(
        _seed_instance_with_skill(
            f"gate-reject-{uuid4().hex[:8]}",
            kind="sql_macro",
            body=json.dumps({"sql": "DROP TABLE foo"}),
        )
    )

    summary = _run_admission(instance_id)

    assert summary == {"evaluated": 1, "promoted": 0, "rejected": 1}

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.gate_status == "pending"
    assert skill.promoted_at is None

    logs = list(SkillAdmissionLog.objects.filter(skill_id=skill_id))
    assert len(logs) == 1
    assert logs[0].verdict == "rejected"
    assert logs[0].rejected_by == "harmlessness"


@pytest.mark.django_db(transaction=True)
def test_admission_disabled_short_circuits(django_store, cfg, monkeypatch):
    """SKILL_ADMISSION_ENABLED=false → zero evaluations, zero log rows."""
    from ai.models.core import SkillAdmissionLog

    monkeypatch.setenv("SKILL_ADMISSION_ENABLED", "false")
    get_settings.cache_clear()

    instance_id, _skill_id = asyncio.run(
        _seed_instance_with_skill(f"gate-off-{uuid4().hex[:8]}")
    )

    summary = _run_admission(instance_id)

    assert summary == {"evaluated": 0, "promoted": 0, "rejected": 0}
    assert SkillAdmissionLog.objects.count() == 0
