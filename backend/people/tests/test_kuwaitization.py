"""Named KOC Kuwaitization GET — closed population, declared fields, CBAC."""
from datetime import date

import pytest

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.kuwaitization import RETURNS, summarize_kuwaitization
from people.models import Employee
from people.tests.ref_helpers import ensure_ref

QUOTA = '/carbon-api/people/compliance/kuwaitization/'


@pytest.fixture
def root(db):
    return OrgUnit.objects.create(
        name='KOC Root', slug='koc-root', org_type='company',
    )


@pytest.fixture
def coiled(root):
    return OrgUnit.objects.create(
        name='Coiled Tubing', slug='koc-ct', parent=root, org_type='division',
    )


@pytest.fixture
def drilling(root):
    return OrgUnit.objects.create(
        name='Drilling', slug='koc-dr', parent=root, org_type='division',
    )


@pytest.fixture
def contracts(db):
    rs, _ = ReferenceSet.objects.get_or_create(
        slug='koc-contract',
        defaults={'name': 'KOC Contract'},
    )
    coiled, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs, code='coiled_tubing',
        defaults={
            'label': 'Coiled Tubing', 'is_active': True, 'sort_order': 1,
            'metadata': {'contract_no': 'CT-1', 'required': 2},
        },
    )
    if coiled.metadata.get('required') != 2:
        coiled.metadata = {'contract_no': 'CT-1', 'required': 2}
        coiled.label = 'Coiled Tubing'
        coiled.is_active = True
        coiled.save()
    drill, _ = ReferenceValue.objects.get_or_create(
        reference_set=rs, code='drilling_60',
        defaults={
            'label': 'Drilling 60', 'is_active': True, 'sort_order': 2,
            'metadata': {'contract_no': 'DR-60', 'required': 1},
        },
    )
    if drill.metadata.get('required') != 1:
        drill.metadata = {'contract_no': 'DR-60', 'required': 1}
        drill.label = 'Drilling 60'
        drill.is_active = True
        drill.save()
    return rs


@pytest.fixture
def scene(coiled, drilling, contracts):
    kwt = ensure_ref('nationality', 'KWT', 'Kuwaiti')
    ind = ensure_ref('nationality', 'IND', 'Indian')
    Employee.objects.create(
        org_unit=coiled, employee_no='KZ-1', full_name='Flagged',
        basic_salary='1.000', join_date=date(2026, 1, 1),
        nationality=kwt, kuwaitization=True, is_active=True,
    )
    Employee.objects.create(
        org_unit=coiled, employee_no='KZ-2', full_name='KWT only',
        basic_salary='1.000', join_date=date(2026, 1, 1),
        nationality=kwt, kuwaitization=False, is_active=True,
    )
    Employee.objects.create(
        org_unit=drilling, employee_no='KZ-3', full_name='Driller',
        basic_salary='1.000', join_date=date(2026, 1, 1),
        nationality=ind, kuwaitization=True, is_active=True,
    )
    return {'coiled': coiled, 'drilling': drilling}


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_quota_returns_declared_fields(scene, auth, create_user):
    client = auth(create_user('kz_admin', is_superuser=True))
    resp = client.get(QUOTA)
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['dimension'] == 'koc_contract'
    assert data['flag'] == 'kuwaitization'
    by_label = {row['label']: row for row in data['breakdown']}
    assert 'Coiled Tubing' in by_label
    coiled = by_label['Coiled Tubing']
    assert coiled['required'] == 2
    assert coiled['actual'] == 1
    assert coiled['deficit'] == 1
    assert coiled['fill_rate_pct'] == 50.0
    assert coiled['status'] == 'non_compliant'
    assert coiled['contract_no'] == 'CT-1'
    assert set(coiled) == set(RETURNS)
    assert 'reimbursement' not in coiled
    drill = by_label['Drilling 60']
    assert drill['actual'] == 1
    assert drill['deficit'] == 0
    assert drill['status'] == 'compliant'


@pytest.mark.django_db
def test_quota_counts_flag_not_nationality(scene, auth, create_user):
    """KZ-2 is KWT nationality but kuwaitization=False — must not count."""
    client = auth(create_user('kz_admin2', is_superuser=True))
    coiled = next(
        row for row in client.get(QUOTA).json()['breakdown']
        if row['label'] == 'Coiled Tubing'
    )
    assert coiled['actual'] == 1


@pytest.mark.django_db
def test_quota_403_without_people_view(scene, auth, create_user):
    resp = auth(create_user('kz_ess')).get(QUOTA)
    assert resp.status_code == 403
    assert 'required' not in resp.json() or 'detail' in resp.json()
    assert resp.json().get('breakdown') is None


@pytest.mark.django_db
def test_quota_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('kz_scoped')
    create_scoped_role(user, 'viewers_group', org_unit=scene['coiled'])
    resp = auth(user).get(QUOTA)
    assert resp.status_code == 200, resp.content
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Coiled Tubing'}


@pytest.mark.django_db
def test_quota_empty_without_contracts(auth, create_user, db):
    client = auth(create_user('kz_empty', is_superuser=True))
    resp = client.get(QUOTA)
    assert resp.status_code == 200
    data = resp.json()
    assert data['breakdown'] == []
    assert data['caveats']


@pytest.mark.django_db
def test_http_matches_summarize(scene, auth, create_user):
    user = create_user('kz_admin3', is_superuser=True)
    code, payload = summarize_kuwaitization(user)
    resp = auth(user).get(QUOTA)
    assert resp.status_code == code
    assert resp.json()['breakdown'] == payload['breakdown']


@pytest.mark.django_db
def test_in_process_uses_same_view(scene, create_user):
    from asgiref.sync import async_to_sync
    from ai.host_executor import CarbonHostExecutor

    user = create_user('kz_admin4', is_superuser=True)
    exe = CarbonHostExecutor(
        db=None, instance_config={},
        user_token=f"inproc:nibras:{user.pk}", host_user_id=str(user.pk),
    )
    out = async_to_sync(exe._people_in_process)(
        method="GET", params={}, body={},
        endpoint="carbon-api/people/compliance/kuwaitization",
    )
    assert out["status_code"] == 200, out
    assert out["data"]["dimension"] == "koc_contract"
    labels = {row["label"] for row in out["data"]["breakdown"]}
    assert "Coiled Tubing" in labels
