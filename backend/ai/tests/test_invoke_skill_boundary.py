"""P3-10 — ``invoke_skill`` reimplementation: executable skills route through
the host command boundary.

Covers the seam at three layers:

  * **Admission** — ``sql_macro`` / ``api_call`` (legacy executable-body kinds)
    are refused by the structural critic before harmlessness runs.
  * **Registry** — ``ProcessRegistry.resolve`` resolves ``process_id@version``
    (exact version) and fails closed on unknown refs.
  * **Invocation** — an executable skill whose body carries ``process_ref``
    routes through ``CarbonHostExecutor.invoke_skill_via_boundary``, producing
    a governed run + a persisted PDP decision.  Guidance skills stay data-only
    (no run, no PDP row), and a legacy kind that reaches ``invoke_skill`` is
    refused fail-closed.

Run (from ``backend/``)::

    python -m pytest ai/tests/test_invoke_skill_boundary.py -q -m "not live"
"""
from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from django.test import override_settings

from accounts.models import User
from ai.engine.agent.tools import execute_invoke_skill
from ai.engine.core.config import get_settings
from ai.engine.core.models import Skill
from ai.engine.skills.gate import structural_critic
from ai.host_executor import CarbonHostExecutor
from ai.models.capability import Capability
from ai.models.core import Run
from ai.models.pdp import PolicyDecisionRow
from ai.models.process import ProcessDefinition
from ai.plans_service import PlansService
from ai.registry_service import ProcessRegistry, RegistryNotFoundError
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


async def _seed_skill(
    instance_name: str,
    *,
    kind: str,
    status: str = "instance_promoted",
    body: str = "{}",
) -> tuple[str, str, str]:
    """Seed an active instance + one skill via the engine Store.

    Returns ``(instance_id, skill_id, name)``.
    """
    from ai.engine.core.models import Instance, generate_uuid
    from ai.store import get_store

    instance_id = generate_uuid()
    skill_id = generate_uuid()
    name = "seeded_skill"
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
            description="Seeded skill",
            signature="{}",
            body=body,
            kind=kind,
            status=status,
            author_user_id="system",
        ))
        await db.commit()

    return instance_id, skill_id, name


class _FakeExecutor:
    """Minimal host executor exposing the session + a non-empty token."""

    def __init__(self, db):
        self.db = db
        self.user_token = "test-token"


def _seed_process(process_id: str, version: str, *, steps: list) -> None:
    ProcessDefinition.objects.create(
        process_id=process_id,
        version=version,
        owner="owner",
        status="active",
        definition={
            "id": process_id,
            "version": version,
            "owner": "owner",
            "status": "active",
            "steps": steps,
        },
    )


# ── 1. Admission: legacy executable-body kinds are refused ───────────────


def test_sql_macro_admission_rejected():
    skill = Skill(
        kind="sql_macro", name="legacy_sql", body=json.dumps({"sql": "DROP TABLE x"}),
    )
    verdict = asyncio.run(structural_critic(skill, db=None))
    assert verdict.rejected is True
    assert any(f.startswith("legacy_executable_body_kind") for f in verdict.flags)


def test_api_call_admission_rejected():
    skill = Skill(
        kind="api_call", name="legacy_api",
        body=json.dumps({"method": "POST", "path": "/rules"}),
    )
    verdict = asyncio.run(structural_critic(skill, db=None))
    assert verdict.rejected is True
    assert any(f.startswith("legacy_executable_body_kind") for f in verdict.flags)


# ── 2. Registry: resolve process_id@version ──────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_registry_resolve_exact_version():
    _seed_process("test.resolve", "1.0", steps=[])
    _seed_process("test.resolve", "2.0", steps=[])

    registry = ProcessRegistry()
    assert registry.resolve("test.resolve@1.0").version == "1.0"
    assert registry.resolve("test.resolve@2.0").version == "2.0"
    # Bare ref resolves to the latest definition for that id.
    assert registry.resolve("test.resolve").process_id == "test.resolve"

    with pytest.raises(RegistryNotFoundError):
        registry.resolve("test.resolve@9.9")
    with pytest.raises(RegistryNotFoundError):
        registry.resolve("missing.process")


# ── 3. Executable skill → governed run + persisted PDP decision ──────────


@pytest.mark.django_db(transaction=True)
def test_executable_skill_invoke_produces_run_and_pdp_row(monkeypatch):
    user = User.objects.create_user(username="invoker", password="secret123")
    _seed_process(
        "test.exec", "1.0",
        steps=[
            {
                "id": "validate",
                "kind": "command",
                "capability": "dq.rule.validate",
                "autonomy": "act_notify",
                "consent": False,
            }
        ],
    )
    Capability.objects.create(
        capability_id="dq.rule.validate",
        host_action="dq.validate_rule",
        approval_requirements={},
        version="1.0",
    )

    def fake_create_plan(self, user, brief, conversation_id=""):
        run = Run.objects.create(
            instance_id="plan-instance",
            conversation_id=conversation_id or "",
            user_message=brief,
            host_user_id=str(user.pk),
            status="pending_approval",
        )
        return {"id": run.id, "status": run.status, "brief": brief}

    monkeypatch.setattr(PlansService, "create_plan", fake_create_plan)

    ex = CarbonHostExecutor(
        db=None,
        instance_config={},
        user_token="inproc:carbon:invoker",
        host_user_id=str(user.pk),
    )

    result = asyncio.run(
        ex.invoke_skill_via_boundary(
            skill_name="release_rule",
            process_ref="test.exec@1.0",
            args={"rule_id": "r1"},
            instance_id="i1",
            host_user_id=str(user.pk),
            author_user_id=str(user.pk),
        )
    )

    assert result["status"] == "executed"
    assert result["run_id"]
    assert result["process_id"] == "test.exec"
    assert result["process_version"] == "1.0"
    assert result["boundary_outcome"] == "executed"
    assert result["pdp_decision"] == "allow"
    assert result["error"] is None

    run = Run.objects.get(id=result["run_id"])
    assert run.definition_id == "test.exec"
    assert run.definition_version == "1.0"

    rows = list(PolicyDecisionRow.objects.filter(action="invoke_skill"))
    assert len(rows) == 1
    assert rows[0].principal == str(user.pk)
    assert rows[0].decision == "allow"
    assert rows[0].stage == "pdp"


# ── 4. Guidance skill stays data-only (no run, no PDP row) ───────────────


@pytest.mark.django_db(transaction=True)
def test_guidance_skill_invoke_returns_data_only(django_store, cfg):
    instance_id, _skill_id, name = asyncio.run(
        _seed_skill(
            f"invoke-guidance-{uuid4().hex[:8]}",
            kind="prompt_template",
            body=json.dumps({"user_prompt_template": "Summarize {topic}"}),
        )
    )

    async def _invoke():
        from ai.store import get_store

        factory = get_store().get_session_factory()
        async with factory() as db:
            return await execute_invoke_skill(
                skill_name=name,
                args={"topic": "DQ rules"},
                instance_id=instance_id,
                executor=_FakeExecutor(db),
            )

    result = asyncio.run(_invoke())

    assert "error" not in result
    assert result["kind"] == "prompt_template"
    assert result["result"]["kind"] == "prompt_template"
    assert result["result"]["rendered_prompt"] == "Summarize DQ rules"

    # Data-only: no governed run and no PDP decision were produced.
    assert Run.objects.count() == 0
    assert PolicyDecisionRow.objects.count() == 0


# ── 5. Legacy executable-body kind reaching invoke_skill is refused ──────


@pytest.mark.django_db(transaction=True)
def test_legacy_kind_reaches_invoke_refused(django_store, cfg):
    instance_id, _skill_id, name = asyncio.run(
        _seed_skill(
            f"invoke-legacy-{uuid4().hex[:8]}",
            kind="sql_macro",
            body=json.dumps({"sql": "SELECT 1"}),
        )
    )

    async def _invoke():
        from ai.store import get_store

        factory = get_store().get_session_factory()
        async with factory() as db:
            return await execute_invoke_skill(
                skill_name=name,
                instance_id=instance_id,
                executor=_FakeExecutor(db),
            )

    result = asyncio.run(_invoke())

    assert result == {"error": "skill kind 'sql_macro' is not executable"}
    assert Run.objects.count() == 0
    assert PolicyDecisionRow.objects.count() == 0
