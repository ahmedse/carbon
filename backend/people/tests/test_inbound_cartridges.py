"""DMS-COR-LEAVE: opening balance upserts; history does not increment used_days."""
import io
from decimal import Decimal

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement, LeaveRecord


PREFIX = f'/{settings.API_PREFIX.strip("/")}/inbound'


def _csv(text):
    buf = io.BytesIO(text.encode('utf-8'))
    buf.name = 't.csv'
    return buf


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='HR', slug='hr-inb', code='HR', org_type='department')


@pytest.fixture
def leave_annual(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type-inb')
    return ReferenceValue.objects.create(reference_set=rs, code='annual', label='Annual')


@pytest.fixture
def prep_cmt(create_user, create_scoped_role):
    prep = create_user('inb_prep')
    cmt = create_user('inb_cmt')
    create_scoped_role(prep, 'people_data_owners_group')
    create_scoped_role(cmt, 'people_lead')
    return prep, cmt


def _auth(client, user, get_token_for_user):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')


@pytest.mark.django_db
def test_employee_snapshot_smoke_zero_writes(prep_cmt, org, get_token_for_user):
    prep, _cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.employee_snapshot',
    }, format='json')
    bid = res.data['id']
    body = 'Code,FullNameEn,Cost Center,Salary\n1067,Bilagot,HR,100.000\n'
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
        },
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert res.data['smoke']['insert'] == 1
    assert res.data['smoke']['sample'][0]['key'] == '1067'
    assert 'employee_no' not in res.data['smoke']['sample'][0]
    assert Employee.objects.count() == 0


@pytest.mark.django_db
def test_employee_snapshot_commit_idempotent(prep_cmt, org, get_token_for_user):
    prep, cmt = prep_cmt
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.employee_snapshot',
    }, format='json')
    bid = res.data['id']
    body = (
        'Code,FullNameEn,Cost Center,Salary,Manager\n'
        '1067,Bilagot,HR,100.000,1712\n'
        '1712,Mohammad,HR,200.000,\n'
    )
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
            'Manager': 'manager_employee_no',
        },
    }, format='json')
    client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    assert Employee.objects.count() == 2
    emp = Employee.objects.get(employee_no='1067')
    assert emp.manager.employee_no == '1712'

    # second batch updates, no dupes
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.employee_snapshot',
    }, format='json')
    bid2 = res.data['id']
    body2 = 'Code,FullNameEn,Cost Center,Salary\n1067,Bilagot Updated,HR,150.000\n'
    client.post(f'{PREFIX}/batches/{bid2}/file/', {'file': _csv(body2)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid2}/mapping/', {
        'columns': {
            'Code': 'employee_no',
            'FullNameEn': 'full_name',
            'Cost Center': 'org_unit',
            'Salary': 'basic_salary',
        },
    }, format='json')
    client.post(f'{PREFIX}/batches/{bid2}/smoke/', {}, format='json')
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid2}/commit/', {}, format='json')
    assert res.status_code == 200
    assert Employee.objects.count() == 2
    assert Employee.objects.get(employee_no='1067').full_name == 'Bilagot Updated'
    assert Employee.objects.get(employee_no='1067').basic_salary == Decimal('150.000')


@pytest.mark.django_db
def test_leave_opening_balance_upsert(prep_cmt, org, leave_annual, get_token_for_user):
    prep, cmt = prep_cmt
    emp = Employee.objects.create(
        org_unit=org, employee_no='1067', full_name='Bilagot',
        basic_salary=Decimal('100.000'),
    )
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_opening_balance',
    }, format='json')
    bid = res.data['id']
    body = 'emp,year,type,entitled,used\n1067,2026,annual,30,4\n'
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'emp': 'employee_no', 'year': 'year', 'type': 'leave_type',
            'entitled': 'entitled_days', 'used': 'used_days',
        },
    }, format='json')
    res = client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    assert res.status_code == 200
    assert LeaveEntitlement.objects.count() == 0
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    ent = LeaveEntitlement.objects.get(employee=emp, year=2026, leave_type=leave_annual)
    assert ent.entitled_days == Decimal('30')
    assert ent.used_days == Decimal('4')


@pytest.mark.django_db
def test_leave_history_does_not_add_used_days(prep_cmt, org, leave_annual, get_token_for_user):
    """DMS-COR-LEAVE"""
    prep, cmt = prep_cmt
    emp = Employee.objects.create(
        org_unit=org, employee_no='1067', full_name='Bilagot',
        basic_salary=Decimal('100.000'),
    )
    LeaveEntitlement.objects.create(
        employee=emp, year=2026, leave_type=leave_annual,
        entitled_days=Decimal('30'), used_days=Decimal('5'),
    )
    client = APIClient()
    _auth(client, prep, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/', {
        'kind': 'typed_object', 'target_key': 'people.leave_history',
    }, format='json')
    bid = res.data['id']
    body = 'emp,type,start,end,days\n1067,annual,2026-01-10,2026-01-12,3\n'
    client.post(f'{PREFIX}/batches/{bid}/file/', {'file': _csv(body)}, format='multipart')
    client.put(f'{PREFIX}/batches/{bid}/mapping/', {
        'columns': {
            'emp': 'employee_no', 'type': 'leave_type',
            'start': 'start_date', 'end': 'end_date', 'days': 'days',
        },
    }, format='json')
    client.post(f'{PREFIX}/batches/{bid}/smoke/', {}, format='json')
    _auth(client, cmt, get_token_for_user)
    res = client.post(f'{PREFIX}/batches/{bid}/commit/', {}, format='json')
    assert res.status_code == 200
    assert LeaveRecord.objects.count() == 1
    ent = LeaveEntitlement.objects.get(employee=emp, year=2026)
    assert ent.used_days == Decimal('5')
