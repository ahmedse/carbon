# people/tests/test_leave_list_perf.py
"""Leave HR list endpoints must stay O(1) queries and paginated."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement, LeaveRecord


@pytest.fixture
def leave_admin(db, create_user, create_scoped_role, get_token_for_user):
    user = create_user('leave_admin', password='x', is_superuser=True, is_staff=True)
    create_scoped_role(user, 'admin')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    return client


@pytest.fixture
def leave_seed(db):
    root = OrgUnit.objects.create(name='Leave Root', slug='leave-root-perf', org_type='company')
    rs, _ = ReferenceSet.objects.get_or_create(name='leave_type', defaults={'slug': 'leave-type'})
    annual, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs, code='annual', defaults={'label': 'Annual', 'is_active': True},
    )
    year = date.today().year
    for i in range(12):
        emp = Employee.objects.create(
            org_unit=root,
            employee_no=f'LP-{i:04d}',
            full_name=f'Leave Person {i}',
            basic_salary='0.000',
            is_active=True,
        )
        LeaveEntitlement.objects.create(
            employee=emp, year=year, leave_type=annual,
            entitled_days=Decimal('30'), used_days=Decimal('0'),
        )
        LeaveRecord.objects.create(
            employee=emp, leave_type=annual,
            start_date=date.today() + timedelta(days=i),
            end_date=date.today() + timedelta(days=i),
            days=Decimal('1'), status='draft',
        )
    return {'year': year, 'annual': annual}


@pytest.mark.django_db
def test_leave_entitlements_list_is_paginated_and_cheap(leave_admin, leave_seed):
    url = reverse('people-leave-entitlements')
    with CaptureQueriesContext(connection) as ctx:
        resp = leave_admin.get(url, {'year': leave_seed['year'], 'page_size': 50})
    assert resp.status_code == 200
    body = resp.json()
    assert 'results' in body
    assert body['page_size'] <= 200
    assert len(body['results']) <= body['page_size']
    assert body['results'][0].get('employee_name')
    assert body['results'][0].get('employee_no')
    # select_related: should not grow with page size (bound well under N*2)
    assert len(ctx) < 20


@pytest.mark.django_db
def test_leave_records_list_embeds_employee(leave_admin, leave_seed):
    url = reverse('people-leave-records')
    resp = leave_admin.get(url, {'page_size': 50})
    assert resp.status_code == 200
    row = resp.json()['results'][0]
    assert row['employee_name']
    assert row['employee_no']
    assert isinstance(row['days'], int) or isinstance(row['days'], float)
