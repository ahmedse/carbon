"""P4.3 / Pulse 0.2 Phase B1 — skill admission gate activation tests.

Proves the sleep-time promotion arrow is wired and gated:

  * ``run_skill_admission`` promotes a clean pending draft to
    ``instance_promoted`` when every *active* critic passes.  The
    marginal-gain critic is disabled via config for this test because the
    ``evals.stream`` infra it needs does not exist in the repo.
  * A draft whose ``sql_macro`` body carries a dangerous SQL pattern is
    rejected by the structural critic (P3-10 — legacy executable-body kinds
    are refused at admission), left pending, and logged.
  * ``SKILL_ADMISSION_ENABLED=false`` short-circuits with zero evaluations
    and zero ``SkillAdmissionLog`` rows.
  * Critic errors are fail-closed: an errored or unparseable critic rejects
    the skill (reason ``critic_error``) and leaves it pending.

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
def test_admission_promotes_clean_draft(django_store, cfg, monkeypatch):
    """A clean procedure draft passes the active critics and is promoted.

    The marginal-gain critic is disabled via ``SKILL_GATE_MARGINAL_GAIN_ENABLED``
    because the ``evals.stream`` module it imports does not exist in the repo;
    with fail-closed error handling that would otherwise (correctly) reject the
    draft instead of silently passing.
    """
    from ai.models.core import Skill, SkillAdmissionLog

    monkeypatch.setenv("SKILL_GATE_MARGINAL_GAIN_ENABLED", "false")
    get_settings.cache_clear()

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
    """A sql_macro body with DROP TABLE is rejected structurally (P3-10).

    Legacy executable-body kinds (``sql_macro`` / ``api_call``) are refused at
    the structural critic before harmlessness even runs, so the dangerous SQL
    never reaches the LLM-free rules pass.
    """
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
    assert logs[0].rejected_by == "structural"
    assert "legacy_executable_body_kind" in (logs[0].structural_flags_json or "")


@pytest.mark.django_db(transaction=True)
def test_admission_rejects_on_marginal_gain_error(django_store, cfg):
    """An errored marginal-gain critic fails closed → rejected, stays pending.

    The marginal-gain critic is left ENABLED (the default).  Because the
    ``evals.stream`` module it imports does not exist, it raises; fail-closed
    handling must reject the skill instead of silently promoting it.
    """
    from ai.models.core import Skill, SkillAdmissionLog

    instance_id, skill_id = asyncio.run(
        _seed_instance_with_skill(f"gate-mg-{uuid4().hex[:8]}")
    )

    summary = _run_admission(instance_id)

    assert summary == {"evaluated": 1, "promoted": 0, "rejected": 1}

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.gate_status == "pending"

    logs = list(SkillAdmissionLog.objects.filter(skill_id=skill_id))
    assert len(logs) == 1
    assert logs[0].verdict == "rejected"
    assert logs[0].rejected_by == "marginal_gain"
    assert "critic_error" in (logs[0].marginal_gain_details_json or "")


@pytest.mark.django_db(transaction=True)
def test_admission_rejects_on_harmlessness_llm_error(django_store, cfg, monkeypatch):
    """An LLM exception in the harmlessness critic fails closed → rejected.

    A ``code_snippet`` skill passes structural and the rules-phase harmlessness
    checks, then triggers the LLM phase.  With ``route_chat`` raising, the
    critic must reject (reason ``critic_error``) and leave the skill pending.
    """
    from unittest.mock import AsyncMock

    from ai.models.core import Skill, SkillAdmissionLog

    monkeypatch.setattr(
        "ai.engine.llm.router.route_chat",
        AsyncMock(side_effect=RuntimeError("LLM key removed")),
    )

    instance_id, skill_id = asyncio.run(
        _seed_instance_with_skill(
            f"gate-llm-{uuid4().hex[:8]}",
            kind="code_snippet",
            body=json.dumps({"code": "print('hello')"}),
        )
    )

    summary = _run_admission(instance_id)

    assert summary == {"evaluated": 1, "promoted": 0, "rejected": 1}

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.gate_status == "pending"

    logs = list(SkillAdmissionLog.objects.filter(skill_id=skill_id))
    assert len(logs) == 1
    assert logs[0].verdict == "rejected"
    assert logs[0].rejected_by == "harmlessness"
    assert "critic_error" in (logs[0].harmlessness_flags_json or "")


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


@pytest.mark.django_db(transaction=True)
def test_skill_gate_status_defaults_to_pending(django_store, cfg):
    """P1-05: Skill.gate_status defaults to 'pending' (Django model default)."""
    from ai.models.core import Skill

    skill = Skill.objects.create(
        instance_id=f"inst-{uuid4().hex[:8]}",
        name=f"default-pending-{uuid4().hex[:8]}",
        kind="procedure",
        author_user_id="system",
    )

    assert skill.gate_status == "pending"
    # Fresh read proves the value was persisted as 'pending', not left NULL.
    assert Skill.objects.get(id=skill.id).gate_status == "pending"


@pytest.mark.django_db(transaction=True)
def test_sweep_picks_up_default_pending_skill(django_store, cfg, monkeypatch):
    """P1-05: a Skill created without gate_status (default 'pending') is swept.

    Proves the default→sweep arrow: a row that never set gate_status is
    persisted as 'pending' and the admission sweep picks it up and promotes it.
    """
    from ai.models.core import Instance, Skill

    monkeypatch.setenv("SKILL_GATE_MARGINAL_GAIN_ENABLED", "false")
    get_settings.cache_clear()

    instance_id = f"inst-{uuid4().hex[:8]}"
    Instance.objects.create(
        id=instance_id,
        name=f"instance-{uuid4().hex[:8]}",
        display_name="sweep-instance",
        host_db_url="postgres://db",
        host_api_url="https://host",
        status="active",
    )
    skill = Skill.objects.create(
        instance_id=instance_id,
        name=f"sweep-default-{uuid4().hex[:8]}",
        kind="procedure",
        author_user_id="system",
    )
    assert skill.gate_status == "pending"  # default applied, not explicit

    summary = _run_admission(instance_id)

    assert summary == {"evaluated": 1, "promoted": 1, "rejected": 0}

    skill = Skill.objects.get(id=skill.id)
    assert skill.status == "instance_promoted"
    assert skill.gate_status == "admitted"
