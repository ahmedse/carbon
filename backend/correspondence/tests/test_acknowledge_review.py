# correspondence/tests/test_acknowledge_review.py
# OF-15 — acknowledge/review transitions + fsm.act dispatcher + API route.

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from django.conf import settings

from correspondence.exceptions import InvalidTransition, NotActorError
from correspondence.fsm import (
    acknowledge,
    act,
    review,
    submit_correspondence,
)
from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee

PREFIX = f'/{settings.API_PREFIX.strip("/")}'


@pytest.fixture
def memo_workflow(db, create_user):
    """internal_memo corr_type + any_admin/acknowledge policy + requester/admin."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='internal_memo', label='Internal Memo',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    requester_user = create_user('ack_requester')
    admin_user = create_user('ack_admin', is_superuser=True)
    Employee.objects.create(
        org_unit=org, employee_no='E-ACK-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
    )
    policy = WorkflowPolicy.objects.create(
        name='Internal Memo Default', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='any_admin', intent='acknowledge',
        is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type, org=org, requester_user=requester_user,
        admin_user=admin_user, policy=policy,
    )


def _submit_memo(wf):
    corr = Correspondence.objects.create(
        corr_type=wf.corr_type, subject_type='', subject_id=None,
        org_unit=wf.org, requester=wf.requester_user,
        title='Team announcement', payload={}, status='draft',
        reference_no=f'DRAFT-{uuid.uuid4().hex[:12]}',
    )
    return submit_correspondence(corr=corr, by=wf.requester_user, subject=None)


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    return api_client


# ── fsm.acknowledge ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_acknowledge_advances_and_records_acknowledged(memo_workflow):
    wf = memo_workflow
    corr = _submit_memo(wf)

    corr = acknowledge(corr, wf.admin_user, comment='Noted')

    assert corr.status == 'approved'
    assert corr.resolved_at is not None
    assert corr.approver_chain[0]['decision'] == 'acknowledged'
    assert corr.approver_chain[0]['decided_by'] == wf.admin_user.id
    assert corr.approver_chain[0]['comment'] == 'Noted'


@pytest.mark.django_db
def test_acknowledge_by_non_approver_raises(memo_workflow, create_user):
    wf = memo_workflow
    corr = _submit_memo(wf)
    outsider = create_user('ack_outsider')

    with pytest.raises(NotActorError):
        acknowledge(corr, outsider)


# ── fsm.review ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_review_advances_and_records_reviewed(memo_workflow):
    wf = memo_workflow
    corr = _submit_memo(wf)

    corr = review(corr, wf.admin_user)

    assert corr.status == 'approved'
    assert corr.approver_chain[0]['decision'] == 'reviewed'
    assert corr.approver_chain[0]['decided_by'] == wf.admin_user.id


# ── fsm.act dispatcher ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_act_dispatches_acknowledge(memo_workflow):
    wf = memo_workflow
    corr = _submit_memo(wf)

    corr = act(corr, wf.admin_user, 'acknowledge')

    assert corr.status == 'approved'
    assert corr.approver_chain[0]['decision'] == 'acknowledged'


@pytest.mark.django_db
def test_act_dispatches_approve(memo_workflow):
    wf = memo_workflow
    corr = _submit_memo(wf)

    corr = act(corr, wf.admin_user, 'approve')

    assert corr.status == 'approved'
    assert corr.approver_chain[0]['decision'] == 'approved'


@pytest.mark.django_db
def test_act_unsupported_intent_raises(memo_workflow):
    wf = memo_workflow
    corr = _submit_memo(wf)

    with pytest.raises(InvalidTransition):
        act(corr, wf.admin_user, 'bogus')


# ── API acknowledge route ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_acknowledge_api_route(memo_workflow, api_client, get_token_for_user):
    wf = memo_workflow
    corr = _submit_memo(wf)

    _auth(api_client, wf.admin_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/acknowledge/', {}, format='json',
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'approved'
    assert data['approver_chain'][0]['decision'] == 'acknowledged'


@pytest.mark.django_db
def test_acknowledge_api_non_approver_403(
    memo_workflow, api_client, get_token_for_user, create_user,
):
    wf = memo_workflow
    corr = _submit_memo(wf)

    outsider = create_user('ack_api_outsider')
    _auth(api_client, outsider, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/acknowledge/', {}, format='json',
    )

    assert resp.status_code == 403


# ── API review route ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_review_api_route(memo_workflow, api_client, get_token_for_user):
    wf = memo_workflow
    corr = _submit_memo(wf)

    _auth(api_client, wf.admin_user, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/review/', {}, format='json',
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'approved'
    assert data['approver_chain'][0]['decision'] == 'reviewed'


@pytest.mark.django_db
def test_review_api_non_approver_403(
    memo_workflow, api_client, get_token_for_user, create_user,
):
    wf = memo_workflow
    corr = _submit_memo(wf)

    outsider = create_user('review_api_outsider')
    _auth(api_client, outsider, get_token_for_user)
    resp = api_client.post(
        f'{PREFIX}/correspondence/{corr.id}/review/', {}, format='json',
    )

    assert resp.status_code == 403
