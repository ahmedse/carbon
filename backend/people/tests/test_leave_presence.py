"""Named leave-presence GET — org month, not Team Who's Out."""
from datetime import date
from decimal import Decimal

import pytest

from mdm.models import OrgUnit
from people.leave_presence import RETURNS, summarize_leave_presence
from people.models import Employee, LeaveRecord
from people.tests.ref_helpers import ensure_ref

PRESENCE = '/carbon-api/people/leave-records/presence/'


@pytest.fixture
def deployment_root(db):
    return OrgUnit.objects.create(
        name='Deployment Root', slug='lp-root', org_type='company',
    )


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='lp-org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='lp-org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def scene(org_a, org_b):
    annual = ensure_ref('leave_type', 'annual', 'Annual')
    sick = ensure_ref('leave_type', 'sick', 'Sick')
    emp1 = Employee.objects.create(
        org_unit=org_a, employee_no='LP-1', full_name='One',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    emp2 = Employee.objects.create(
        org_unit=org_a, employee_no='LP-2', full_name='Two',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    emp3 = Employee.objects.create(
        org_unit=org_b, employee_no='LP-3', full_name='Three',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    LeaveRecord.objects.create(
        employee=emp1, leave_type=annual,
        start_date=date(2026, 9, 15), end_date=date(2026, 9, 16),
        days=Decimal('2.00'), status='approved',
    )
    LeaveRecord.objects.create(
        employee=emp1, leave_type=annual,
        start_date=date(2026, 9, 29), end_date=date(2026, 10, 2),
        days=Decimal('4.00'), status='submitted',
    )
    LeaveRecord.objects.create(
        employee=emp2, leave_type=sick,
        start_date=date(2026, 9, 10), end_date=date(2026, 9, 10),
        days=Decimal('1.00'), status='draft',
    )
    LeaveRecord.objects.create(
        employee=emp2, leave_type=sick,
        start_date=date(2026, 9, 12), end_date=date(2026, 9, 12),
        days=Decimal('1.00'), status='rejected',
    )
    LeaveRecord.objects.create(
        employee=emp3, leave_type=annual,
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 3),
        days=Decimal('3.00'), status='approved',
    )
    return {'org_a': org_a, 'org_b': org_b}


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_presence_returns_declared_fields(scene, auth, create_user):
    client = auth(create_user('lp_admin', is_superuser=True))
    resp = client.get(PRESENCE, {'year': '2026', 'month': '9', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['year'] == 2026
    assert data['month'] == 9
    assert data['status'] == ['submitted', 'approved']
    by_label = {row['label']: row for row in data['breakdown']}
    org_a = by_label['Org A']
    assert org_a['on_leave_count'] == 1
    assert org_a['days'] == '4.00'  # 2 in-month + 2/4 of spanning 4 days
    assert set(org_a) == set(RETURNS)
    assert by_label['Org B']['on_leave_count'] == 1
    assert by_label['Org B']['days'] == '3.00'


@pytest.mark.django_db
def test_presence_ignores_draft_and_rejected(scene, auth, create_user):
    resp = auth(create_user('lp_ignore', is_superuser=True)).get(
        PRESENCE, {'year': '2026', 'month': '9', 'dimension': 'leave_type'},
    )
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'annual'}


@pytest.mark.django_db
def test_presence_403_without_people_view(scene, auth, create_user):
    resp = auth(create_user('lp_ess')).get(
        PRESENCE, {'year': '2026', 'month': '9', 'dimension': 'org_unit'},
    )
    assert resp.status_code == 403
    assert resp.json().get('breakdown') is None


@pytest.mark.django_db
def test_presence_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('lp_scoped')
    create_scoped_role(user, 'viewers_group', org_unit=scene['org_a'])
    resp = auth(user).get(PRESENCE, {'year': '2026', 'month': '9', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Org A'}


@pytest.mark.django_db
def test_presence_empty_month(scene, auth, create_user):
    resp = auth(create_user('lp_empty', is_superuser=True)).get(
        PRESENCE, {'year': '2026', 'month': '1', 'dimension': 'org_unit'},
    )
    assert resp.status_code == 200
    assert resp.json()['breakdown'] == []


@pytest.mark.django_db
def test_presence_unknown_dimension_400(scene, auth, create_user):
    resp = auth(create_user('lp_bad', is_superuser=True)).get(
        PRESENCE, {'year': '2026', 'month': '9', 'dimension': 'gender'},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_http_matches_summarize(scene, auth, create_user):
    user = create_user('lp_match', is_superuser=True)
    code, payload = summarize_leave_presence(
        user, year='2026', month='9', dimension='org_unit',
    )
    resp = auth(user).get(PRESENCE, {'year': '2026', 'month': '9', 'dimension': 'org_unit'})
    assert resp.status_code == code
    assert resp.json()['breakdown'] == payload['breakdown']


@pytest.mark.django_db
def test_in_process_uses_same_view(scene, create_user):
    from asgiref.sync import async_to_sync
    from ai.host_executor import CarbonHostExecutor

    user = create_user('lp_inproc', is_superuser=True)
    exe = CarbonHostExecutor(
        db=None, instance_config={},
        user_token=f"inproc:nibras:{user.pk}", host_user_id=str(user.pk),
    )
    out = async_to_sync(exe._people_in_process)(
        method="GET",
        params={"year": "2026", "month": "9", "dimension": "org_unit"},
        body={},
        endpoint="carbon-api/people/leave-records/presence",
    )
    assert out["status_code"] == 200, out
    assert out["data"]["month"] == 9
