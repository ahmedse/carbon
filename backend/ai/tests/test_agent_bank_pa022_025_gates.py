"""Agent bank PA-022…025 — SoD / kill-switch / human_only / grant expiry.

Extends existing oracles only (test_run_machine, test_grant, Nibras process
YAML, registry SoD). Does **not** rewrite PDP, PlansService, or steward
journeys — bank IDs map to proven seams for CI.

Source: docs/pulse/QA-CHAT-AGENTIC-SCENARIO-BANK.md §B3

Run::

    cd backend && ../.venv/bin/python -m pytest ai/tests/test_agent_bank_pa022_025_gates.py -q
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.constants import AI_PROCESS_OWNER_GROUP, AI_PUBLISHER_GROUP
from accounts.models import User
from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports.domain import load_domain_pack
from ai.grant import resolve_grant
from ai.models.approval import ApprovalGrant, canonicalize_args
from ai.models.core import Run
from ai.models.process import ProcessDefinition
from ai.pdp import PDP
from ai.plans_service import PlansService
from ai.protocol import Scope
from ai.registry_service import ProcessRegistry
from ai.tests.conftest import grant_role, make_user

PACK_DIR = Path(settings.BASE_DIR).parent / "domain_packs" / "nibras"

# Processes whose human gates declare SoD role pairs (PA-022 dial contract).
SOD_PROCESSES = (
    "leave.request.lifecycle",
    "loan.request.lifecycle",
    "payroll.run.lifecycle",
    "employee.onboarding.lifecycle",
    "gosi_wps.sif.lifecycle",
)


def _doc(process_id: str) -> dict:
    pack = load_domain_pack(PACK_DIR)
    return dict(next(p for p in pack.processes() if p.get("id") == process_id))


# ── PA-022 Self-approval SoD forbidden ────────────────────────────────────


@pytest.mark.parametrize("process_id", SOD_PROCESSES)
def test_pa022_process_declares_sod_on_human_gates(process_id):
    """PA-022 dial: human_only steps carry separation_of_duties (≥2 roles)."""
    doc = _doc(process_id)
    human = [s for s in doc["steps"] if s.get("autonomy") == "human_only"]
    assert human, f"{process_id}: expected human_only gate"
    for step in human:
        sod = step.get("separation_of_duties") or []
        assert len(sod) >= 2, (
            f"{process_id}.{step['id']}: SoD roles required, got {sod!r}"
        )


def test_pa022_payroll_refuse_if_self_approve():
    """PA-022 policy: payroll refuses when preparer equals approver."""
    doc = _doc("payroll.run.lifecycle")
    refuse = doc.get("policies", {}).get("refuse_if") or []
    assert any("preparer equals approver" in r for r in refuse)


@pytest.mark.django_db(transaction=True)
def test_pa022_registry_self_publish_refused(monkeypatch):
    """PA-022 runtime: author==publisher cannot self-publish (existing SoD)."""
    monkeypatch.setattr(
        "ai.models.process._default_known_capabilities",
        lambda: {"noop.capability"},
    )
    pid = f"proc.pa022.{uuid4().hex[:8]}"
    author = make_user(f"pa022-author-{uuid4().hex[:6]}")
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
        "objective": {"predicate": "pa022 sod"},
    }
    client = APIClient()
    client.force_authenticate(user=author)
    create = client.post(reverse("ai-registry-list"), data=doc, format="json")
    assert create.status_code in (200, 201), create.content
    submit = client.post(reverse("ai-registry-submit", kwargs={"pk": pid}))
    assert submit.status_code == 200, submit.content
    publish = client.post(reverse("ai-registry-publish", kwargs={"pk": pid}))
    assert publish.status_code == 403, publish.content
    assert publish.json().get("error") == "forbidden"


# ── PA-023 Kill switch refuses with reason ────────────────────────────────


@pytest.mark.django_db
def test_pa023_kill_switch_preflight_refuses():
    """PA-023: kill switch blocks effect; decision=refuse; kill_switched_at set.

    Mirrors ``test_run_machine.test_kill_switch_preflight_blocks_effect`` under
    a bank ID — same PlansService.preflight + ProcessRegistry path.
    """
    user = User.objects.create_user(
        username=f"pa023-owner-{uuid4().hex[:6]}", password="secret123"
    )
    operator = User.objects.create_superuser(
        username=f"pa023-op-{uuid4().hex[:6]}", password="secret123"
    )
    pid = f"proc.pa023.{uuid4().hex[:8]}"

    ProcessDefinition.objects.create(
        process_id=pid,
        version="v1",
        owner="pa023",
        status="active",
        definition={
            "id": pid,
            "version": "v1",
            "owner": "pa023",
            "status": "active",
            "steps": [],
            "kill_switch": False,
        },
    )
    run = Run.objects.create(
        instance_id="pa023",
        conversation_id=f"conv-{uuid4().hex[:8]}",
        user_message="run",
        host_user_id=str(user.pk),
        definition_id=pid,
    )

    ok = PlansService.preflight(run, action="run", autonomy="auto")
    assert ok["allowed"] is True

    ProcessRegistry().set_kill_switch(pid, True, operator)
    blocked = PlansService.preflight(run, action="run", autonomy="auto")
    assert blocked["allowed"] is False
    assert blocked["decision"] == "refuse"
    run.refresh_from_db()
    assert run.kill_switched_at is not None

    # Restore — do not leave killed process for other tests.
    ProcessRegistry().set_kill_switch(pid, False, operator)


# ── PA-024 human_only never auto-executes ─────────────────────────────────


@pytest.mark.django_db
def test_pa024_human_only_preflight_asks_not_allows():
    """PA-024: autonomy=human_only → preflight ask (blocked), never allow."""
    user = User.objects.create_user(
        username=f"pa024-{uuid4().hex[:6]}", password="secret123"
    )
    run = Run.objects.create(
        instance_id="pa024",
        conversation_id=f"conv-{uuid4().hex[:8]}",
        user_message="mutate",
        host_user_id=str(user.pk),
    )
    result = PlansService.preflight(run, action="run", autonomy="human_only")
    assert result["allowed"] is False
    assert result["decision"] == "ask"


@pytest.mark.parametrize(
    "process_id,step_id",
    [
        ("payroll.run.lifecycle", "commit"),
        ("leave.request.lifecycle", "review"),
        ("gosi_wps.sif.lifecycle", "submit"),
    ],
)
def test_pa024_nibras_irreversible_steps_are_human_only(process_id, step_id):
    """PA-024 dial: irreversible Nibras steps stay human_only (never auto)."""
    doc = _doc(process_id)
    step = next(s for s in doc["steps"] if s["id"] == step_id)
    assert step["autonomy"] == "human_only"
    assert step["autonomy"] != "auto"


# ── PA-025 Grant expired mid-run → stop / re-request ──────────────────────


@pytest.mark.django_db(transaction=True)
def test_pa025_expired_grant_is_inert():
    """PA-025: expired ApprovalGrant is not find_active (fail-closed)."""
    ApprovalGrant.objects.create(
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        canonical_args=canonicalize_args({"audience": "public"}),
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
        expires_at=timezone.now() - timedelta(seconds=1),
        status="active",
        granted_by="pa025@example.com",
    )
    found = ApprovalGrant.find_active(
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        canonical_args=canonicalize_args({"audience": "public"}),
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
    )
    assert found is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pa025_expired_grant_boundary_refuses_effect():
    """PA-025: CommandBoundary grant stage refuses when grant is expired."""
    await sync_to_async(ApprovalGrant.objects.create, thread_sensitive=True)(
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        canonical_args=canonicalize_args({"audience": "public"}),
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
        expires_at=timezone.now() - timedelta(seconds=1),
        status="active",
        granted_by="pa025-boundary@example.com",
    )

    class _Never:
        calls = 0

        async def __call__(self, command):
            self.calls += 1
            return {"ok": True}

    executor = _Never()
    boundary = CommandBoundary(
        pdp=PDP(),
        grant_resolver=resolve_grant,
        tool_catalog={"read": {}},
        executor=executor,
    )
    scope = Scope(
        user_identifier="u1",
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=True,
    )
    cmd = Command(
        principal="pa025-actor",
        scope=scope,
        action="read",
        tool="read",
        params={"audience": "public"},
        objects=["tbl"],
        requires_confirmation=False,
        requires_grant=True,
        capability="ai:publisher",
        process_version="v3",
        capability_version="c1",
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
        autonomy="human_only",
    )
    outcome = await boundary.execute(cmd)
    assert outcome.status == "refused"
    assert outcome.stages[-1] == "grant"
    assert "ApprovalGrant" in (outcome.error or "")
    assert executor.calls == 0
