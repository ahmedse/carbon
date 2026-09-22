"""Attendance permission ESS via Correspondence (ADR-0030 / NPS attendance ESS)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.conf import settings

from correspondence.fsm import approve as corr_approve
from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import AttendancePermission, Employee

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
ME_ATT_URL = f'{PREFIX}/people/me/attendance-permissions/'


@pytest.fixture
def att_workflow(db, create_user):
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type-att',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='attendance_permission',
        label='Attendance Permission',
    )
    perm_set = ReferenceSet.objects.create(
        name='permission_type', slug='permission-type-att',
    )
    personal = ReferenceValue.objects.create(
        reference_set=perm_set, code='personal', label='Personal',
    )
    org = OrgUnit.objects.create(
        name='Ops', slug='ops-att', code='OPS-ATT', org_type='department',
    )
    manager_user = create_user('att_mgr')
    requester_user = create_user('att_req')
    manager_emp = Employee.objects.create(
        org_unit=org, employee_no='E-ATT-MGR', full_name='Att Manager',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager_user,
        is_active=True,
    )
    requester_emp = Employee.objects.create(
        org_unit=org, employee_no='E-ATT-REQ', full_name='Att Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        manager=manager_emp, is_active=True,
    )
    policy = WorkflowPolicy.objects.create(
        name='Attendance Default', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve',
        skip_if_self=True, is_active=True,
    )
    return SimpleNamespace(
        corr_type=corr_type, org=org, manager_user=manager_user,
        requester_user=requester_user, manager_emp=manager_emp,
        requester_emp=requester_emp, personal=personal,
    )


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
    )
    return api_client


def _payload(day=None):
    day = day or (date.today() + timedelta(days=7))
    return {
        'date': day.isoformat(),
        'permission_type': 'personal',
        'hours': '2.00',
        'notes': 'ESS test',
    }


@pytest.mark.django_db
def test_submit_attendance_ess_happy_path(att_workflow, api_client, get_token_for_user):
    wf = att_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(ME_ATT_URL, _payload(), format='json')
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data['subject_type'] == 'people.AttendancePermission'
    assert data['status'] in ('submitted', 'in_review', 'approved')
    record = AttendancePermission.objects.get(pk=data['subject_id'])
    assert record.employee_id == wf.requester_emp.id
    assert record.approved is False
    assert record.hours == Decimal('2.00')


@pytest.mark.django_db
def test_manager_approve_flips_approved(att_workflow, api_client, get_token_for_user):
    wf = att_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    resp = api_client.post(ME_ATT_URL, _payload(), format='json')
    assert resp.status_code == 201, resp.content
    corr = Correspondence.objects.get(pk=resp.json()['id'])
    record = AttendancePermission.objects.get(pk=corr.subject_id)
    assert record.approved is False

    corr_approve(corr, wf.manager_user, comment='ok')
    record.refresh_from_db()
    assert record.approved is True


@pytest.mark.django_db
def test_submit_invalid_permission_type_400(att_workflow, api_client, get_token_for_user):
    wf = att_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    bad = _payload()
    bad['permission_type'] = 'not-a-real-type'
    resp = api_client.post(ME_ATT_URL, bad, format='json')
    assert resp.status_code == 400
    assert AttendancePermission.objects.count() == 0


@pytest.mark.django_db
def test_list_my_attendance_permissions(att_workflow, api_client, get_token_for_user):
    wf = att_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    assert api_client.post(ME_ATT_URL, _payload(), format='json').status_code == 201
    listed = api_client.get(ME_ATT_URL)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.django_db
def test_edit_then_resubmit_attendance_subject(
    att_workflow, api_client, get_token_for_user,
):
    """sent_back → edit payload (+ AttendancePermission sync) → resubmit."""
    from datetime import date as date_cls

    wf = att_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    day = date_cls.today() + timedelta(days=10)
    resp = api_client.post(ME_ATT_URL, _payload(day=day), format='json')
    assert resp.status_code == 201, resp.content
    corr_id = resp.json()['id']
    subject_id = resp.json()['subject_id']

    _auth(api_client, wf.manager_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/send-back/',
        {'comment': 'change hours'}, format='json',
    ).status_code == 200

    new_day = day + timedelta(days=1)
    _auth(api_client, wf.requester_user, get_token_for_user)
    edit = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/edit/',
        {
            'payload': {
                'permission_type': 'personal',
                'date': new_day.isoformat(),
                'hours': '3.50',
                'notes': 'revised',
            },
        },
        format='json',
    )
    assert edit.status_code == 200, edit.content
    body = edit.json()
    assert body['status'] == 'sent_back'
    assert body['payload']['hours'] == '3.50'
    assert body['payload']['date'] == new_day.isoformat()
    record = AttendancePermission.objects.get(pk=subject_id)
    assert record.hours == Decimal('3.50')
    assert record.date == new_day
    assert record.approved is False

    resub = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/resubmit/', {}, format='json',
    )
    assert resub.status_code == 200
    assert resub.json()['status'] == 'submitted'


@pytest.mark.django_db
def test_edit_rehydrates_orphaned_attendance_subject(
    att_workflow, api_client, get_token_for_user,
):
    """If AttendancePermission was deleted under an open corr, edit recreates it."""
    from datetime import date as date_cls

    wf = att_workflow
    _auth(api_client, wf.requester_user, get_token_for_user)
    day = date_cls.today() + timedelta(days=14)
    resp = api_client.post(ME_ATT_URL, _payload(day=day), format='json')
    assert resp.status_code == 201, resp.content
    corr_id = resp.json()['id']
    orphan_id = resp.json()['subject_id']

    _auth(api_client, wf.manager_user, get_token_for_user)
    assert api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/send-back/',
        {'comment': 'fix'}, format='json',
    ).status_code == 200

    AttendancePermission.objects.filter(pk=orphan_id).delete()

    _auth(api_client, wf.requester_user, get_token_for_user)
    edit = api_client.post(
        f'{PREFIX}/correspondence/{corr_id}/edit/',
        {
            'payload': {
                'permission_type': 'personal',
                'date': day.isoformat(),
                'hours': '1.00',
                'notes': 'rehydrate',
            },
        },
        format='json',
    )
    assert edit.status_code == 200, edit.content
    corr = Correspondence.objects.get(pk=corr_id)
    assert corr.subject_id != orphan_id
    restored = AttendancePermission.objects.get(pk=corr.subject_id)
    assert restored.hours == Decimal('1.00')
    assert restored.approved is False
