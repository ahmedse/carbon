# LeaveRecord admin cannot approve/reject via PATCH — Correspondence / Team only.
from datetime import date

import pytest

from mdm.models import OrgUnit
from people.models import Employee, LeaveRecord
from people.tests.ref_helpers import ensure_ref

LEAVE_URL = '/carbon-api/people/leave-records/'


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    return api_client


@pytest.fixture
def leave_admin_ctx(db, create_user, api_client, get_token_for_user):
    org = OrgUnit.objects.create(name='Eng', slug='eng-leave-demote', org_type='department')
    annual = ensure_ref('leave_type', 'annual')
    emp = Employee.objects.create(
        org_unit=org,
        employee_no='E-LV-DEM',
        full_name='Leave Demote',
        basic_salary='1000.000',
        join_date=date(2026, 1, 1),
        is_active=True,
    )
    record = LeaveRecord.objects.create(
        employee=emp,
        leave_type=annual,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 5),
        days='5.00',
        status='submitted',
    )
    client = _auth(api_client, create_user('leave_demote_admin', is_superuser=True), get_token_for_user)
    return {'client': client, 'record': record, 'emp': emp, 'annual': annual}


@pytest.mark.django_db
def test_patch_approve_refused(leave_admin_ctx):
    client = leave_admin_ctx['client']
    record = leave_admin_ctx['record']
    resp = client.patch(
        f'{LEAVE_URL}{record.pk}/',
        {'status': 'approved'},
        format='json',
    )
    assert resp.status_code == 403, resp.content
    assert resp.json().get('code') == 'leave_status_via_correspondence'
    record.refresh_from_db()
    assert record.status == 'submitted'


@pytest.mark.django_db
def test_patch_reject_refused(leave_admin_ctx):
    client = leave_admin_ctx['client']
    record = leave_admin_ctx['record']
    resp = client.patch(
        f'{LEAVE_URL}{record.pk}/',
        {'status': 'rejected'},
        format='json',
    )
    assert resp.status_code == 403, resp.content
    record.refresh_from_db()
    assert record.status == 'submitted'


@pytest.mark.django_db
def test_create_with_approved_refused(leave_admin_ctx):
    client = leave_admin_ctx['client']
    emp = leave_admin_ctx['emp']
    annual = leave_admin_ctx['annual']
    resp = client.post(
        LEAVE_URL,
        {
            'employee': emp.pk,
            'leave_type': annual.code,
            'start_date': '2026-11-01',
            'end_date': '2026-11-02',
            'days': '2',
            'status': 'approved',
        },
        format='json',
    )
    assert resp.status_code == 400, resp.content
    assert resp.json().get('code') == 'leave_status_via_correspondence'


@pytest.mark.django_db
def test_patch_non_terminal_status_ok(leave_admin_ctx):
    client = leave_admin_ctx['client']
    record = leave_admin_ctx['record']
    resp = client.patch(
        f'{LEAVE_URL}{record.pk}/',
        {'days': '4.00'},
        format='json',
    )
    assert resp.status_code == 200, resp.content
    record.refresh_from_db()
    assert str(record.days) == '4.00'
    assert record.status == 'submitted'
