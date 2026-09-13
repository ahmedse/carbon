# people/tests/test_leave_journey_e2e.py
# OF-12 — full leave journey, thin vertical slice (self-service → correspondence
# engine → manager approval), exercised through the DRF test client.
#
# Self-contained (mirrors test_self_api.py): defines its own ``workflow``
# fixture so it can run standalone:
#     python -m pytest people/tests/test_leave_journey_e2e.py -q

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.conf import settings

from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement, LeaveRecord

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
ME_URL = f'{PREFIX}/people/me/'
BALANCE_URL = ME_URL + 'leave-balance/'
LEAVE_URL = ME_URL + 'leave/'
INBOX_URL = f'{PREFIX}/correspondence/inbox/'


def _dec(value) -> Decimal:
    return Decimal(str(value))


# ── fixture ────────────────────────────────────────────────────────────────

@pytest.fixture
def workflow(db, create_user):
    """Org, corr_type/leave_type reference sets, manager + requester employees,
    and a single-step (manager) workflow policy."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='leave_request', label='Leave Request',
    )
    leave_set = ReferenceSet.objects.create(
        name='leave_type', slug='leave-type',
    )
    leave_annual = ReferenceValue.objects.create(
        reference_set=leave_set, code='annual', label='Annual Leave', sort_order=1,
    )
    leave_sick = ReferenceValue.objects.create(
        reference_set=leave_set, code='sick', label='Sick Leave', sort_order=2,
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    manager_user = create_user('self_manager')
    requester_user = create_user('self_requester')
    manager_emp = Employee.objects.create(
        org_unit=org, employee_no='E-SELF-MGR', full_name='Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager_user,
        is_active=True,
    )
    requester_emp = Employee.objects.create(
        org_unit=org, employee_no='E-SELF-REQ', full_name='Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        manager=manager_emp, is_active=True,
    )
    policy = WorkflowPolicy.objects.create(
        name='Leave Default', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve', is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type, org=org, manager_user=manager_user,
        requester_user=requester_user, manager_emp=manager_emp,
        requester_emp=requester_emp, policy=policy,
        leave_annual=leave_annual, leave_sick=leave_sick,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
    )
    return api_client


def _payload(leave_type='annual', days='5', start=None, end=None):
    start = start or (date.today() + timedelta(days=5))
    end = end or (start + timedelta(days=4))
    return {
        'leave_type': leave_type,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'days': days,
    }


def _seed_annual(wf, days='20'):
    """Seed the requester's annual entitlement for the current year."""
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year,
        leave_type=wf.leave_annual,
        entitled_days=Decimal(str(days)),
    )


def _annual_balance(api_client):
    """Fetch the balance rows and return the 'annual' row (or None)."""
    resp = api_client.get(BALANCE_URL)
    assert resp.status_code == 200, resp.content
    by_type = {row['leave_type']: row for row in resp.json()}
    return by_type.get('annual')


# ── 1. submit creates a governed correspondence ────────────────────────────

@pytest.mark.django_db
def test_submit_leave_creates_governed_correspondence(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    _seed_annual(wf, days='20')
    _auth(api_client, wf.requester_user, get_token_for_user)

    resp = api_client.post(LEAVE_URL, _payload(), format='json')
    assert resp.status_code == 201, resp.content
    data = resp.json()

    assert data['status'] in ('submitted', 'approved')
    assert data['reference_no']
    assert data['subject_type'] == 'people.LeaveRecord'
    assert wf.manager_user.id in data['current_approver_ids']
    assert len(data['events']) >= 1

    # The LeaveRecord is created (draft), and carries the subject_id link.
    record = LeaveRecord.objects.get(pk=data['subject_id'])
    assert record.employee_id == wf.requester_emp.id
    assert record.status == 'draft'  # governed Correspondence carries the status

    corr = Correspondence.objects.get(pk=data['id'])
    assert corr.reference_no == data['reference_no']
    assert corr.subject_id == record.pk


# ── 2. manager inbox + approve completes the single-step chain ─────────────

@pytest.mark.django_db
def test_manager_inbox_and_approve(workflow, api_client, get_token_for_user):
    wf = workflow
    _seed_annual(wf, days='20')

    _auth(api_client, wf.requester_user, get_token_for_user)
    submitted = api_client.post(LEAVE_URL, _payload(), format='json')
    assert submitted.status_code == 201, submitted.content
    corr_id = submitted.json()['id']

    # Manager sees the awaiting correspondence in their inbox.
    _auth(api_client, wf.manager_user, get_token_for_user)
    inbox = api_client.get(INBOX_URL)
    assert inbox.status_code == 200, inbox.content
    data = inbox.json()
    # Pagination is disabled under pytest → plain JSON list.
    if isinstance(data, dict):
        data = data.get('results', [])
    assert any(item['id'] == corr_id for item in data)

    # Manager approves → single-step chain → terminal 'approved'.
    approve = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/approve/',
        {'comment': 'approved'}, format='json',
    )
    assert approve.status_code == 200, approve.content
    assert approve.json()['status'] == 'approved'


# ── 3. balance pending rises on submit and falls on approve ────────────────

@pytest.mark.django_db
def test_balance_pending_rises_then_falls(workflow, api_client, get_token_for_user):
    wf = workflow
    _seed_annual(wf, days='20')
    _auth(api_client, wf.requester_user, get_token_for_user)

    before = _annual_balance(api_client)
    assert _dec(before['pending']) == Decimal('0')

    submitted = api_client.post(LEAVE_URL, _payload(), format='json')
    assert submitted.status_code == 201, submitted.content

    after_submit = _annual_balance(api_client)
    assert _dec(after_submit['pending']) == Decimal('5')

    corr_id = submitted.json()['id']
    _auth(api_client, wf.manager_user, get_token_for_user)
    approve = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/approve/',
        {'comment': 'approved'}, format='json',
    )
    assert approve.status_code == 200, approve.content
    assert approve.json()['status'] == 'approved'

    _auth(api_client, wf.requester_user, get_token_for_user)
    after_approve = _annual_balance(api_client)
    assert _dec(after_approve['pending']) == Decimal('0')

    # LeaveRecord itself stays 'draft' — the governed Correspondence holds status.
    record = LeaveRecord.objects.get(pk=submitted.json()['subject_id'])
    assert record.status == 'draft'


# ── 3b. approved correspondence counts days as used (F13 regression) ───────

@pytest.mark.django_db
def test_balance_used_after_approval(workflow, api_client, get_token_for_user):
    wf = workflow
    _seed_annual(wf, days='20')
    _auth(api_client, wf.requester_user, get_token_for_user)

    before = _annual_balance(api_client)
    assert _dec(before['used']) == Decimal('0')
    assert _dec(before['remaining']) == Decimal('20')

    submitted = api_client.post(LEAVE_URL, _payload(), format='json')
    assert submitted.status_code == 201, submitted.content

    corr_id = submitted.json()['id']
    _auth(api_client, wf.manager_user, get_token_for_user)
    approve = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/approve/',
        {'comment': 'approved'}, format='json',
    )
    assert approve.status_code == 200, approve.content
    assert approve.json()['status'] == 'approved'

    _auth(api_client, wf.requester_user, get_token_for_user)
    after = _annual_balance(api_client)
    assert _dec(after['used']) == Decimal('5')
    assert _dec(after['pending']) == Decimal('0')
    assert _dec(after['remaining']) == Decimal('15')

    # LeaveRecord stays 'draft' — approved days still count as used (F13).
    record = LeaveRecord.objects.get(pk=submitted.json()['subject_id'])
    assert record.status == 'draft'


# ── 4. reject path: rejected request no longer blocks a new overlap ────────

@pytest.mark.django_db
def test_reject_unblocks_overlapping_request(workflow, api_client, get_token_for_user):
    wf = workflow
    _seed_annual(wf, days='20')
    _auth(api_client, wf.requester_user, get_token_for_user)

    start = date.today() + timedelta(days=5)
    first = api_client.post(LEAVE_URL, _payload(start=start), format='json')
    assert first.status_code == 201, first.content
    corr_id = first.json()['id']

    _auth(api_client, wf.manager_user, get_token_for_user)
    reject = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/reject/',
        {'comment': 'Invalid dates'}, format='json',
    )
    assert reject.status_code == 200, reject.content
    assert reject.json()['status'] == 'rejected'

    # An overlapping request is now allowed (rejected record is not blocking).
    _auth(api_client, wf.requester_user, get_token_for_user)
    overlap_start = start + timedelta(days=2)
    second = api_client.post(
        LEAVE_URL, _payload(start=overlap_start, days='3'), format='json',
    )
    assert second.status_code == 201, second.content
