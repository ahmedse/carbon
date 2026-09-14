"""P3-09 — Human Task Inbox (durable approval tasks).

Covers the six "done-when" behaviours of the durable approval-task inbox:

1. approving a task mints a bound :class:`ApprovalGrant` pinning the exact
   ``(objects+revisions, evidence, expiry, …)`` tuple;
2. an expired task is refused (and marked expired) — never approved;
3. a principal without the task's ``required_authority`` is refused fail-closed;
4. declining a task never mints a grant;
5. the inbox item **survives restart** (a fresh service instance reads the same
   pending task from the DB with identical fields);
6. re-approving an already-approved task is idempotent (no second grant).

It also exercises the boundary ``task_enqueuer`` seam (P3-09 deliverable 4):
with no matching grant the boundary defers to the inbox instead of hard-refusing.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from ai.command_boundary import Command, CommandBoundary
from ai.grant import resolve_grant
from ai.models.approval import STATUS_ACTIVE, ApprovalGrant
from ai.models.human_task import (
    IRREVERSIBLE,
    STATUS_APPROVED,
    STATUS_DECLINED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    HumanTask,
)
from ai.pdp import PDP
from ai.protocol import Scope
from ai.task_inbox import (
    TaskExpired,
    TaskInbox,
    UnauthorizedApprover,
    enqueue_inbox_task,
)

pytestmark = pytest.mark.django_db(transaction=True)


# ── Helpers ────────────────────────────────────────────────────────────────

def _mk_task(inbox: TaskInbox, *, expires_at=None, **overrides: Any) -> HumanTask:
    base: dict[str, Any] = dict(
        consequence="Delete table customers",
        objects_revisions={"tbl-customers": 7},
        before={"rows": 100},
        after={"rows": 0},
        evidence={"report": "audit-1"},
        reversibility=IRREVERSIBLE,
        required_authority="ai:operator",
        expires_at=expires_at or (timezone.now() + timedelta(hours=1)),
        capability="ai:operator",
        process_version="v1",
        capability_version="c1",
        canonical_args={"table": "customers"},
        object_id="tbl-customers",
        object_type="table",
        process_instance="pi-1",
        effect_limits={"max_rows": 0},
        alternatives=["archive the table instead"],
    )
    base.update(overrides)
    return inbox.create_task(**base)


def _scope() -> Scope:
    return Scope(
        user_identifier="u1",
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=True,
    )


class _CountingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, command: Command) -> Any:
        self.calls += 1
        return {"ok": True}


# ── 1. approve mints a bound ApprovalGrant ────────────────────────────────

def test_approve_mints_bound_grant(create_user):
    admin = create_user("admin", is_superuser=True)
    inbox = TaskInbox()
    task = _mk_task(inbox)

    approved = inbox.approve(admin, task.id)

    assert approved.status == STATUS_APPROVED
    assert approved.grant_id
    assert approved.decided_by == "admin"
    assert approved.decided_at is not None

    # Exactly one grant, bound to the task's exact pinned tuple.
    assert ApprovalGrant.objects.count() == 1
    grant = ApprovalGrant.objects.get(pk=approved.grant_id)
    assert grant.status == STATUS_ACTIVE
    assert grant.granted_by == "admin"
    assert grant.capability == task.capability == "ai:operator"
    assert grant.process_version == task.process_version == "v1"
    assert grant.capability_version == task.capability_version == "c1"
    assert grant.canonical_args == task.canonical_args == {"table": "customers"}
    assert grant.object_revisions == task.objects_revisions_json == {"tbl-customers": 7}
    assert grant.evidence_digest == task.evidence_digest
    assert grant.effect_limits == task.effect_limits == {"max_rows": 0}
    assert grant.object_id == task.object_id == "tbl-customers"
    assert grant.object_type == task.object_type == "table"
    assert grant.process_instance == task.process_instance == "pi-1"
    assert grant.expires_at == task.expires_at


# ── 2. expired task is refused (and marked expired) ──────────────────────

def test_expired_task_refuses(create_user):
    admin = create_user("admin", is_superuser=True)
    inbox = TaskInbox()
    task = _mk_task(inbox, expires_at=timezone.now() - timedelta(seconds=1))

    with pytest.raises(TaskExpired):
        inbox.approve(admin, task.id)

    task.refresh_from_db()
    assert task.status == STATUS_EXPIRED
    assert task.grant_id is None
    assert ApprovalGrant.objects.count() == 0


# ── 3. wrong authority is refused fail-closed ────────────────────────────

def test_wrong_authority_refuses_fail_closed(create_user):
    inbox = TaskInbox()
    task = _mk_task(inbox, required_authority="ai:operator")

    plain = create_user("plain")  # no roles → no ai:operator capability

    with pytest.raises(UnauthorizedApprover):
        inbox.approve(plain, task.id)

    task.refresh_from_db()
    assert task.status == STATUS_PENDING
    assert task.grant_id is None
    assert ApprovalGrant.objects.count() == 0


def test_authority_holder_can_approve(create_user, create_scoped_role):
    inbox = TaskInbox()
    task = _mk_task(inbox, required_authority="ai:operator")

    operator = create_user("operator")
    create_scoped_role(operator, "ai_operator_group")  # global ai:operator role

    approved = inbox.approve(operator, task.id)

    assert approved.status == STATUS_APPROVED
    assert ApprovalGrant.objects.count() == 1
    assert ApprovalGrant.objects.get().granted_by == "operator"


# ── 4. decline mints no grant ────────────────────────────────────────────

def test_decline_no_grant(create_user):
    admin = create_user("admin", is_superuser=True)
    inbox = TaskInbox()
    task = _mk_task(inbox)

    declined = inbox.decline(admin, task.id, reason="too risky")

    assert declined.status == STATUS_DECLINED
    assert declined.decline_reason == "too risky"
    assert declined.grant_id is None
    assert ApprovalGrant.objects.count() == 0


# ── 5. inbox item survives restart ───────────────────────────────────────

def test_inbox_survives_restart(create_user):
    admin = create_user("admin", is_superuser=True)
    inbox_a = TaskInbox()
    task = _mk_task(inbox_a)
    task_id = task.id

    # A brand-new service instance (process restart) reads the same row back.
    inbox_b = TaskInbox()
    reloaded = inbox_b.get(task_id)

    assert reloaded.status == STATUS_PENDING
    assert reloaded.consequence == task.consequence
    assert reloaded.objects_revisions_json == task.objects_revisions_json
    assert reloaded.before_json == task.before_json
    assert reloaded.after_json == task.after_json
    assert reloaded.evidence_json == task.evidence_json
    assert reloaded.evidence_digest == task.evidence_digest
    assert reloaded.reversibility == task.reversibility
    assert reloaded.required_authority == task.required_authority
    assert reloaded.expires_at == task.expires_at
    assert reloaded.alternatives_json == task.alternatives_json
    assert reloaded.capability == task.capability

    # And it is still approvable after the "restart".
    approved = inbox_b.approve(admin, task_id)
    assert approved.status == STATUS_APPROVED
    assert ApprovalGrant.objects.count() == 1


# ── 6. duplicate approve is idempotent (no second grant) ─────────────────

def test_duplicate_approve_idempotent(create_user):
    admin = create_user("admin", is_superuser=True)
    inbox = TaskInbox()
    task = _mk_task(inbox)

    first = inbox.approve(admin, task.id)
    second = inbox.approve(admin, task.id)

    assert second.grant_id == first.grant_id
    assert second.status == STATUS_APPROVED
    assert ApprovalGrant.objects.count() == 1


# ── Boundary enqueuer seam (deliverable 4) ────────────────────────────────

@pytest.mark.asyncio
async def test_boundary_defers_to_inbox_when_no_grant():
    captured: dict[str, Any] = {}

    async def _fake_enqueuer(command: Command) -> str:
        captured["command"] = command
        return "task-123"

    boundary = CommandBoundary(
        pdp=PDP(),
        grant_resolver=resolve_grant,  # no grant minted → returns None
        task_enqueuer=_fake_enqueuer,
        tool_catalog={"read": {}},
        executor=_CountingExecutor(),
    )
    command = Command(
        principal="alice",
        scope=_scope(),
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

    outcome = await boundary.execute(command)

    assert outcome.status == "deferred"
    assert outcome.result == {"task_id": "task-123"}
    assert "human task inbox" in (outcome.error or "")
    assert captured["command"] is command


@pytest.mark.asyncio
async def test_enqueue_inbox_task_persists():
    command = Command(
        principal="alice",
        scope=_scope(),
        action="delete_table",
        tool="delete_table",
        params={"table": "customers"},
        objects=["tbl-customers"],
        requires_confirmation=False,
        requires_grant=True,
        capability="ai:operator",
        process_version="v1",
        capability_version="c1",
        object_revisions={"tbl-customers": 7},
        evidence_digest="sha256:abc",
        object_id="tbl-customers",
        object_type="table",
        process_instance="pi-1",
        run_id="run-1",
        autonomy="human_only",
    )

    task_id = await enqueue_inbox_task(command)

    assert task_id is not None
    task = await sync_to_async(HumanTask.objects.get, thread_sensitive=True)(pk=task_id)
    assert task.status == STATUS_PENDING
    assert task.capability == "ai:operator"
    assert task.object_id == "tbl-customers"
    assert task.object_type == "table"
    assert task.process_instance == "pi-1"
    assert task.run_id == "run-1"
    assert task.evidence_digest == "sha256:abc"
    assert task.required_authority == "ai:operator"
    assert task.consequence  # non-empty human-readable consequence
