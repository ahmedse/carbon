"""NPS-2 — Pulse review authority binds to host HR CBAC (not ai:operator)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.capabilities import (
    CORRESPONDENCE_ACT,
    CORRESPONDENCE_FINANCE,
    PEOPLE_MANAGE,
)
from ai.command_boundary import Command
from ai.engine.ports.domain import load_domain_pack
from ai.governance.review_authority import (
    DEFAULT_REQUIRED_AUTHORITY,
    REVIEW_AUTHORITY_BY_CAPABILITY,
    assert_registry_keys_are_cbac,
    known_hr_review_authorities,
    resolve_required_authority,
)
from ai.instance_registry import resolve_default_app_identifier
from ai.models.human_task import IRREVERSIBLE, STATUS_PENDING, HumanTask
from ai.protocol import Scope
from ai.task_inbox import TaskInbox, UnauthorizedApprover, enqueue_inbox_task
from django.urls import reverse

pytestmark = pytest.mark.django_db(transaction=True)

PACK_DIR = Path(settings.BASE_DIR).parent / "domain_packs" / "nibras"


def _task_kwargs(**overrides):
    base = dict(
        objects_revisions={},
        before={},
        after={},
        evidence={},
        reversibility=IRREVERSIBLE,
        expires_at=timezone.now() + timedelta(hours=1),
        process_version="1.0",
        capability_version="1.0",
        app_identifier=resolve_default_app_identifier(),
        visibility="global",
    )
    base.update(overrides)
    return base


def _scope() -> Scope:
    return Scope(
        user_identifier="u1",
        org_unit_ids=["*"],
        module_ids=["*"],
        is_superuser=True,
    )


def test_registry_keys_are_real_cbac():
    assert_registry_keys_are_cbac()
    assert DEFAULT_REQUIRED_AUTHORITY == "ai:operator"
    assert known_hr_review_authorities() == frozenset(
        {
            CORRESPONDENCE_ACT.key,
            CORRESPONDENCE_FINANCE.key,
            PEOPLE_MANAGE.key,
        }
    )


@pytest.mark.parametrize(
    "capability,expected",
    [
        ("leave.request.review", "correspondence:act"),
        ("loan.request.review", "correspondence:finance"),
        ("payroll.run.review", "people:manage"),
        ("gosi_wps.sif.review", "people:manage"),
        ("employee.onboarding.review", "people:manage"),
        ("attendance.permission.review", "correspondence:act"),
        ("ai:operator", "ai:operator"),
        ("dq.rule.publish", "ai:operator"),
        ("", "ai:operator"),
    ],
)
def test_resolve_required_authority(capability, expected):
    assert resolve_required_authority(capability) == expected


def test_every_nibras_human_task_review_is_mapped():
    """Honesty: pack human_task review caps must not silently keep ai:operator."""
    pack = load_domain_pack(PACK_DIR)
    missing = []
    for process in pack.processes():
        for step in process.get("steps") or []:
            if step.get("kind") != "human_task":
                continue
            cap = step.get("capability")
            if not cap:
                continue
            if cap not in REVIEW_AUTHORITY_BY_CAPABILITY:
                missing.append(f"{process.get('id')}:{cap}")
            else:
                assert (
                    REVIEW_AUTHORITY_BY_CAPABILITY[cap] != DEFAULT_REQUIRED_AUTHORITY
                ), f"{cap} must not map to ai:operator"
    assert missing == [], f"Unmapped Nibras human_task reviews: {missing}"


@pytest.mark.asyncio
async def test_enqueue_leave_review_binds_manager_authority():
    command = Command(
        principal="alice",
        scope=_scope(),
        action="review",
        tool="leave.request.review",
        params={"request_id": "lr-1"},
        objects=["lr-1"],
        requires_confirmation=False,
        requires_grant=True,
        capability="leave.request.review",
        process_version="1.0",
        capability_version="1.0",
        object_revisions={},
        evidence_digest="",
        autonomy="human_only",
    )
    task_id = await enqueue_inbox_task(command)
    task = await sync_to_async(HumanTask.objects.get, thread_sensitive=True)(
        pk=task_id
    )
    assert task.required_authority == "correspondence:act"
    assert task.capability == "leave.request.review"


@pytest.mark.asyncio
async def test_enqueue_unmapped_keeps_operator_default():
    command = Command(
        principal="alice",
        scope=_scope(),
        action="delete_table",
        tool="delete_table",
        params={},
        objects=["tbl"],
        requires_confirmation=False,
        requires_grant=True,
        capability="ai:publisher",
        process_version="v1",
        capability_version="c1",
        object_revisions={},
        evidence_digest="",
        autonomy="human_only",
    )
    task_id = await enqueue_inbox_task(command)
    task = await sync_to_async(HumanTask.objects.get, thread_sensitive=True)(
        pk=task_id
    )
    assert task.required_authority == "ai:operator"


def test_manager_approves_leave_review_operator_refused(
    create_user, create_scoped_role,
):
    manager = create_user("mgr_nps2")
    create_scoped_role(manager, "manager_group")
    operator = create_user("op_nps2")
    create_scoped_role(operator, "ai_operator_group")

    inbox = TaskInbox()
    task = inbox.create_task(
        **_task_kwargs(
            consequence="Review leave request lr-nps2",
            required_authority=resolve_required_authority("leave.request.review"),
            capability="leave.request.review",
        )
    )
    assert task.required_authority == "correspondence:act"

    with pytest.raises(UnauthorizedApprover):
        inbox.approve(operator, task.id)

    approved = inbox.approve(manager, task.id)
    assert approved.status != STATUS_PENDING
    assert approved.grant_id


def test_finance_approves_loan_review_manager_refused(
    create_user, create_scoped_role,
):
    manager = create_user("mgr_loan_nps2")
    create_scoped_role(manager, "manager_group")
    finance = create_user("fin_nps2")
    create_scoped_role(finance, "finance_group")

    inbox = TaskInbox()
    task = inbox.create_task(
        **_task_kwargs(
            consequence="Review loan request",
            required_authority=resolve_required_authority("loan.request.review"),
            capability="loan.request.review",
        )
    )

    with pytest.raises(UnauthorizedApprover):
        inbox.approve(manager, task.id)

    approved = inbox.approve(finance, task.id)
    assert approved.grant_id


def test_people_lead_approves_payroll_review_operator_refused(
    create_user, create_scoped_role,
):
    lead = create_user("lead_nps2")
    create_scoped_role(lead, "people_lead")
    operator = create_user("op_pay_nps2")
    create_scoped_role(operator, "ai_operator_group")

    inbox = TaskInbox()
    task = inbox.create_task(
        **_task_kwargs(
            consequence="Review payroll run",
            required_authority=resolve_required_authority("payroll.run.review"),
            capability="payroll.run.review",
        )
    )
    assert task.required_authority == "people:manage"

    with pytest.raises(UnauthorizedApprover):
        inbox.approve(operator, task.id)

    approved = inbox.approve(lead, task.id)
    assert approved.grant_id


def test_list_pending_filters_to_designated_authority(
    create_user, create_scoped_role,
):
    manager = create_user("mgr_list_nps2")
    create_scoped_role(manager, "manager_group")
    finance = create_user("fin_list_nps2")
    create_scoped_role(finance, "finance_group")

    inbox = TaskInbox()
    leave_task = inbox.create_task(
        **_task_kwargs(
            consequence="leave",
            required_authority="correspondence:act",
            capability="leave.request.review",
        )
    )
    loan_task = inbox.create_task(
        **_task_kwargs(
            consequence="loan",
            required_authority="correspondence:finance",
            capability="loan.request.review",
        )
    )

    mgr_ids = {t.id for t in inbox.list_pending(user=manager)}
    fin_ids = {t.id for t in inbox.list_pending(user=finance)}
    assert leave_task.id in mgr_ids
    assert loan_task.id not in mgr_ids
    assert loan_task.id in fin_ids
    assert leave_task.id not in fin_ids


def test_inbox_api_manager_can_list_and_approve(
    create_user, create_scoped_role,
):
    manager = create_user("mgr_api_nps2")
    create_scoped_role(manager, "manager_group")
    plain = create_user("plain_api_nps2")

    inbox = TaskInbox()
    task = inbox.create_task(
        **_task_kwargs(
            consequence="API leave review",
            required_authority="correspondence:act",
            capability="leave.request.review",
        )
    )

    list_url = reverse("ai-inbox-list")
    approve_url = reverse("ai-inbox-approve", kwargs={"pk": task.id})

    client = APIClient()
    client.force_authenticate(user=plain)
    assert client.get(list_url).status_code == 403

    client.force_authenticate(user=manager)
    listed = client.get(list_url)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.data}
    assert task.id in ids

    approved = client.post(approve_url)
    assert approved.status_code == 200
    assert approved.data["grant_id"]
