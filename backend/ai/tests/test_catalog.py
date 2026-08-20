"""
Phase W3-D — Unified Agent Catalog API tests (backend CRUD + federated
discovery).

Covers:
  * anonymous access -> 401 on every surface
  * list agent roles with declared handoff edges + admitted skills
  * one-agent detail: metadata, incoming/outgoing handoffs, admitted skills,
    last admission log
  * topology: declared graph as ``{nodes, edges}`` (ADR-001)
  * skill catalog + admission status
  * federated index merges DB agents + plugin discovery (DB is the source of
    truth; plugins are additive)
  * writes (POST / PATCH / DELETE) are staff-gated: 403 for regular users,
    201/200 for staff (RULE_21)
  * PATCH updates role/tool_set/max_turns in place (name is immutable)
  * DELETE soft-deletes (is_active=False); unknown ids -> 404

Engine data is seeded through the real engine seams (``AgentRegistry``,
``get_session_factory``) against the Django store backend
(``AI_STORE_BACKEND=django``) so durable writes land in the test DB and
generated PKs are back-filled — the same pattern as ``test_store_execute.py``
and the ``django_store`` fixtures used by the cognition/learning tests.
"""
from __future__ import annotations

import asyncio

import pytest
from django.test import override_settings

from ai.plans_service import PLAN_INSTANCE_ID
from ai.store import reset_store

BASE = "/carbon-api/ai/catalog"


# ── Fixtures ─────────────────────────────────────────────────────────────


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

    return User.objects.create_user(username="catalog-user", password="secret123")


@pytest.fixture
def staff_user(db):
    from accounts.models import User

    user = User.objects.create_user(username="catalog-admin", password="secret123")
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def auth_client(get_token_for_user, user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return client


@pytest.fixture
def staff_client(get_token_for_user, staff_user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(staff_user)}")
    return client


# ── Seeding helpers (through the engine seams, not the ORM) ──────────────


def _seed_defaults() -> dict:
    """Register the 5 default agent roles + 7 declared edges (idempotent)."""
    from ai.engine.agent.registry import AgentRegistry
    from ai.engine.core.database import get_session_factory

    async def _seed():
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            registry = AgentRegistry(db)
            agents = await registry.seed_defaults(PLAN_INSTANCE_ID)
            return {a.name: a for a in agents}

    return asyncio.run(_seed())


def _seed_skill(name: str, *, admitted: bool = True, kind: str = "sql_macro") -> str:
    """Create one Skill + one admission-gate log (verdict by ``admitted``)."""
    from ai.engine.core.database import get_session_factory
    from ai.engine.core.models import Skill, SkillAdmissionLog

    async def _seed():
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            skill = Skill(
                instance_id=PLAN_INSTANCE_ID,
                name=name,
                description=f"{name} description",
                signature='{"type": "object", "properties": {}}',
                body='{"steps": []}',
                kind=kind,
                status="instance_promoted",
                author_user_id="u-1",
            )
            db.add(skill)
            await db.commit()
            await db.refresh(skill)
            db.add(
                SkillAdmissionLog(
                    skill_id=skill.id,
                    instance_id=PLAN_INSTANCE_ID,
                    structural_passed=True,
                    harmlessness_passed=True,
                    consistency_passed=True,
                    marginal_gain_passed=admitted,
                    verdict="admitted" if admitted else "rejected",
                    admitted_by="auto" if admitted else None,
                    rejected_by=None if admitted else "critic.harmlessness",
                )
            )
            await db.commit()
            return skill.id

    return asyncio.run(_seed())


# ── Auth ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_api_requires_auth(api_client):
    assert api_client.get(f"{BASE}/").status_code == 401
    assert api_client.get(f"{BASE}/agents/").status_code == 401
    assert api_client.get(f"{BASE}/topology/").status_code == 401
    assert api_client.get(f"{BASE}/skills/").status_code == 401
    assert api_client.get(f"{BASE}/index/").status_code == 401
    assert api_client.get(f"{BASE}/some-agent-id/").status_code == 401


# ── List ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_list_agents_returns_roles_with_edges_and_skills(auth_client):
    _seed_defaults()
    _seed_skill("emit-sql", admitted=True)
    _seed_skill("bad-skill", admitted=False)

    resp = auth_client.get(f"{BASE}/")
    assert resp.status_code == 200
    agents = resp.json()
    roles = {a["role"] for a in agents}
    assert roles == {
        "orchestrator",
        "researcher",
        "planner",
        "critic",
        "domain_specialist",
    }

    by_role = {a["role"]: a for a in agents}
    orch = by_role["orchestrator"]
    # Declared edges (ADR-001): orchestrator -> researcher/planner/domain_expert
    out_targets = {e["to_agent_id"] for e in orch["outgoing_handoffs"]}
    assert len(out_targets) == 3
    in_targets = {e["from_agent_id"] for e in orch["incoming_handoffs"]}
    assert len(in_targets) == 4  # researcher/planner/critic/domain_expert return to it

    # Admitted skills are attached; rejected ones are not.
    skill_names = {s["name"] for s in orch["skills"]}
    assert "emit-sql" in skill_names
    assert "bad-skill" not in skill_names


@pytest.mark.django_db(transaction=True)
def test_list_agents_literal_agents_alias(auth_client):
    _seed_defaults()
    resp = auth_client.get(f"{BASE}/agents/")
    assert resp.status_code == 200
    assert {a["role"] for a in resp.json()} >= {"orchestrator", "researcher"}


@pytest.mark.django_db(transaction=True)
def test_list_agents_role_filter_and_invalid_role(auth_client):
    _seed_defaults()
    ok = auth_client.get(f"{BASE}/", {"role": "researcher"})
    assert ok.status_code == 200
    assert {a["role"] for a in ok.json()} == {"researcher"}

    bad = auth_client.get(f"{BASE}/", {"role": "bogus"})
    assert bad.status_code == 400
    assert bad.json()["error"] == "invalid_role"


# ── Detail ───────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_agent_detail_has_metadata_handoffs_skills_last_admission(auth_client):
    agents = _seed_defaults()
    _seed_skill("emit-sql", admitted=True)
    orch_id = agents["orchestrator"].id

    resp = auth_client.get(f"{BASE}/{orch_id}/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "orchestrator"
    assert body["role"] == "orchestrator"
    assert body["is_active"] is True
    assert isinstance(body["tool_set"], list)
    assert {e["to_agent_id"] for e in body["outgoing_handoffs"]}
    assert {e["from_agent_id"] for e in body["incoming_handoffs"]}
    assert {"emit-sql"} <= {s["name"] for s in body["skills"]}
    assert body["last_admission_log"]["verdict"] == "admitted"


@pytest.mark.django_db(transaction=True)
def test_agent_detail_literal_alias(auth_client):
    agents = _seed_defaults()
    resp = auth_client.get(f"{BASE}/agents/{agents['critic'].id}/")
    assert resp.status_code == 200
    assert resp.json()["role"] == "critic"


@pytest.mark.django_db(transaction=True)
def test_agent_detail_unknown_returns_404(auth_client):
    resp = auth_client.get(f"{BASE}/no-such-agent/")
    assert resp.status_code == 404
    assert resp.json()["error"] == "agent_not_found"


# ── Topology ─────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_topology_returns_declared_graph(auth_client):
    agents = _seed_defaults()
    resp = auth_client.get(f"{BASE}/topology/")
    assert resp.status_code == 200
    body = resp.json()
    assert {n["name"] for n in body["nodes"]} == {
        "orchestrator",
        "researcher",
        "planner",
        "critic",
        "domain_expert",
    }
    for node in body["nodes"]:
        assert {"id", "name", "role", "status"} <= set(node)
        assert node["status"] == "active"

    assert len(body["edges"]) == 7  # seed_defaults declares exactly 7 edges
    orch_id = agents["orchestrator"].id
    res_id = agents["researcher"].id
    assert any(
        e["from"] == orch_id and e["to"] == res_id for e in body["edges"]
    )
    for edge in body["edges"]:
        assert {"from", "to", "description", "max_parallel"} <= set(edge)


# ── Skills ───────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_skill_catalog_with_admission_status(auth_client):
    _seed_skill("emit-sql", admitted=True)
    _seed_skill("bad-skill", admitted=False)

    resp = auth_client.get(f"{BASE}/skills/")
    assert resp.status_code == 200
    by_name = {s["name"]: s for s in resp.json()}
    assert by_name["emit-sql"]["admission"]["verdict"] == "admitted"
    assert by_name["emit-sql"]["kind"] == "sql_macro"
    assert by_name["bad-skill"]["admission"]["verdict"] == "rejected"


# ── Writes (staff-gated, RULE_21) ────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_create_agent_requires_staff(auth_client, staff_client):
    payload = {
        "name": "auditor",
        "role": "critic",
        "tool_set": ["search_knowledge"],
        "max_turns": 2,
    }
    denied = auth_client.post(f"{BASE}/", payload, format="json")
    assert denied.status_code == 403
    assert denied.json()["error"] == "admin_required"

    created = staff_client.post(f"{BASE}/", payload, format="json")
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "auditor"
    assert body["role"] == "critic"
    assert body["max_turns"] == 2
    assert body["is_active"] is True

    listed = staff_client.get(f"{BASE}/", {"role": "critic"}).json()
    assert any(a["name"] == "auditor" for a in listed)


@pytest.mark.django_db(transaction=True)
def test_create_agent_invalid_role_returns_400(staff_client):
    resp = staff_client.post(
        f"{BASE}/", {"name": "rogue", "role": "spy"}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_patch_agent_requires_staff_and_updates_in_place(auth_client, staff_client):
    agents = _seed_defaults()
    orch_id = agents["orchestrator"].id

    denied = auth_client.patch(
        f"{BASE}/{orch_id}/", {"role": "critic"}, format="json"
    )
    assert denied.status_code == 403

    updated = staff_client.patch(
        f"{BASE}/{orch_id}/",
        {"role": "planner", "tool_set": ["search_knowledge"], "max_turns": 7},
        format="json",
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["role"] == "planner"
    assert body["tool_set"] == ["search_knowledge"]
    assert body["max_turns"] == 7
    assert body["name"] == "orchestrator"  # name is the upsert key — immutable

    detail = staff_client.get(f"{BASE}/{orch_id}/").json()
    assert detail["role"] == "planner"
    assert detail["max_turns"] == 7


@pytest.mark.django_db(transaction=True)
def test_patch_agent_unknown_returns_404(staff_client):
    resp = staff_client.patch(
        f"{BASE}/no-such-agent/", {"max_turns": 5}, format="json"
    )
    assert resp.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_delete_agent_requires_staff_and_soft_deletes(auth_client, staff_client):
    agents = _seed_defaults()
    critic_id = agents["critic"].id

    denied = auth_client.delete(f"{BASE}/{critic_id}/")
    assert denied.status_code == 403

    removed = staff_client.delete(f"{BASE}/{critic_id}/")
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True

    detail = staff_client.get(f"{BASE}/{critic_id}/").json()
    assert detail["is_active"] is False  # soft-deleted, row stays in the DB

    missing = staff_client.delete(f"{BASE}/no-such-agent/")
    assert missing.status_code == 404


# ── Federated index ──────────────────────────────────────────────────────


class _FakeToolPlugin:
    name = "fake_tool"
    description = "Fake tool plugin"
    input_schema = {"type": "object", "properties": {"q": {"type": "string"}}}
    requires_confirmation = False
    capability = "dq:manage_rules"
    app_identifier = "dq"


class _FakeWorkflowPlugin:
    name = "fake_workflow"
    description = "Fake workflow plugin"
    input_schema = {"type": "object", "properties": {}}
    requires_confirmation = True
    capability = None
    app_identifier = "importexport"


@pytest.mark.django_db(transaction=True)
def test_federated_index_merges_plugins(auth_client, monkeypatch):
    from ai.engine.agent.plugins import WorkflowPlugin

    # Kind classification must come from the real WorkflowPlugin ABC.  All
    # metadata is defined directly on the subclass — the ABC's class attrs
    # (ToolPlugin.name == "") would otherwise win the MRO lookup.
    class FakeWorkflow(WorkflowPlugin):
        name = "fake_workflow"
        description = "Fake workflow plugin"
        input_schema = {"type": "object", "properties": {}}
        requires_confirmation = True
        capability = None
        app_identifier = "importexport"
        steps = [{"tool": "call_host_api", "args": {}}]

    monkeypatch.setattr(
        "ai.engine.agent.plugins.registered_plugins",
        lambda: [_FakeToolPlugin(), FakeWorkflow()],
    )

    _seed_defaults()
    _seed_skill("emit-sql", admitted=True)

    resp = auth_client.get(f"{BASE}/index/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "federated"
    assert body["db_is_source_of_truth"] is True

    # DB agents are the source of truth…
    roles = {a["role"] for a in body["agents"]}
    assert "orchestrator" in roles
    assert {s["name"] for s in body["agents"][0]["skills"]} == {"emit-sql"}

    # …and plugins are discovered additively (never shadowing agents).
    plugins = {p["name"]: p for p in body["plugins"]}
    assert plugins["fake_tool"]["kind"] == "tool"
    assert plugins["fake_tool"]["capability"] == "dq:manage_rules"
    assert plugins["fake_tool"]["requires_confirmation"] is False
    assert plugins["fake_workflow"]["kind"] == "workflow"
    assert plugins["fake_workflow"]["app_identifier"] == "importexport"
    assert "fake_tool" not in {a["name"] for a in body["agents"]}
