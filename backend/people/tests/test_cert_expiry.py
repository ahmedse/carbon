"""Named certification-expiry GET — counts only, closed horizon."""
from datetime import date

import pytest

from mdm.models import OrgUnit
from people.cert_expiry import RETURNS, summarize_cert_expiry
from people.models import Certification, Employee
from people.tests.ref_helpers import ensure_ref

SUMMARY = '/carbon-api/people/certifications/summary/'


@pytest.fixture
def deployment_root(db):
    return OrgUnit.objects.create(
        name='Deployment Root', slug='ce-root', org_type='company',
    )


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='ce-org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='ce-org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def scene(org_a, org_b):
    twic = ensure_ref('cert_type', 'twic', 'TWIC')
    h2s = ensure_ref('cert_type', 'h2s', 'H2S')
    emp1 = Employee.objects.create(
        org_unit=org_a, employee_no='CE-1', full_name='One',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    emp2 = Employee.objects.create(
        org_unit=org_a, employee_no='CE-2', full_name='Two',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    emp3 = Employee.objects.create(
        org_unit=org_b, employee_no='CE-3', full_name='Three',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    as_of = date(2026, 9, 25)
    Certification.objects.create(
        employee=emp1, cert_type=twic, expiry_date=date(2026, 8, 1),
    )
    Certification.objects.create(
        employee=emp1, cert_type=h2s, expiry_date=date(2026, 10, 10),
    )
    Certification.objects.create(
        employee=emp2, cert_type=twic, expiry_date=date(2027, 1, 1),
    )
    Certification.objects.create(
        employee=emp2, cert_type=h2s, expiry_date=None,
    )
    Certification.objects.create(
        employee=emp3, cert_type=twic, expiry_date=date(2026, 9, 1),
    )
    return {'org_a': org_a, 'org_b': org_b, 'as_of': as_of}


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_expiry_returns_declared_fields(scene, auth, create_user):
    client = auth(create_user('ce_admin', is_superuser=True))
    resp = client.get(SUMMARY, {
        'horizon': '90', 'dimension': 'org_unit', 'as_of': '2026-09-25',
    })
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['horizon'] == 90
    assert data['as_of'] == '2026-09-25'
    assert data['omitted'] == 1
    by_label = {row['label']: row for row in data['breakdown']}
    org_a = by_label['Org A']
    assert org_a['expired'] == 1
    assert org_a['expiring'] == 1
    assert org_a['current'] == 1
    assert set(org_a) == set(RETURNS)
    org_b = by_label['Org B']
    assert org_b['expired'] == 1
    assert org_b['expiring'] == 0
    assert org_b['current'] == 0


@pytest.mark.django_db
def test_expiry_by_cert_type(scene, auth, create_user):
    resp = auth(create_user('ce_type', is_superuser=True)).get(
        SUMMARY, {'horizon': '90', 'dimension': 'cert_type', 'as_of': '2026-09-25'},
    )
    by_label = {row['label']: row for row in resp.json()['breakdown']}
    assert set(by_label) == {'twic', 'h2s'}


@pytest.mark.django_db
def test_expiry_403_without_people_view(scene, auth, create_user):
    resp = auth(create_user('ce_ess')).get(
        SUMMARY, {'horizon': '90', 'dimension': 'org_unit', 'as_of': '2026-09-25'},
    )
    assert resp.status_code == 403
    assert resp.json().get('breakdown') is None


@pytest.mark.django_db
def test_expiry_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('ce_scoped')
    create_scoped_role(user, 'viewers_group', org_unit=scene['org_a'])
    resp = auth(user).get(SUMMARY, {
        'horizon': '90', 'dimension': 'org_unit', 'as_of': '2026-09-25',
    })
    assert resp.status_code == 200, resp.content
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Org A'}


@pytest.mark.django_db
def test_expiry_unknown_horizon_400(scene, auth, create_user):
    resp = auth(create_user('ce_bad', is_superuser=True)).get(
        SUMMARY, {'horizon': '45', 'dimension': 'org_unit', 'as_of': '2026-09-25'},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_expiry_empty(auth, create_user, db):
    resp = auth(create_user('ce_empty', is_superuser=True)).get(
        SUMMARY, {'horizon': '90', 'dimension': 'org_unit', 'as_of': '2026-09-25'},
    )
    assert resp.status_code == 200
    assert resp.json()['breakdown'] == []


@pytest.mark.django_db
def test_http_matches_summarize(scene, auth, create_user):
    user = create_user('ce_match', is_superuser=True)
    code, payload = summarize_cert_expiry(
        user, horizon='90', dimension='org_unit', as_of='2026-09-25',
    )
    resp = auth(user).get(SUMMARY, {
        'horizon': '90', 'dimension': 'org_unit', 'as_of': '2026-09-25',
    })
    assert resp.status_code == code
    assert resp.json()['breakdown'] == payload['breakdown']


@pytest.mark.django_db
def test_in_process_uses_same_view(scene, create_user):
    from asgiref.sync import async_to_sync
    from ai.host_executor import CarbonHostExecutor

    user = create_user('ce_inproc', is_superuser=True)
    exe = CarbonHostExecutor(
        db=None, instance_config={},
        user_token=f"inproc:nibras:{user.pk}", host_user_id=str(user.pk),
    )
    out = async_to_sync(exe._people_in_process)(
        method="GET",
        params={"horizon": "90", "dimension": "org_unit", "as_of": "2026-09-25"},
        body={},
        endpoint="carbon-api/people/certifications/summary",
    )
    assert out["status_code"] == 200, out
    assert out["data"]["omitted"] == 1
