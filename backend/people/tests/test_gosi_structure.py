"""Named committed-GOSI GET — separate from pay, compensation-gated."""
from datetime import date

import pytest

from catalog.models import GovernanceEvent
from mdm.models import OrgUnit
from people.gosi_structure import RETURNS, summarize_committed_gosi
from people.models import Employee, PayrollRun, PayslipLine, Position
from people.tests.ref_helpers import ensure_ref

SUMMARY = '/carbon-api/people/payslip-lines/gosi-summary/'
PAY = '/carbon-api/people/payslip-lines/summary/'


@pytest.fixture
def deployment_root(db):
    return OrgUnit.objects.create(
        name='Deployment Root', slug='gs-root', org_type='company',
    )


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='gs-org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='gs-org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def scene(org_a, org_b):
    kwt = ensure_ref('nationality', 'KWT', 'Kuwaiti')
    ind = ensure_ref('nationality', 'IND', 'Indian')
    pos = Position.objects.create(org_unit=org_a, code='GS-ENG', title='Engineer')
    gosi = ensure_ref('payslip_line_type', 'gosi')
    net = ensure_ref('payslip_line_type', 'net')
    emp1 = Employee.objects.create(
        org_unit=org_a, employee_no='GS-1', full_name='One',
        basic_salary='1000.000', join_date=date(2026, 1, 1),
        nationality=kwt, position=pos, is_active=True,
    )
    emp2 = Employee.objects.create(
        org_unit=org_a, employee_no='GS-2', full_name='Two',
        basic_salary='2000.000', join_date=date(2026, 1, 1),
        nationality=ind, position=pos, is_active=True,
    )
    emp3 = Employee.objects.create(
        org_unit=org_b, employee_no='GS-3', full_name='Three',
        basic_salary='3000.000', join_date=date(2026, 1, 1),
        nationality=kwt, is_active=True,
    )
    committed_a = PayrollRun.objects.create(
        org_unit=org_a, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
        status='committed', committed_at=date(2026, 10, 1),
    )
    committed_b = PayrollRun.objects.create(
        org_unit=org_b, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
        status='committed', committed_at=date(2026, 10, 1),
    )
    draft = PayrollRun.objects.create(
        org_unit=org_a, period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
        status='draft',
    )
    for emp, run, amount in (
        (emp1, committed_a, '80.000'),
        (emp2, committed_a, '160.000'),
        (emp3, committed_b, '240.000'),
        (emp1, draft, '999.000'),
    ):
        PayslipLine.objects.create(
            payroll_run=run, employee=emp, line_type=gosi, amount=amount,
            rule_id='test', rule_version='1',
        )
    PayslipLine.objects.create(
        payroll_run=committed_a, employee=emp1, line_type=net, amount='1000.000',
        rule_id='test', rule_version='1',
    )
    return {'org_a': org_a, 'org_b': org_b, 'gosi': gosi, 'committed_a': committed_a}


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_gosi_returns_declared_fields(scene, auth, create_user):
    client = auth(create_user('gs_admin', is_superuser=True))
    resp = client.get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'nationality'})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['line_type'] == 'gosi'
    assert data['status'] == 'committed'
    assert data['omitted'] == 0
    by_label = {row['label']: row for row in data['breakdown']}
    assert set(by_label) == {'KWT', 'IND'}
    kwt = by_label['KWT']
    assert kwt['headcount'] == 2
    assert kwt['total'] == '320.000'
    assert set(kwt) == {
        'label', 'headcount', 'average', 'median', 'min', 'max', 'total',
    }
    assert set(RETURNS) >= set(kwt)
    assert GovernanceEvent.objects.filter(action='view_compensation').count() == 1


@pytest.mark.django_db
def test_gosi_is_not_a_pay_line_type(scene, auth, create_user):
    resp = auth(create_user('gs_block', is_superuser=True)).get(
        PAY, {'period_end': '2026-09-30', 'dimension': 'org_unit', 'line_type': 'gosi'},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_gosi_403_without_compensation(scene, auth, create_user, create_scoped_role):
    user = create_user('gs_viewer')
    create_scoped_role(user, 'viewers_group')
    resp = auth(user).get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit'})
    assert resp.status_code == 403
    assert '80' not in str(resp.json())
    assert resp.json().get('breakdown') is None


@pytest.mark.django_db
def test_gosi_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('gs_scoped')
    create_scoped_role(user, 'admins_group', org_unit=scene['org_a'])
    resp = auth(user).get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Org A'}


@pytest.mark.django_db
def test_gosi_draft_period_is_empty(scene, auth, create_user):
    resp = auth(create_user('gs_draft', is_superuser=True)).get(
        SUMMARY, {'period_end': '2026-10-31', 'dimension': 'org_unit'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['breakdown'] == []
    assert data['run_ids'] == []


@pytest.mark.django_db
def test_http_matches_summarize(scene, auth, create_user):
    user = create_user('gs_match', is_superuser=True)
    code, payload = summarize_committed_gosi(
        user, period_end='2026-09-30', dimension='org_unit',
    )
    resp = auth(user).get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit'})
    assert resp.status_code == code
    assert resp.json()['breakdown'] == payload['breakdown']


@pytest.mark.django_db
def test_in_process_uses_same_view(scene, create_user):
    from asgiref.sync import async_to_sync
    from ai.host_executor import CarbonHostExecutor

    user = create_user('gs_inproc', is_superuser=True)
    exe = CarbonHostExecutor(
        db=None, instance_config={},
        user_token=f"inproc:nibras:{user.pk}", host_user_id=str(user.pk),
    )
    out = async_to_sync(exe._people_in_process)(
        method="GET",
        params={"period_end": "2026-09-30", "dimension": "org_unit"},
        body={},
        endpoint="carbon-api/people/payslip-lines/gosi-summary",
    )
    assert out["status_code"] == 200, out
    assert out["data"]["line_type"] == "gosi"
