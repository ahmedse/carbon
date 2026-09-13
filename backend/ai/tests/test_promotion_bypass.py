"""P1-06 — promotion bypass closure tests.

Proves the promotion arrow has exactly one door (the admission gate):

  * ``SkillsStore._promote_to_instance`` is private and token-guarded — a
    direct call with a forged (or missing) token raises ``RuntimeError``.
  * ``SkillRegistry._update_status`` refuses ``instance_promoted`` and
    enforces the explicit transition table for every other transition.
  * ``gate._promote_skill`` always runs admission — a non-pending skill with a
    dangerous body is still rejected (the old ``gate_status != "pending"``
    short-circuit is gone).
  * ``gate._promote_skill`` promotes a clean draft through the gate.

Nothing here exercises a stub: every assertion hits the real Django Store.
"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from django.test import override_settings

from ai.engine.core.config import get_settings
from ai.store import reset_store


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


async def _seed(
    instance_name: str,
    *,
    status: str = "draft",
    gate_status: str = "pending",
    kind: str = "procedure",
    body: str = "{}",
) -> tuple[str, str]:
    """Seed an active instance + one Skill.  Returns ``(instance_id, skill_id)``."""
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
            description="Seeded skill",
            signature="{}",
            body=body,
            kind=kind,
            status=status,
            author_user_id="system",
            gate_status=gate_status,
        ))
        await db.commit()

    return instance_id, skill_id


def _with_session(coro_fn, *args, **kwargs):
    """Run ``coro_fn(db, *args, **kwargs)`` inside a fresh engine session."""
    from ai.store import get_store

    async def _go():
        factory = get_store().get_session_factory()
        async with factory() as db:
            return await coro_fn(db, *args, **kwargs)

    return asyncio.run(_go())


# ── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_store_promote_to_instance_raises_without_token(django_store, cfg):
    """``SkillsStore._promote_to_instance`` rejects a forged token."""
    from ai.engine.skills.crud import SkillsStore
    from ai.models.core import Skill

    _, skill_id = asyncio.run(_seed(f"bypass-store-{uuid4().hex[:8]}"))

    async def _call(db, skill_id):
        store = SkillsStore(db)
        return await store._promote_to_instance(skill_id, "attacker", _token=object())

    with pytest.raises(RuntimeError):
        _with_session(_call, skill_id)

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.promoted_at is None


@pytest.mark.django_db(transaction=True)
def test_registry_update_status_refuses_promotion(django_store, cfg):
    """``SkillRegistry._update_status`` refuses ``instance_promoted``."""
    from ai.engine.skills.registry import SkillRegistry
    from ai.models.core import Skill

    _, skill_id = asyncio.run(_seed(f"bypass-reg-{uuid4().hex[:8]}"))

    async def _call(db, skill_id):
        registry = SkillRegistry(db)
        return await registry._update_status(skill_id, "instance_promoted", "attacker")

    with pytest.raises(RuntimeError):
        _with_session(_call, skill_id)

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.promoted_at is None


@pytest.mark.django_db(transaction=True)
def test_registry_update_status_enforces_transition_table(django_store, cfg):
    """``SkillRegistry._update_status`` enforces the explicit transition table."""
    from ai.engine.skills.registry import SkillRegistry
    from ai.models.core import Skill

    _, skill_id = asyncio.run(_seed(f"bypass-table-{uuid4().hex[:8]}"))

    async def _call(db, skill_id, new_status):
        registry = SkillRegistry(db)
        return await registry._update_status(skill_id, new_status)

    # Legal: draft → user_approved.
    _with_session(_call, skill_id, "user_approved")
    assert Skill.objects.get(id=skill_id).status == "user_approved"

    # Illegal: user_approved → (an unknown target) is refused by the table.
    with pytest.raises(ValueError):
        _with_session(_call, skill_id, "does_not_exist")

    # Status must be unchanged after the illegal transition.
    assert Skill.objects.get(id=skill_id).status == "user_approved"


@pytest.mark.django_db(transaction=True)
def test_promote_skill_always_admits_non_pending(django_store, cfg):
    """``gate._promote_skill`` runs admission even when gate_status != pending.

    Regression guard: the old implementation skipped the critics whenever
    ``gate_status != "pending"``, letting a dangerous skill be promoted.  The
    dangerous body below must still be rejected.
    """
    from ai.engine.skills.gate import _promote_skill
    from ai.models.core import Skill

    instance_id, skill_id = asyncio.run(
        _seed(
            f"bypass-always-{uuid4().hex[:8]}",
            gate_status="admitted",  # non-pending — must not skip admission
            kind="sql_macro",
            body=json.dumps({"sql": "DROP TABLE foo"}),
        )
    )

    async def _call(db, skill_id):
        return await _promote_skill(skill_id, db)

    with pytest.raises(ValueError):
        _with_session(_call, skill_id)

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.gate_status == "admitted"  # unchanged; admission wrote a reject log
    assert skill.promoted_at is None


@pytest.mark.django_db(transaction=True)
def test_promote_skill_clean_draft_promotes(django_store, cfg, monkeypatch):
    """``gate._promote_skill`` promotes a clean draft through the gate."""
    from ai.engine.skills.gate import _promote_skill
    from ai.models.core import Skill

    monkeypatch.setenv("SKILL_GATE_MARGINAL_GAIN_ENABLED", "false")
    get_settings.cache_clear()

    _, skill_id = asyncio.run(_seed(f"bypass-clean-{uuid4().hex[:8]}"))

    async def _call(db, skill_id):
        return await _promote_skill(skill_id, db)

    _with_session(_call, skill_id)

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "instance_promoted"
    assert skill.gate_status == "admitted"
    assert skill.promoted_by == "auto"
    assert skill.promoted_at is not None
