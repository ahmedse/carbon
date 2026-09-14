"""P3-12 — Pilot end-to-end acceptance tests (backend).

The five pilot "done-when" scenarios, authored as tests only (no production
code changes):

1. **Restart survival** — durable plan/registry state is byte-for-byte the
   same when read back through a *fresh* service instance.
2. **Concurrent edit invalidates approval** — a grant minted against
   revision/version N never authorizes N+1 (P3-06 fail-closed).
3. **Duplicate submit → no duplicate effect** — the same submit/command is
   refused or deduplicated so the effect fires exactly once.
4. **Revoked permission blocks publish** — deactivating ``ai:publisher``
   turns a previously-working publish into a 403, leaving the document in
   ``review``.
5. **Self-approval refused** — a non-superuser publisher who is also the
   author cannot self-publish (separation of duties); a superuser can.

All tests are ``not live``-compatible: no LLM, no network, no SQLAlchemy.
Run from ``backend/``:

    ../.venv/bin/python -m pytest ai/tests/pilot/test_pilot_e2e.py -q -m "not live"
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.constants import AI_PROCESS_OWNER_GROUP, AI_PUBLISHER_GROUP
from ai.command_boundary import Command, CommandBoundary
from ai.engine.ports import Decision
from ai.engine.ports.domain import load_domain_pack
from ai.models.approval import ApprovalGrant, canonicalize_args
from ai.models.capability import default_pack_dir
from ai.models.core import Run, RunStep
from ai.models.process import STATUS_DRAFT, STATUS_REVIEW, ProcessDefinition
from ai.plans_service import PLAN_INSTANCE_ID, PlansService
from ai.protocol import Scope
from ai.tests.conftest import grant_role, make_user

pytestmark = pytest.mark.django_db(transaction=True)

PACK_DIR = default_pack_dir()
PROCESS_ID = "dq.rule.release"


# ── Helpers ────────────────────────────────────────────────────────────────


def _pilot_document(**overrides) -> dict:
    """Load the pilot ``dq.rule.release`` definition from the domain pack."""
    pack = load_domain_pack(PACK_DIR)
    doc = next(p for p in pack.processes() if p.get("id") == PROCESS_ID)
    result = dict(doc)
    result.update(overrides)
    return result


def _url(name: str, **kwargs) -> str:
    return reverse(f"ai-registry-{name}", kwargs=kwargs)


def _owner(username: str = "owner"):
    user = make_user(username)
    grant_role(user, group_name=AI_PROCESS_OWNER_GROUP)
    return user


def _publisher(username: str = "publisher"):
    user = make_user(username)
    grant_role(user, group_name=AI_PUBLISHER_GROUP)
    return user


def _create_draft(api_client, user, document=None):
    api_client.force_authenticate(user=user)
    return api_client.post(
        _url("list"), data=document or _pilot_document(), format="json"
    )


def _latest_definition() -> ProcessDefinition | None:
    return (
        ProcessDefinition.objects.filter(process_id=PROCESS_ID)
        .order_by("-created_at")
        .first()
    )


def _clear_capability_cache(user) -> None:
    """Drop the request-level capability cache so a revocation is re-read."""
    if hasattr(user, "_cached_capabilities"):
        delattr(user, "_cached_capabilities")


# ── Offline boundary fakes (scenario 3) ────────────────────────────────────


class _AllowPDP:
    async def decide(self, principal, action, objects, process_state=None,
                     autonomy="human_only", budget=None, time=None) -> dict:
        return {"decision": Decision.ALLOW, "reason": "test allow",
                "policy_version": "v1"}


class _CountingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, command: Command) -> dict:
        self.calls += 1
        return {"ok": True}


class _AlwaysEligible:
    async def __call__(self, command: Command) -> bool:
        return True


# ── 1. Restart survival ────────────────────────────────────────────────────


def test_plan_survives_service_restart():
    """A run persisted by one service instance is read back identically by a
    brand-new ``PlansService`` (simulating a process restart)."""
    user = _owner("restart-plan-owner")
    run = Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id=PLAN_INSTANCE_ID,
        conversation_id="conv-restart",
        host_user_id=str(user.pk),
        user_message="Recompute the pilot release",
        status="pending_approval",
        run_state="awaiting_approval",
        plan_json={"steps": [{"step_id": 0, "intent": "validate rule"}]},
    )
    RunStep.objects.create(
        run_id=run.id,
        step_index=0,
        intent="validate rule",
        status="pending",
        step_state="planned",
    )

    # A fresh service instance reads the same durable row + steps.
    plan = PlansService().get_plan(user, run.id)

    assert plan["id"] == run.id
    assert plan["status"] == "pending_approval"
    assert plan["brief"] == "Recompute the pilot release"
    assert plan["conversation_id"] == "conv-restart"
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["step_id"] == 0
    assert plan["steps"][0]["intent"] == "validate rule"
    assert plan["steps"][0]["status"] == "pending"

    # The durable row itself is unchanged.
    run.refresh_from_db()
    assert run.status == "pending_approval"
    assert run.run_state == "awaiting_approval"


def test_registry_definition_survives_service_restart(api_client):
    """A registry draft is durable: a fresh read (post-restart) returns the
    same owner/version/status."""
    owner = _owner("restart-registry-owner")
    resp = _create_draft(api_client, owner)
    assert resp.status_code == 201
    created = resp.json()

    # Fresh DB read — the equivalent of a new service process querying.
    persisted = _latest_definition()
    assert persisted is not None
    assert persisted.owner == owner.username
    assert persisted.host_user_id == str(owner.pk)
    assert persisted.version == created["version"]
    assert persisted.status == STATUS_DRAFT
    assert persisted.definition["status"] == "draft"

    # A fresh authenticated HTTP read returns the same shape.
    api_client.force_authenticate(user=owner)
    again = api_client.get(_url("detail", pk=PROCESS_ID))
    assert again.status_code == 200
    assert again.json()["status"] == "draft"
    assert again.json()["version"] == created["version"]


# ── 2. Concurrent edit invalidates approval ───────────────────────────────


def test_concurrent_edit_invalidates_approval():
    """A grant pinned to revision 7 / version 1 must never authorize a
    concurrently-edited revision 8 / version 2 (P3-06 fail-closed)."""
    grant = ApprovalGrant.objects.create(
        capability="dq.rule.publish",
        process_version="1",
        capability_version="c1",
        canonical_args=canonicalize_args({"rule_id": "rule-1"}),
        object_revisions={"rule-1": 7},
        evidence_digest="sha256:abc",
        object_id="rule-1",
        object_type="rule",
        process_instance="pi-1",
        expires_at=timezone.now() + timedelta(hours=1),
        status="active",
        granted_by="publisher@example.com",
    )

    def _find(*, process_version: str, object_revisions: dict):
        return ApprovalGrant.find_active(
            capability="dq.rule.publish",
            process_version=process_version,
            capability_version="c1",
            canonical_args=canonicalize_args({"rule_id": "rule-1"}),
            object_revisions=object_revisions,
            evidence_digest="sha256:abc",
            object_id="rule-1",
            object_type="rule",
            process_instance="pi-1",
        )

    # Baseline: the exact pinned tuple still authorizes.
    assert _find(process_version="1", object_revisions={"rule-1": 7}) == grant

    # Concurrent edit 1: object revision bumped → grant fails closed.
    assert _find(process_version="1", object_revisions={"rule-1": 8}) is None

    # Concurrent edit 2: process version bumped → grant fails closed.
    assert _find(process_version="2", object_revisions={"rule-1": 7}) is None


# ── 3. Duplicate submit → no duplicate effect ─────────────────────────────


def test_duplicate_submit_has_no_duplicate_effect(api_client):
    """Submitting the same definition twice transitions it exactly once and
    never creates a duplicate row."""
    owner = _owner("dup-submit-owner")
    _create_draft(api_client, owner)
    api_client.force_authenticate(user=owner)

    first = api_client.post(_url("submit", pk=PROCESS_ID))
    assert first.status_code == 200
    assert first.json()["status"] == "review"

    second = api_client.post(_url("submit", pk=PROCESS_ID))
    assert second.status_code == 400

    # Exactly one definition row, still in review — no duplicate effect.
    rows = ProcessDefinition.objects.filter(process_id=PROCESS_ID)
    assert rows.count() == 1
    assert rows.get().status == "review"


@pytest.mark.asyncio
async def test_duplicate_command_idempotency_key_executes_once():
    """The boundary replays the stored outcome for a repeated idempotency key
    and never re-runs the effect (exactly one execution)."""
    executor = _CountingExecutor()
    store: dict = {}
    boundary = CommandBoundary(
        pdp=_AllowPDP(),
        executor=executor,
        tool_catalog={"dq.rule.release": {}},
        eligibility_checker=_AlwaysEligible(),
        idempotency_store=store,
    )
    scope = Scope(
        user_identifier="alice",
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=True,
    )

    def _command() -> Command:
        return Command(
            principal="alice",
            scope=scope,
            action="dq.rule.release",
            tool="dq.rule.release",
            params={"rule_id": "rule-1"},
            objects=["rule-1"],
            requires_confirmation=False,
            idempotency_key="submit:rule-1:rev-7",
        )

    first = await boundary.execute(_command())
    second = await boundary.execute(_command())

    assert first.status == "executed"
    assert second.status == "executed"
    assert first.result == {"ok": True}
    assert second.result == {"ok": True}
    # The executor ran exactly once despite two submits.
    assert executor.calls == 1


# ── 4. Revoked permission blocks publish ──────────────────────────────────


def test_revoked_publisher_permission_blocks_publish(api_client):
    """A publisher who can publish while ``ai:publisher`` is active is refused
    with 403 after the role is revoked, and the document stays in review."""
    author = _owner("revoke-author")
    publisher = make_user("revoke-publisher")
    publisher_role = grant_role(publisher, group_name=AI_PUBLISHER_GROUP)

    # Baseline: the publisher CAN publish while the role is active.
    _create_draft(api_client, author)
    api_client.force_authenticate(user=author)
    api_client.post(_url("submit", pk=PROCESS_ID))

    api_client.force_authenticate(user=publisher)
    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    # Author starts the next change as a fresh draft and submits it.
    api_client.force_authenticate(user=author)
    assert api_client.post(
        _url("list"), data=_pilot_document(), format="json"
    ).status_code == 201
    api_client.post(_url("submit", pk=PROCESS_ID))

    # Revoke the publisher's ai:publisher capability mid-flight.
    publisher_role.is_active = False
    publisher_role.save(update_fields=["is_active"])
    _clear_capability_cache(publisher)

    api_client.force_authenticate(user=publisher)
    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 403

    # The publish was blocked — the latest definition is still in review.
    latest = _latest_definition()
    assert latest is not None
    assert latest.status == "review"


# ── 5. Self-approval refused ──────────────────────────────────────────────


def test_self_approval_refused(api_client):
    """A non-superuser who is both author and publisher cannot self-publish."""
    author = _owner("self-approve-author")
    grant_role(author, group_name=AI_PUBLISHER_GROUP)  # author also a publisher
    _create_draft(api_client, author)
    api_client.force_authenticate(user=author)
    api_client.post(_url("submit", pk=PROCESS_ID))

    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden"

    # Refused self-publish leaves the document in review (no partial effect).
    latest = _latest_definition()
    assert latest is not None
    assert latest.status == "review"


def test_superuser_can_self_publish(api_client):
    """The separation-of-duties rule targets authors, not superusers."""
    root = make_user("self-approve-root", superuser=True)
    _create_draft(api_client, root)
    api_client.force_authenticate(user=root)
    api_client.post(_url("submit", pk=PROCESS_ID))

    resp = api_client.post(_url("publish", pk=PROCESS_ID))
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
