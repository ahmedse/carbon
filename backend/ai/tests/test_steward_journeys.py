# backend/ai/tests/test_steward_journeys.py
"""ADR-0036 Phase 7 — Steward journeys J1–J7 (API pack).

Exit gate for Control Plane harden: one green module that proves a steward can
contain risk, enforce SoD, persist reject, join evidence+PDP, freeze learning
promote, revoke memory, and trip budget — without stitching five screens.

Offline where possible (no live LLM). Run::

    PYTHONPATH=. ../.venv/bin/pytest ai/tests/test_steward_journeys.py -q -m "not live"
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.constants import AI_PROCESS_OWNER_GROUP, AI_PUBLISHER_GROUP
from ai.engine.core.config import get_settings
from ai.instance_registry import resolve_instance_id
from ai.models.control_state import PulseControlState, get_or_create_control_state
from ai.models.core import AuditLog, MemoryLongTerm
from ai.models.knowledge import KnowledgeItem
from ai.models.pdp import PolicyDecisionRow
from ai.models.process import STATUS_DRAFT, STATUS_REVIEW, ProcessDefinition
from ai.store import reset_store
from ai.tests.conftest import grant_role, make_user


User = get_user_model()


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser(
        username="steward_admin", email="steward@example.com", password="x"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


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


# ── J1 Contain ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_j1_contain_learning_freeze(admin_client):
    """POST containment → command reflects freeze → promote returns 423."""
    client, user = admin_client
    instance_id = resolve_instance_id()

    resp = client.post(
        "/carbon-api/ai/pulse/control/containment/",
        {"level": "learning_freeze", "reason": "J1 steward contain"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["containment_level"] == "learning_freeze"
    assert body["learning_admissions_frozen"] is True

    cmd = client.get("/carbon-api/ai/pulse/control/command/")
    assert cmd.status_code == 200
    assert cmd.json()["containment"]["containment_level"] == "learning_freeze"

    assert AuditLog.objects.filter(
        action="ai.containment.set", actor=user.username
    ).exists()

    # Promote under freeze → 423 (skill may be missing; freeze check is first)
    from ai.models.core import Skill as DjangoSkill
    from ai.engine.core.models import generate_uuid

    skill_id = generate_uuid()
    DjangoSkill.objects.create(
        id=skill_id,
        instance_id=instance_id,
        name="j1-frozen-skill",
        description="x",
        signature={},
        body={},
        kind="procedure",
        status="draft",
        author_user_id="system",
        gate_status="pending",
        visibility="global",
        app_identifier="carbon",
    )
    promote = client.post(
        reverse("ai-skill-promote", kwargs={"pk": skill_id}),
        {},
        format="json",
    )
    assert promote.status_code == 423
    assert promote.json().get("error") == "learning_frozen"

    # Reset containment so later tests in the same DB are not poisoned
    client.post(
        "/carbon-api/ai/pulse/control/containment/",
        {"level": "normal", "reason": "J1 reset"},
        format="json",
    )


# ── J2 Publish SoD ─────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_j2_publish_sod_self_approval_refused(api_client, monkeypatch):
    """Author who is also publisher cannot self-publish (SoD)."""
    monkeypatch.setattr(
        "ai.models.process._default_known_capabilities",
        lambda: {"noop.capability"},
    )
    pid = f"proc.j2.{uuid4().hex[:8]}"
    author = make_user(f"j2-author-{uuid4().hex[:6]}")
    grant_role(author, group_name=AI_PROCESS_OWNER_GROUP)
    grant_role(author, group_name=AI_PUBLISHER_GROUP)

    doc = {
        "id": pid,
        "version": "0.1.0",
        "owner": author.username,
        "status": "draft",
        "steps": [
            {
                "id": "s1",
                "kind": "command",
                "capability": "noop.capability",
                "autonomy": "human_only",
            }
        ],
        "objective": {"predicate": "j2 sod"},
    }

    api_client.force_authenticate(user=author)
    create = api_client.post(
        reverse("ai-registry-list"), data=doc, format="json"
    )
    assert create.status_code in (200, 201), create.content
    submit = api_client.post(reverse("ai-registry-submit", kwargs={"pk": pid}))
    assert submit.status_code == 200, submit.content

    publish = api_client.post(reverse("ai-registry-publish", kwargs={"pk": pid}))
    assert publish.status_code == 403, publish.content
    assert publish.json().get("error") == "forbidden"
    latest = (
        ProcessDefinition.objects.filter(process_id=pid)
        .order_by("-created_at")
        .first()
    )
    assert latest is not None
    assert latest.status == STATUS_REVIEW


# ── J3 Reject persisted ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_j3_reject_persisted(admin_client, monkeypatch):
    client, user = admin_client
    monkeypatch.setattr(
        "ai.models.process._default_known_capabilities",
        lambda: {"noop.capability"},
    )
    pid = f"proc.j3.{uuid4().hex[:8]}"
    doc = {
        "id": pid,
        "version": "1.0.0",
        "owner": "author",
        "status": STATUS_REVIEW,
        "steps": [
            {
                "id": "s1",
                "kind": "command",
                "capability": "noop.capability",
                "autonomy": "human_only",
            }
        ],
        "objective": {"predicate": "j3"},
    }
    obj = ProcessDefinition.from_document(doc)
    obj.host_user_id = str(user.pk)
    obj.save()

    resp = client.post(
        f"/carbon-api/ai/registry/processes/{pid}/reject/",
        {"reason": "J3 missing evidence"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["status"] == STATUS_DRAFT
    assert body["definition"]["last_reject_reason"] == "J3 missing evidence"
    assert body["definition"]["review_history"][-1]["action"] == "rejected"


# ── J4 Evidence PDP ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_j4_evidence_includes_pdp(admin_client):
    from ai.instance_registry import resolve_default_app_identifier

    client, _ = admin_client
    run_id = f"run-j4-{uuid4().hex[:8]}"
    PolicyDecisionRow.objects.create(
        principal="user:steward",
        action="carbon:query",
        resource_objects=[],
        decision="allow",
        reason="J4 fixture",
        policy_version="test",
        autonomy="propose",
        stage="pdp",
        request_id=run_id,
        visibility="shared",
        app_identifier=resolve_default_app_identifier(),
    )

    resp = client.get(
        f"/carbon-api/ai/pulse/control/evidence/?run_id={run_id}"
    )
    assert resp.status_code == 200, resp.content
    events = resp.json().get("events") or []
    pdp = [e for e in events if e.get("source") == "pdp"]
    assert pdp, f"expected pdp events, got {events}"
    assert pdp[0]["detail"]["decision"] == "allow"


# ── J5 Skill promote blocked by freeze ─────────────────────────────────────


@pytest.mark.django_db
def test_j5_skill_promote_blocked_when_frozen(admin_client):
    """Explicit J5: learning_freeze blocks skill promote."""
    from ai.instance_registry import resolve_default_app_identifier
    from ai.models.core import Skill as DjangoSkill
    from ai.engine.core.models import generate_uuid

    client, _ = admin_client
    state = get_or_create_control_state(resolve_instance_id())
    state.containment_level = "learning_freeze"
    state.learning_admissions_frozen = True
    state.save(
        update_fields=[
            "containment_level",
            "learning_admissions_frozen",
            "updated_at",
        ]
    )

    skill_id = generate_uuid()
    DjangoSkill.objects.create(
        id=skill_id,
        instance_id=resolve_instance_id(),
        name="j5-skill",
        description="x",
        signature={},
        body={},
        kind="procedure",
        status="draft",
        author_user_id="system",
        gate_status="pending",
        visibility="global",
        app_identifier=resolve_default_app_identifier(),
    )
    resp = client.post(
        reverse("ai-skill-promote", kwargs={"pk": skill_id}),
        {},
        format="json",
    )
    assert resp.status_code == 423

    state.containment_level = "normal"
    state.learning_admissions_frozen = False
    state.save(
        update_fields=[
            "containment_level",
            "learning_admissions_frozen",
            "updated_at",
        ]
    )


# ── J6 Memory revoke ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_j6_memory_revoke(admin_client):
    from ai.instance_registry import resolve_default_app_identifier

    client, user = admin_client
    fact = MemoryLongTerm.objects.create(
        instance_id=resolve_instance_id(),
        category="preference",
        content="J6 fact to revoke",
        source="test",
        confidence=0.9,
        archived=False,
        host_user_id=str(user.pk),
        visibility="shared",
        app_identifier=resolve_default_app_identifier(),
    )
    resp = client.post(
        f"/carbon-api/ai/memory/facts/{fact.pk}/revoke/",
        {"reason": "J6 steward revoke"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json().get("revoked") is True
    fact.refresh_from_db()
    assert fact.archived is True
    assert fact.valid_to is not None
    assert AuditLog.objects.filter(
        action="ai.memory.revoke", target=str(fact.pk)
    ).exists()


# ── J7 Budget trip via control-plane override ──────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_j7_budget_trip_via_control_override(admin_client, django_store, cfg, monkeypatch):
    """PATCH control/budget → route_chat finishes budget_exceeded."""
    from ai.engine.core.models import LLMCallLog as EngineLLMCallLog
    from ai.engine.core.models import Instance, generate_uuid
    from ai.engine.llm.router import route_chat
    from ai.store import get_store

    client, _ = admin_client
    instance_id = generate_uuid()

    # Control override for this instance (router reads PulseControlState by id)
    PulseControlState.objects.update_or_create(
        instance_id=instance_id,
        defaults={
            "daily_budget_usd": 0.01,
            "containment_level": "normal",
            "learning_admissions_frozen": False,
        },
    )
    # High env default so override is what trips
    monkeypatch.setenv("LLM_DAILY_BUDGET_USD", "100.0")
    get_settings.cache_clear()

    async def _seed():
        factory = get_store().get_session_factory()
        async with factory() as db:
            db.add(
                Instance(
                    id=instance_id,
                    name=f"j7-{instance_id[:8]}",
                    display_name="j7",
                    host_db_url="postgres://db",
                    host_api_url="https://host",
                    status="active",
                )
            )
            db.add(
                EngineLLMCallLog(
                    id=generate_uuid(),
                    instance_id=instance_id,
                    conversation_id="seed-conv",
                    model="test",
                    llm_calls=1,
                    total_tokens=100,
                    cost_usd=0.5,
                    duration_ms=10,
                )
            )
            await db.commit()

    asyncio.run(_seed())

    result = asyncio.run(
        route_chat(
            task="chat",
            instance_id=instance_id,
            conversation_id=f"conv-{uuid4().hex[:8]}",
            messages=[{"role": "user", "content": "hi"}],
        )
    )
    assert result["finish_reason"] == "budget_exceeded"
    assert result["input_tokens"] == 0

    # Also prove Platform PATCH path still works on resolved instance
    patch = client.patch(
        "/carbon-api/ai/pulse/control/budget/",
        {"daily_budget_usd": 25.0},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.json()["daily_budget_usd"] == 25.0


# ── Bonus: Knowledge revoke path used by Assets ────────────────────────────


@pytest.mark.django_db
def test_j_assets_knowledge_revoke(admin_client):
    client, _ = admin_client
    create = client.post(
        "/carbon-api/ai/knowledge/items/",
        {
            "knowledge_class": "business_fact",
            "content": "J knowledge item",
            "source": "steward",
        },
        format="json",
    )
    assert create.status_code == 201, create.content
    item_id = create.json()["id"]
    revoke = client.post(
        f"/carbon-api/ai/knowledge/items/{item_id}/revoke/",
        {"reason": "stale"},
        format="json",
    )
    assert revoke.status_code == 200
    assert KnowledgeItem.objects.get(pk=item_id).review_status == "deprecated"
