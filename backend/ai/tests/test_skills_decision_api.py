"""PEC-6A — Admin skill promote/reject decision API.

Covers:
  * Unauthenticated → 401
  * Authenticated non-publisher / non-process-owner → 403
  * Publisher promote path runs the admission gate → instance_promoted
    + SkillAdmissionLog + AuditLog
  * Publisher reject → deprecated / gate_status rejected + AuditLog
  * Forged status write still gate-only (adapter refuses instance_promoted)
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.test import override_settings
from django.urls import reverse

from accounts.constants import AI_PROCESS_OWNER_GROUP, AI_PUBLISHER_GROUP
from ai.engine.core.config import get_settings
from ai.store import reset_store
from ai.tests.conftest import grant_role, make_user

pytestmark = pytest.mark.django_db(transaction=True)


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


def _url(name: str, pk: str) -> str:
    return reverse(f"ai-skill-{name}", kwargs={"pk": pk})


def _publisher(username: str = "skill-publisher"):
    user = make_user(username)
    grant_role(user, group_name=AI_PUBLISHER_GROUP)
    return user


def _owner(username: str = "skill-owner"):
    user = make_user(username)
    grant_role(user, group_name=AI_PROCESS_OWNER_GROUP)
    return user


async def _seed_pending_skill_async(instance_name: str | None = None) -> str:
    """Seed a clean pending draft via the Store; return skill_id."""
    from ai.engine.core.models import Instance, Skill, generate_uuid
    from ai.store import get_store

    instance_id = generate_uuid()
    skill_id = generate_uuid()
    name = instance_name or f"decision-{uuid4().hex[:8]}"
    factory = get_store().get_session_factory()
    async with factory() as db:
        db.add(
            Instance(
                id=instance_id,
                name=name,
                display_name=name,
                host_db_url="postgres://db",
                host_api_url="https://host",
                status="active",
            )
        )
        db.add(
            Skill(
                id=skill_id,
                instance_id=instance_id,
                name="admin_decision_skill",
                description="Pending draft for admin promote/reject",
                signature="{}",
                body="{}",
                kind="procedure",
                status="draft",
                author_user_id="system",
                gate_status="pending",
            )
        )
        await db.commit()
    return skill_id


def _seed_pending_skill(instance_name: str | None = None) -> str:
    """Seed + stamp CBAC columns so publisher lookups succeed."""
    from ai.models.core import Skill as DjangoSkill

    skill_id = asyncio.run(_seed_pending_skill_async(instance_name))
    DjangoSkill.objects.filter(id=skill_id).update(
        visibility="global",
        app_identifier="carbon",
        org_unit_id=None,
    )
    return skill_id


# ── Auth / CBAC ────────────────────────────────────────────────────────────


def test_promote_unauthenticated_401(api_client, django_store):
    skill_id = _seed_pending_skill()
    resp = api_client.post(_url("promote", skill_id), {}, format="json")
    assert resp.status_code == 401


def test_reject_unauthenticated_401(api_client, django_store):
    skill_id = _seed_pending_skill()
    resp = api_client.post(
        _url("reject", skill_id), {"reason": "nope"}, format="json"
    )
    assert resp.status_code == 401


def test_promote_plain_user_403(api_client, django_store):
    skill_id = _seed_pending_skill()
    plain = make_user("plain-skill-user")
    api_client.force_authenticate(user=plain)
    resp = api_client.post(_url("promote", skill_id), {}, format="json")
    assert resp.status_code == 403


def test_reject_plain_user_403(api_client, django_store):
    skill_id = _seed_pending_skill()
    plain = make_user("plain-skill-reject")
    api_client.force_authenticate(user=plain)
    resp = api_client.post(
        _url("reject", skill_id), {"reason": "unsafe"}, format="json"
    )
    assert resp.status_code == 403


# ── Promote path ───────────────────────────────────────────────────────────


def test_publisher_promote_runs_gate(api_client, django_store, cfg, monkeypatch):
    """Publisher promote → admitted + instance_promoted + admission + audit logs."""
    from ai.models.core import AuditLog, Skill, SkillAdmissionLog

    monkeypatch.setenv("SKILL_GATE_MARGINAL_GAIN_ENABLED", "false")
    get_settings.cache_clear()

    skill_id = _seed_pending_skill()
    before_promoted = Skill.objects.filter(status="instance_promoted").count()

    user = _publisher()
    api_client.force_authenticate(user=user)
    resp = api_client.post(_url("promote", skill_id), {}, format="json")

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["decision"] == "promote"
    assert body["verdict"] == "admitted"
    assert body["skill"]["id"] == skill_id
    assert body["skill"]["status"] == "instance_promoted"
    assert body["skill"]["gate_status"] == "admitted"

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "instance_promoted"
    assert skill.gate_status == "admitted"
    assert skill.promoted_by == f"admin:{user.username}"
    assert skill.promoted_at is not None
    assert Skill.objects.filter(status="instance_promoted").count() == before_promoted + 1

    logs = list(SkillAdmissionLog.objects.filter(skill_id=skill_id))
    assert len(logs) == 1
    assert logs[0].verdict == "admitted"
    assert logs[0].admitted_by == f"admin:{user.username}"

    audit = AuditLog.objects.filter(
        action="ai.skill_promoted", target=skill_id
    ).first()
    assert audit is not None
    assert audit.actor == str(user.pk)
    assert (audit.detail or {}).get("decision") == "promote"


def test_process_owner_can_promote(api_client, django_store, cfg, monkeypatch):
    monkeypatch.setenv("SKILL_GATE_MARGINAL_GAIN_ENABLED", "false")
    get_settings.cache_clear()

    skill_id = _seed_pending_skill()
    api_client.force_authenticate(user=_owner())
    resp = api_client.post(_url("promote", skill_id), {}, format="json")
    assert resp.status_code == 200
    assert resp.json()["skill"]["status"] == "instance_promoted"


# ── Reject path ────────────────────────────────────────────────────────────


def test_publisher_reject_deprecates(api_client, django_store, cfg):
    from ai.models.core import AuditLog, Skill

    skill_id = _seed_pending_skill()
    user = _publisher("reject-publisher")
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        _url("reject", skill_id),
        {"reason": "fails harmlessness review"},
        format="json",
    )

    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["decision"] == "reject"
    assert body["verdict"] == "rejected"
    assert body["skill"]["status"] == "deprecated"

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "deprecated"
    assert skill.gate_status == "rejected"

    audit = AuditLog.objects.filter(
        action="ai.skill_rejected", target=skill_id
    ).first()
    assert audit is not None
    assert "fails harmlessness" in (audit.detail or {}).get("reason", "")


# ── Gate-only forged path ─────────────────────────────────────────────────


def test_forged_status_write_still_gate_only(django_store):
    """Direct adapter update_status(instance_promoted) must raise — no bypass."""
    from ai.adapters.skills import DjangoSkillAdapter
    from ai.store import get_store

    skill_id = _seed_pending_skill("forge-gate")

    async def _forge():
        factory = get_store().get_session_factory()
        async with factory() as db:
            adapter = DjangoSkillAdapter(db)
            with pytest.raises(RuntimeError, match="gate-only"):
                await adapter.update_status(skill_id, "instance_promoted")

    asyncio.run(_forge())

    from ai.models.core import Skill

    skill = Skill.objects.get(id=skill_id)
    assert skill.status == "draft"
    assert skill.gate_status == "pending"
