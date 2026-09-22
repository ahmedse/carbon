# people/tests/test_team_manager_reads.py
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.conf import settings
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveRecord

PREFIX = f'/{settings.API_PREFIX.strip("/")}'
REPORTS_URL = f'{PREFIX}/people/me/direct-reports/'
TEAM_LEAVE_URL = f'{PREFIX}/people/me/team-leave/'


@pytest.fixture
def manager_world(db, create_user, create_scoped_role):
    org = OrgUnit.objects.create(
        name='Team Reads OU', slug='team-reads-ou', org_type='department',
    )
    mgr_user = create_user('team_mgr_r', password='x', is_staff=True)
    create_scoped_role(mgr_user, 'manager_group', org_unit=org)
    rep_user = create_user('team_rep_r', password='x')
    create_scoped_role(rep_user, 'employee_group')
    mgr = Employee.objects.create(
        org_unit=org, employee_no='TM-MGR', full_name='Team Mgr',
        user=mgr_user, basic_salary=Decimal('0'), join_date=date(2026, 1, 1),
        is_active=True,
    )
    rep = Employee.objects.create(
        org_unit=org, employee_no='TM-REP', full_name='Team Rep',
        user=rep_user, manager=mgr, basic_salary=Decimal('0'),
        join_date=date(2026, 1, 1), is_active=True,
    )
    leave_set, _ = ReferenceSet.objects.get_or_create(
        name='leave_type', defaults={'slug': 'leave-type'},
    )
    annual, _ = ReferenceValue.objects.get_or_create(
        reference_set=leave_set, code='annual',
        defaults={'label': 'Annual', 'is_active': True},
    )
    LeaveRecord.objects.create(
        employee=rep, leave_type=annual,
        start_date=date(2026, 9, 10), end_date=date(2026, 9, 12),
        days=Decimal('3'), status='approved',
    )
    return SimpleNamespace(mgr_user=mgr_user, rep=rep, mgr=mgr)


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')


@pytest.mark.django_db
def test_direct_reports_lists_reports(manager_world, api_client, get_token_for_user):
    _auth(api_client, manager_world.mgr_user, get_token_for_user)
    resp = api_client.get(REPORTS_URL)
    assert resp.status_code == 200, resp.content
    nos = {row['employee_no'] for row in resp.json()}
    assert 'TM-REP' in nos
    assert 'TM-MGR' not in nos


@pytest.mark.django_db
def test_team_leave_month_overlap(manager_world, api_client, get_token_for_user):
    _auth(api_client, manager_world.mgr_user, get_token_for_user)
    resp = api_client.get(TEAM_LEAVE_URL, {'year': 2026, 'month': 9})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['year'] == 2026 and data['month'] == 9
    assert len(data['items']) == 1
    assert data['items'][0]['employee_no'] == 'TM-REP'
    assert data['items'][0]['leave_type'] == 'annual'


@pytest.mark.django_db
def test_team_leave_empty_other_month(manager_world, api_client, get_token_for_user):
    _auth(api_client, manager_world.mgr_user, get_token_for_user)
    resp = api_client.get(TEAM_LEAVE_URL, {'year': 2026, 'month': 1})
    assert resp.status_code == 200
    assert resp.json()['items'] == []
