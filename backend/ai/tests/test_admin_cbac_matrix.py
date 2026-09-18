# backend/ai/tests/test_admin_cbac_matrix.py
"""Pulse Admin QA Gate L3 — roles × actions CBAC deny matrix.

Minimal personas (one AI governance group each; no superuser).
Platform manage uses ``admins_group`` (*) because ``ai:manage_console`` is not
assigned via AI governance groups today.

Contract: ``ai:view_console`` never authorizes publish / promote / budget /
containment / knowledge write / prompt activate.

Plan: docs/pulse/PULSE-ADMIN-QA-GATE.md §4.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.constants import (
    ADMINS_GROUP,
    AI_AUDITOR_GROUP,
    AI_OPERATOR_GROUP,
    AI_POLICY_OWNER_GROUP,
    AI_PROCESS_OWNER_GROUP,
    AI_PUBLISHER_GROUP,
)
from ai.instance_registry import resolve_default_app_identifier, resolve_instance_id
from ai.models.core import MemoryLongTerm, PromptVersion, Skill
from ai.models.knowledge import KnowledgeItem
from ai.models.process import STATUS_DRAFT, STATUS_REVIEW, ProcessDefinition
from ai.tests.conftest import grant_role, make_user

pytestmark = pytest.mark.django_db


CONTROL = "/carbon-api/ai/pulse/control"
REGISTRY = "/carbon-api/ai/registry/processes"
KNOWLEDGE = "/carbon-api/ai/knowledge/items"
MEMORY = "/carbon-api/ai/memory/facts"


def _client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _persona(group_name: str, label: str):
    user = make_user(f"cbac-{label}-{uuid4().hex[:6]}")
    grant_role(user, group_name=group_name)
    return user


@pytest.fixture
def auditor():
    return _persona(AI_AUDITOR_GROUP, "auditor")


@pytest.fixture
def process_owner():
    return _persona(AI_PROCESS_OWNER_GROUP, "owner")


@pytest.fixture
def publisher():
    return _persona(AI_PUBLISHER_GROUP, "publisher")


@pytest.fixture
def operator():
    return _persona(AI_OPERATOR_GROUP, "operator")


@pytest.fixture
def policy_owner():
    return _persona(AI_POLICY_OWNER_GROUP, "policy")


@pytest.fixture
def manage():
    """Platform admin — wildcard caps include ai:manage_console."""
    return _persona(ADMINS_GROUP, "manage")


@pytest.fixture
def plain():
    """Authenticated, zero AI capabilities."""
    return make_user(f"cbac-plain-{uuid4().hex[:6]}")


# ── Reads (command / evidence / candidates) ────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 200),
        ("process_owner", 200),  # ControlRead allows process_owner
        ("publisher", 403),  # publisher alone has no view_console
        ("operator", 403),
        ("policy_owner", 403),
        ("manage", 200),
        ("plain", 403),
    ],
)
def test_get_command_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).get(f"{CONTROL}/command/")
    assert resp.status_code == expected, resp.content


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 200),
        ("process_owner", 200),
        ("publisher", 403),
        ("plain", 403),
    ],
)
def test_get_candidates_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).get(f"{CONTROL}/candidates/")
    assert resp.status_code == expected


def test_anonymous_command_401(api_client):
    assert api_client.get(f"{CONTROL}/command/").status_code == 401


# ── Containment ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("publisher", 403),
        ("policy_owner", 403),
        ("plain", 403),
        ("operator", 200),
        ("process_owner", 200),
        ("manage", 200),
    ],
)
def test_post_containment_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).post(
        f"{CONTROL}/containment/",
        {"level": "learning_freeze", "reason": "cbac matrix"},
        format="json",
    )
    assert resp.status_code == expected, resp.content
    # Reset if we froze
    if expected == 200:
        _client_for(user).post(
            f"{CONTROL}/containment/",
            {"level": "normal", "reason": "cbac reset"},
            format="json",
        )


# ── Budget ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("process_owner", 403),
        ("publisher", 403),
        ("operator", 403),
        ("policy_owner", 403),
        ("plain", 403),
        ("manage", 200),
    ],
)
def test_patch_budget_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).patch(
        f"{CONTROL}/budget/",
        {"daily_budget_usd": 99.0},
        format="json",
    )
    assert resp.status_code == expected, resp.content


# ── PDP dry-run ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("publisher", 403),
        ("operator", 403),
        ("plain", 403),
        ("policy_owner", 200),
        ("process_owner", 200),
        ("manage", 200),
    ],
)
def test_pdp_dry_run_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).post(
        f"{CONTROL}/pdp/dry-run/",
        {
            "action": "carbon:query",
            "autonomy": "human_only",
            "objects": [],
            "process_state": {},
        },
        format="json",
    )
    assert resp.status_code == expected, resp.content


# ── Registry publish / create ──────────────────────────────────────────────


def _seed_review_process(owner_username: str, monkeypatch) -> str:
    monkeypatch.setattr(
        "ai.models.process._default_known_capabilities",
        lambda: {"noop.capability"},
    )
    pid = f"cbac.reg.{uuid4().hex[:8]}"
    doc = {
        "id": pid,
        "version": "0.1.0",
        "owner": owner_username,
        "status": STATUS_REVIEW,
        "steps": [
            {
                "id": "s1",
                "kind": "command",
                "capability": "noop.capability",
                "autonomy": "human_only",
            }
        ],
        "objective": {"predicate": "cbac"},
    }
    ProcessDefinition.from_document(doc).save()
    return pid


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("operator", 403),
        ("policy_owner", 403),
        ("plain", 403),
        ("process_owner", 403),  # SoD / publisher-only for publish
        ("publisher", 200),
        ("manage", 200),  # wildcard
    ],
)
def test_registry_publish_by_role(request, persona, expected, monkeypatch):
    user = request.getfixturevalue(persona)
    # Author must differ from publisher for SoD (non-superuser)
    author_name = "cbac-author-other"
    pid = _seed_review_process(author_name, monkeypatch)
    resp = _client_for(user).post(f"{REGISTRY}/{pid}/publish/", {}, format="json")
    assert resp.status_code == expected, resp.content


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("publisher", 403),
        ("operator", 403),
        ("plain", 403),
        ("process_owner", 201),
        ("manage", 201),
    ],
)
def test_registry_create_by_role(request, persona, expected, monkeypatch):
    user = request.getfixturevalue(persona)
    monkeypatch.setattr(
        "ai.models.process._default_known_capabilities",
        lambda: {"noop.capability"},
    )
    pid = f"cbac.create.{uuid4().hex[:8]}"
    doc = {
        "id": pid,
        "version": "0.1.0",
        "owner": user.username,
        "status": STATUS_DRAFT,
        "steps": [
            {
                "id": "s1",
                "kind": "command",
                "capability": "noop.capability",
                "autonomy": "human_only",
            }
        ],
        "objective": {"predicate": "cbac create"},
    }
    resp = _client_for(user).post(f"{REGISTRY}/", doc, format="json")
    # Some stacks return 200 on create
    if expected == 201:
        assert resp.status_code in (200, 201), resp.content
    else:
        assert resp.status_code == expected, resp.content


# ── Skills promote ─────────────────────────────────────────────────────────


def _seed_skill() -> str:
    from ai.engine.core.models import generate_uuid

    skill_id = generate_uuid()
    Skill.objects.create(
        id=skill_id,
        instance_id=resolve_instance_id(),
        name=f"cbac-skill-{skill_id[:8]}",
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
    return skill_id


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("operator", 403),
        ("policy_owner", 403),
        ("plain", 403),
        ("process_owner", 200),  # may be 200 or admission reject body — not 403
        ("publisher", 200),
        ("manage", 200),
    ],
)
def test_skill_promote_permission_by_role(request, persona, expected):
    """Permission gate only — admission may still refuse; never 403 for allowed."""
    user = request.getfixturevalue(persona)
    skill_id = _seed_skill()
    resp = _client_for(user).post(
        reverse("ai-skill-promote", kwargs={"pk": skill_id}),
        {},
        format="json",
    )
    if expected == 403:
        assert resp.status_code == 403, resp.content
    else:
        # Allowed roles passed CBAC; admission gate may return 200/400/423.
        assert resp.status_code != 403, resp.content
        assert resp.status_code in (200, 400, 423), resp.content


# ── Knowledge write ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("process_owner", 403),
        ("operator", 403),
        ("policy_owner", 403),
        ("plain", 403),
        ("publisher", 201),
        ("manage", 201),
    ],
)
def test_knowledge_create_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).post(
        f"{KNOWLEDGE}/",
        {
            "knowledge_class": "business_fact",
            "content": "cbac knowledge",
            "source": "test",
        },
        format="json",
    )
    assert resp.status_code == expected, resp.content


# ── Prompt versions list / activate permission ─────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("process_owner", 403),
        ("operator", 403),
        ("plain", 403),
        ("publisher", 200),
        ("manage", 200),
    ],
)
def test_prompt_versions_list_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    resp = _client_for(user).get(f"{CONTROL}/prompts/versions/")
    assert resp.status_code == expected, resp.content


# ── Memory revoke (steward manage_console) ─────────────────────────────────


@pytest.mark.parametrize(
    "persona,expected",
    [
        ("auditor", 403),
        ("publisher", 403),
        ("operator", 403),
        ("process_owner", 403),
        ("plain", 403),
        ("manage", 200),
    ],
)
def test_memory_revoke_steward_by_role(request, persona, expected):
    user = request.getfixturevalue(persona)
    # Fact owned by someone else — only manage_console (or owner) may revoke
    owner = make_user(f"cbac-fact-owner-{uuid4().hex[:6]}")
    fact = MemoryLongTerm.objects.create(
        instance_id=resolve_instance_id(),
        category="preference",
        content="cbac revoke target",
        source="test",
        confidence=0.9,
        archived=False,
        host_user_id=str(owner.pk),
        visibility="shared",
        app_identifier=resolve_default_app_identifier(),
    )
    resp = _client_for(user).post(
        f"{MEMORY}/{fact.pk}/revoke/",
        {"reason": "cbac"},
        format="json",
    )
    assert resp.status_code == expected, resp.content


# ── View-never-publish smoke ───────────────────────────────────────────────


def test_auditor_cannot_publish_or_budget_or_contain(auditor, monkeypatch):
    """Canonical contract: view_console (auditor) never mutates authority."""
    client = _client_for(auditor)
    assert client.get(f"{CONTROL}/command/").status_code == 200
    assert (
        client.post(
            f"{CONTROL}/containment/",
            {"level": "tool_freeze", "reason": "x"},
            format="json",
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{CONTROL}/budget/", {"daily_budget_usd": 1}, format="json"
        ).status_code
        == 403
    )
    pid = _seed_review_process("other-author", monkeypatch)
    assert client.post(f"{REGISTRY}/{pid}/publish/", {}, format="json").status_code == 403
    assert (
        client.post(
            f"{KNOWLEDGE}/",
            {
                "knowledge_class": "business_fact",
                "content": "nope",
                "source": "t",
            },
            format="json",
        ).status_code
        == 403
    )
