"""PS-* fixtures — specialized Nibras coworker agents + handoffs + pack coerce.

Maps to canvases/pulse-nibras-coworker-qa §7b:
  PS-01 payroll_controller (+ siblings) registered with export tools
  PS-02 topology edges orchestrator → specialists → back
  PS-03 board-pack brief coerces export_document format=pack
  PS-04 templates from seed_complex_agent_demos shape (plan_json export step)
"""

from __future__ import annotations

import asyncio

import pytest
from django.test import override_settings

from ai.catalog_service import CatalogService
from ai.engine.agent.registry import AgentRegistry
from ai.engine.cognition.plan.planner import (
    PlanStep,
    _coerce_export_steps,
    _ensure_export_deliverable,
    _infer_export_format,
)
from ai.engine.core.database import get_session_factory
from ai.plans_service import PLAN_INSTANCE_ID
from ai.store import reset_store

BASE = "/carbon-api/ai/catalog"

SPECIALISTS = (
    "payroll_controller",
    "compliance_auditor",
    "workforce_researcher",
    "finance_packager",
)


@pytest.fixture(autouse=True)
def _django_store():
    with override_settings(AI_STORE_BACKEND="django"):
        reset_store()
        yield
        reset_store()


def _seed_defaults() -> dict:
    async def _seed():
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            registry = AgentRegistry(db)
            agents = await registry.seed_defaults(PLAN_INSTANCE_ID)
            return {a.name: a for a in agents}

    return asyncio.run(_seed())


def _seed_specialists() -> dict[str, str]:
    """Mirror seed_complex_agent_demos agent + handoff registration."""
    from ai.management.commands.seed_complex_agent_demos import (
        AGENT_SPECS,
        HANDOFF_SPECS,
    )

    _seed_defaults()
    catalog = CatalogService(instance_id=PLAN_INSTANCE_ID)
    by_name: dict[str, str] = {}
    for spec in AGENT_SPECS:
        row = catalog.register_agent(
            name=spec["name"],
            role=spec["role"],
            tool_set=spec["tool_set"],
            playbook_blocks=spec["playbook_blocks"],
            max_turns=spec["max_turns"],
        )
        by_name[spec["name"]] = row["id"]
    for agent in catalog.list_agents():
        by_name.setdefault(agent["name"], agent["id"])

    async def _edges():
        async with get_session_factory(PLAN_INSTANCE_ID)() as db:
            registry = AgentRegistry(db)
            for from_name, to_name, max_parallel, desc in HANDOFF_SPECS:
                if from_name not in by_name or to_name not in by_name:
                    continue
                await registry.add_handoff(
                    from_agent_id=by_name[from_name],
                    to_agent_id=by_name[to_name],
                    description=desc,
                    max_parallel=max_parallel,
                )

    asyncio.run(_edges())
    return by_name


@pytest.fixture
def auth_client(get_token_for_user, db):
    from accounts.models import User
    from rest_framework.test import APIClient

    user = User.objects.create_user(username="ps-catalog-user", password="secret123")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    return client


@pytest.mark.django_db(transaction=True)
def test_ps01_specialists_registered_with_export_document():
    by_name = _seed_specialists()
    catalog = CatalogService(instance_id=PLAN_INSTANCE_ID)
    agents = {a["name"]: a for a in catalog.list_agents()}
    for name in SPECIALISTS:
        assert name in agents, f"missing specialist {name}"
        assert name in by_name
        tools = agents[name].get("tool_set") or []
        assert "export_document" in tools, f"{name} must own export_document"
    assert agents["payroll_controller"]["role"] == "domain_specialist"
    assert agents["compliance_auditor"]["role"] == "critic"
    assert agents["workforce_researcher"]["role"] == "researcher"
    assert agents["finance_packager"]["role"] == "planner"


@pytest.mark.django_db(transaction=True)
def test_ps02_orchestrator_handoffs_to_specialists(auth_client):
    by_name = _seed_specialists()
    resp = auth_client.get(f"{BASE}/topology/")
    assert resp.status_code == 200
    body = resp.json()
    names = {n["name"] for n in body["nodes"]}
    for name in SPECIALISTS:
        assert name in names

    orch = by_name["orchestrator"]
    edges = {(e["from"], e["to"]) for e in body["edges"]}
    for specialist in SPECIALISTS:
        sid = by_name[specialist]
        assert (orch, sid) in edges, f"missing orchestrator → {specialist}"
        assert (sid, orch) in edges, f"missing {specialist} → orchestrator"


# ── PS-03 pack coerce ─────────────────────────────────────────────────────


def test_ps03_infer_pack_from_board_pack_brief():
    assert _infer_export_format("Export a board pack for GOFSCO payroll") == "pack"
    assert _infer_export_format("give me all four formats") == "pack"
    assert _infer_export_format("Word and Excel and PDF chart") == "pack"


def test_ps03_coerce_pack_intent_to_export_document():
    s = PlanStep(
        step_id=4,
        intent="Export board pack as Word, Excel, PDF, and PNG chart",
        tool_name=None,
    )
    _coerce_export_steps([s])
    assert s.tool_name == "export_document"
    assert s.tool_args["format"] == "pack"


def test_ps03_ensure_pack_appended_when_brief_asks_board_pack():
    steps = [
        PlanStep(step_id=0, intent="Fetch headcount", tool_name="call_host_api"),
        PlanStep(step_id=1, intent="Summarize GOSI", tool_name=None),
    ]
    _ensure_export_deliverable(
        "Run October payroll variance and export a board pack (Word + Excel + PDF + PNG)",
        steps,
    )
    assert steps[-1].tool_name == "export_document"
    assert steps[-1].tool_args["format"] == "pack"


def test_ps03_pdf_only_stays_pdf():
    s = PlanStep(step_id=2, intent="Export findings as a PDF brief", tool_name=None)
    _coerce_export_steps([s])
    assert s.tool_args["format"] == "pdf"


# ── PS-04 template shape (seed specs) ──────────────────────────────────────


def test_ps04_seed_templates_end_in_export_pack():
    from ai.management.commands.seed_complex_agent_demos import TEMPLATE_SPECS

    assert len(TEMPLATE_SPECS) >= 3
    for spec in TEMPLATE_SPECS:
        steps = spec["plan_json"]["steps"]
        export_steps = [s for s in steps if s.get("tool_name") == "export_document"]
        assert export_steps, f"{spec['name']} missing export_document"
        assert export_steps[-1]["tool_args"]["format"] == "pack"
        assert "table" in export_steps[-1]["tool_args"]
        assert export_steps[-1]["tool_args"].get("content")
