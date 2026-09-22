# people/tests/test_self_api.py
# OF-8 — employee self-service surface (/people/me/).

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


# ── 1. profile summary ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_me_returns_summary(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.get(ME_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert data['id'] == wf.requester_emp.id
    assert data['employee_no'] == 'E-SELF-REQ'
    assert data['full_name'] == 'Requester'
    assert data['is_active'] is True
    assert data['org_unit']['id'] == wf.org.id
    assert data['org_unit']['name'] == 'Engineering'
    assert data['manager']['id'] == wf.manager_emp.id
    assert data['manager']['name'] == 'Manager'


# ── 2. leave balance ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_leave_balance(workflow, api_client, get_token_for_user):
    wf = workflow
    year = date.today().year
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.get(BALANCE_URL)
    assert resp.status_code == 200
    data = resp.json()
    by_type = {row['leave_type']: row for row in data}

    assert set(by_type) == {'annual', 'sick'}
    assert _dec(by_type['annual']['entitled']) == Decimal('20')
    assert _dec(by_type['annual']['remaining']) == Decimal('20')
    # Whole days serialize as JSON ints (not "20.00" strings).
    assert by_type['annual']['entitled'] == 20
    assert isinstance(by_type['annual']['entitled'], int)
    assert by_type['annual']['remaining'] == 20
    # No entitlement seeded → entitled/remaining are 0 (never negative).
    assert _dec(by_type['sick']['entitled']) == Decimal('0')
    assert _dec(by_type['sick']['remaining']) == Decimal('0')
    assert by_type['sick']['entitled'] == 0


# ── 3. submit happy path ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_leave_happy_path(workflow, api_client, get_token_for_user):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LEAVE_URL, _payload(), format='json')
    assert resp.status_code == 201, resp.content
    data = resp.json()

    assert data['status'] in ('submitted', 'approved')
    assert data['reference_no']
    assert data['subject_type'] == 'people.LeaveRecord'
    assert len(data['events']) >= 1

    record = LeaveRecord.objects.get(pk=data['subject_id'])
    assert record.employee_id == wf.requester_emp.id
    assert record.status == 'draft'  # LeaveRecord stays draft; corr holds status

    corr = Correspondence.objects.get(pk=data['id'])
    assert corr.reference_no == data['reference_no']
    assert corr.subject_id == record.pk


@pytest.mark.django_db
def test_submit_leave_no_manager_400(workflow, api_client, get_token_for_user):
    wf = workflow
    wf.requester_emp.manager = None
    wf.requester_emp.save(update_fields=['manager'])
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LEAVE_URL, _payload(), format='json')
    assert resp.status_code == 400, resp.content
    data = resp.json()
    assert data['error_kind'] == 'no_manager'
    assert LeaveRecord.objects.count() == 0
    assert Correspondence.objects.count() == 0


@pytest.mark.django_db
def test_submit_leave_manager_no_user_400(workflow, api_client, get_token_for_user):
    wf = workflow
    wf.manager_emp.user = None
    wf.manager_emp.save(update_fields=['user'])
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LEAVE_URL, _payload(), format='json')
    assert resp.status_code == 400, resp.content
    assert resp.json()['error_kind'] == 'manager_no_user'
    assert LeaveRecord.objects.count() == 0


# ── 4. insufficient balance ────────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_insufficient_balance_400(workflow, api_client, get_token_for_user):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('1'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LEAVE_URL, _payload(days='5'), format='json')
    assert resp.status_code == 400
    data = resp.json()
    assert data['error_kind'] == 'insufficient_balance'
    assert 'insufficient' in data['detail'].lower()
    assert _dec(data['remaining']) == Decimal('1')
    assert data.get('hints', {}).get('suggestion')
    assert LeaveRecord.objects.count() == 0


# ── 5. overlap ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_overlap_400(workflow, api_client, get_token_for_user):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)

    start = date.today() + timedelta(days=5)
    first = api_client.post(
        LEAVE_URL, _payload(start=start), format='json',
    )
    assert first.status_code == 201

    overlap_start = start + timedelta(days=2)
    second = api_client.post(
        LEAVE_URL, _payload(start=overlap_start, days='3'), format='json',
    )
    assert second.status_code == 400
    body = second.json()
    assert body['error_kind'] == 'overlap'
    assert 'overlap' in body['detail'].lower()
    assert body.get('hints', {}).get('suggestion')


# ── 6. validation: days <= 0 and end < start ───────────────────────────────

@pytest.mark.django_db
def test_submit_nonpositive_days_400(workflow, api_client, get_token_for_user):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LEAVE_URL, _payload(days='0'), format='json')
    assert resp.status_code == 400
    assert LeaveRecord.objects.count() == 0


@pytest.mark.django_db
def test_submit_end_before_start_400(workflow, api_client, get_token_for_user):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    start = date.today() + timedelta(days=5)
    end = start - timedelta(days=1)
    resp = api_client.post(LEAVE_URL, _payload(start=start, end=end), format='json')
    assert resp.status_code == 400
    assert LeaveRecord.objects.count() == 0


@pytest.mark.django_db
def test_submit_long_past_start_400(workflow, api_client, get_token_for_user):
    """A year-old start date is a clockless assistant, not a real request."""
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    stale = date.today().replace(year=date.today().year - 1)
    resp = api_client.post(
        LEAVE_URL, _payload(start=stale, end=stale), format='json',
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body['error_kind'] == 'invalid_dates'
    assert body['hints']['earliest_allowed']
    assert LeaveRecord.objects.count() == 0


@pytest.mark.django_db
def test_submit_recent_backdate_allowed(workflow, api_client, get_token_for_user):
    """Sick leave reported after the fact still goes through."""
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    yesterday = date.today() - timedelta(days=1)
    resp = api_client.post(
        LEAVE_URL, _payload(start=yesterday, end=yesterday), format='json',
    )
    assert resp.status_code == 201, resp.content


# ── 7. cross-user isolation ────────────────────────────────────────────────

@pytest.mark.django_db
def test_cross_user_isolation(workflow, api_client, get_token_for_user, create_user):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(LEAVE_URL, _payload(), format='json')
    assert resp.status_code == 201
    record_id = resp.json()['subject_id']

    other_user = create_user('self_other')
    Employee.objects.create(
        org_unit=wf.org, employee_no='E-SELF-OTH', full_name='Other',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=other_user,
        manager=wf.manager_emp, is_active=True,
    )
    _auth(api_client, other_user, get_token_for_user)

    detail = api_client.get(f'{LEAVE_URL}{record_id}/')
    assert detail.status_code == 404

    listing = api_client.get(LEAVE_URL)
    assert listing.status_code == 200
    assert listing.json() == []


# ── 8. detail returns reference_no + events ────────────────────────────────

@pytest.mark.django_db
def test_leave_detail_has_reference_and_events(
    workflow, api_client, get_token_for_user,
):
    wf = workflow
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year, leave_type=wf.leave_annual,
        entitled_days=Decimal('20'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    submitted = api_client.post(LEAVE_URL, _payload(), format='json')
    assert submitted.status_code == 201
    record_id = submitted.json()['subject_id']

    resp = api_client.get(f'{LEAVE_URL}{record_id}/')
    assert resp.status_code == 200
    data = resp.json()
    assert data['id'] == record_id
    assert data['leave_type'] == 'annual'
    assert data['leave_type_label'] == 'Annual Leave'
    assert data['reference_no']
    assert data['correspondence_id'] == submitted.json()['id']
    assert len(data['events']) >= 1


# ── 9. unknown leave_type → 400 ────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_unknown_leave_type_400(workflow, api_client, get_token_for_user):
    wf = workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(
        LEAVE_URL, _payload(leave_type='bereavement'), format='json',
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body['error_kind'] == 'invalid_leave_type'
    assert 'bereavement' in body['detail']
    assert 'allowed_types' in body.get('hints', {})
    assert LeaveRecord.objects.count() == 0


@pytest.mark.django_db
def test_submit_arada_alias_resolves_to_emergency(workflow, api_client, get_token_for_user):
    """عارضة must resolve to emergency via host leave_type_resolve (not Chat)."""
    from people.leave_type_resolve import ensure_leave_type_aliases
    from people.tests.ref_helpers import ensure_ref

    wf = workflow
    ensure_ref('leave_type', 'emergency', 'Emergency')
    ensure_leave_type_aliases()
    LeaveEntitlement.objects.create(
        employee=wf.requester_emp, year=date.today().year,
        leave_type=ensure_ref('leave_type', 'emergency', 'Emergency'),
        entitled_days=Decimal('5'),
    )
    _auth(api_client, wf.requester_user, get_token_for_user)
    start = date.today() + timedelta(days=40)
    resp = api_client.post(
        LEAVE_URL,
        _payload(leave_type='عارضة', start=start, days='1'),
        format='json',
    )
    assert resp.status_code == 201, resp.content
    assert LeaveRecord.objects.filter(
        employee=wf.requester_emp, leave_type__code='emergency',
    ).exists()
