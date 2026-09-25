"""Named leave-utilization GET — days only, closed query, CBAC."""
from datetime import date
from decimal import Decimal

import pytest

from mdm.models import OrgUnit
from people.leave_utilization import RETURNS, summarize_leave_utilization
from people.models import Employee, LeaveEntitlement, Position
from people.tests.ref_helpers import ensure_ref

SUMMARY = '/carbon-api/people/leave-entitlements/summary/'


@pytest.fixture
def deployment_root(db):
    return OrgUnit.objects.create(
        name='Deployment Root', slug='lu-root', org_type='company',
    )


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='lu-org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='lu-org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def scene(org_a, org_b):
    kwt = ensure_ref('nationality', 'KWT', 'Kuwaiti')
    annual = ensure_ref('leave_type', 'annual', 'Annual')
    sick = ensure_ref('leave_type', 'sick', 'Sick')
    pos = Position.objects.create(org_unit=org_a, code='LU-ENG', title='Engineer')
    emp1 = Employee.objects.create(
        org_unit=org_a, employee_no='LU-1', full_name='One',
        basic_salary='1.000', join_date=date(2026, 1, 1),
        nationality=kwt, position=pos, is_active=True,
    )
    emp2 = Employee.objects.create(
        org_unit=org_a, employee_no='LU-2', full_name='Two',
        basic_salary='1.000', join_date=date(2026, 1, 1),
        nationality=kwt, is_active=True,
    )
    emp3 = Employee.objects.create(
        org_unit=org_b, employee_no='LU-3', full_name='Three',
        basic_salary='1.000', join_date=date(2026, 1, 1),
        nationality=kwt, is_active=True,
    )
    LeaveEntitlement.objects.create(
        employee=emp1, year=2026, leave_type=annual,
        entitled_days=Decimal('20.00'), used_days=Decimal('5.00'),
        carried_forward=Decimal('2.00'),
    )
    LeaveEntitlement.objects.create(
        employee=emp2, year=2026, leave_type=sick,
        entitled_days=Decimal('10.00'), used_days=Decimal('0.00'),
    )
    LeaveEntitlement.objects.create(
        employee=emp3, year=2026, leave_type=annual,
        entitled_days=Decimal('30.00'), used_days=Decimal('10.00'),
    )
    LeaveEntitlement.objects.create(
        employee=emp1, year=2025, leave_type=annual,
        entitled_days=Decimal('99.00'), used_days=Decimal('99.00'),
    )
    return {'org_a': org_a, 'org_b': org_b, 'annual': annual}


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_utilization_returns_declared_day_fields(scene, auth, create_user):
    client = auth(create_user('lu_admin', is_superuser=True))
    resp = client.get(SUMMARY, {'year': '2026', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['year'] == 2026
    assert data['dimension'] == 'org_unit'
    by_label = {row['label']: row for row in data['breakdown']}
    assert set(by_label) == {'Org A', 'Org B'}
    org_a = by_label['Org A']
    assert org_a['headcount'] == 2
    assert org_a['entitled_days'] == '32.00'  # 20+2 + 10
    assert org_a['used_days'] == '5.00'
    assert org_a['remaining_days'] == '27.00'
    assert org_a['utilization_pct'] == 15.63  # 5 / 32
    assert set(org_a) == set(RETURNS)
    assert 'amount' not in org_a
    assert 'total' not in org_a


@pytest.mark.django_db
def test_utilization_by_leave_type(scene, auth, create_user):
    resp = auth(create_user('lu_type', is_superuser=True)).get(
        SUMMARY, {'year': '2026', 'dimension': 'leave_type'},
    )
    by_label = {row['label']: row for row in resp.json()['breakdown']}
    assert set(by_label) == {'annual', 'sick'}
    assert by_label['annual']['headcount'] == 2
    assert by_label['annual']['entitled_days'] == '52.00'


@pytest.mark.django_db
def test_utilization_403_without_people_view(scene, auth, create_user):
    resp = auth(create_user('lu_ess')).get(SUMMARY, {'year': '2026', 'dimension': 'org_unit'})
    assert resp.status_code == 403
    assert resp.json().get('breakdown') is None


@pytest.mark.django_db
def test_utilization_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('lu_scoped')
    create_scoped_role(user, 'viewers_group', org_unit=scene['org_a'])
    resp = auth(user).get(SUMMARY, {'year': '2026', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Org A'}


@pytest.mark.django_db
def test_utilization_empty_year(scene, auth, create_user):
    resp = auth(create_user('lu_empty', is_superuser=True)).get(
        SUMMARY, {'year': '2024', 'dimension': 'org_unit'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['breakdown'] == []
    assert data['caveats']


@pytest.mark.django_db
def test_utilization_unknown_dimension_400(scene, auth, create_user):
    resp = auth(create_user('lu_bad', is_superuser=True)).get(
        SUMMARY, {'year': '2026', 'dimension': 'gender'},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_http_matches_summarize(scene, auth, create_user):
    user = create_user('lu_match', is_superuser=True)
    code, payload = summarize_leave_utilization(user, year='2026', dimension='org_unit')
    resp = auth(user).get(SUMMARY, {'year': '2026', 'dimension': 'org_unit'})
    assert resp.status_code == code
    assert resp.json()['breakdown'] == payload['breakdown']


@pytest.mark.django_db
def test_in_process_uses_same_view(scene, create_user):
    from asgiref.sync import async_to_sync
    from ai.host_executor import CarbonHostExecutor

    user = create_user('lu_inproc', is_superuser=True)
    exe = CarbonHostExecutor(
        db=None, instance_config={},
        user_token=f"inproc:nibras:{user.pk}", host_user_id=str(user.pk),
    )
    out = async_to_sync(exe._people_in_process)(
        method="GET", params={"year": "2026", "dimension": "org_unit"}, body={},
        endpoint="carbon-api/people/leave-entitlements/summary",
    )
    assert out["status_code"] == 200, out
    labels = {row["label"] for row in out["data"]["breakdown"]}
    assert labels == {"Org A", "Org B"}
