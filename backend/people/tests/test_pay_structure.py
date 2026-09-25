"""Named committed-pay GET — closed query, declared fields, CBAC."""
from datetime import date
from decimal import Decimal

import pytest

from catalog.models import GovernanceEvent
from mdm.models import OrgUnit
from people.models import Employee, PayrollRun, PayslipLine, Position
from people.tests.ref_helpers import ensure_ref

SUMMARY = '/carbon-api/people/payslip-lines/summary/'
RUNS = '/carbon-api/people/payroll-runs/'


@pytest.fixture
def deployment_root(db):
    return OrgUnit.objects.create(
        name='Deployment Root', slug='pay-root', org_type='company',
    )


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='pay-org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='pay-org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def scene(org_a, org_b):
    kwt = ensure_ref('nationality', 'KWT', 'Kuwaiti')
    ind = ensure_ref('nationality', 'IND', 'Indian')
    pos = Position.objects.create(org_unit=org_a, code='ENG', title='Engineer')
    net = ensure_ref('payslip_line_type', 'net')
    emp1 = Employee.objects.create(
        org_unit=org_a, employee_no='PAY-1', full_name='One',
        basic_salary='1000.000', join_date=date(2026, 1, 1),
        nationality=kwt, position=pos, is_active=True,
    )
    emp2 = Employee.objects.create(
        org_unit=org_a, employee_no='PAY-2', full_name='Two',
        basic_salary='2000.000', join_date=date(2026, 1, 1),
        nationality=ind, position=pos, is_active=True,
    )
    emp3 = Employee.objects.create(
        org_unit=org_b, employee_no='PAY-3', full_name='Three',
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
        (emp1, committed_a, '1000.000'),
        (emp2, committed_a, '2000.000'),
        (emp3, committed_b, '3000.000'),
        (emp1, draft, '9999.000'),
    ):
        PayslipLine.objects.create(
            payroll_run=run, employee=emp, line_type=net, amount=amount,
            rule_id='test', rule_version='1',
        )
    return {
        'org_a': org_a, 'org_b': org_b, 'emp1': emp1, 'net': net,
        'committed_a': committed_a, 'draft': draft,
    }


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_summary_returns_declared_fields(scene, auth, create_user):
    client = auth(create_user('pay_admin', is_superuser=True))
    resp = client.get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'nationality'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['period_end'] == '2026-09-30'
    assert data['dimension'] == 'nationality'
    assert data['line_type'] == 'net'
    assert data['status'] == 'committed'
    assert data['omitted'] == 0
    by_label = {row['label']: row for row in data['breakdown']}
    assert set(by_label) == {'KWT', 'IND'}
    kwt = by_label['KWT']
    assert kwt['headcount'] == 2
    assert kwt['total'] == '4000.000'
    assert kwt['average'] == '2000.000'
    assert kwt['median'] == '2000.000'
    assert kwt['min'] == '1000.000'
    assert kwt['max'] == '3000.000'
    assert set(kwt) == {
        'label', 'headcount', 'average', 'median', 'min', 'max', 'total',
    }
    assert GovernanceEvent.objects.filter(action='view_compensation').count() == 1


@pytest.mark.django_db
def test_summary_403_without_compensation(scene, auth, create_user, create_scoped_role):
    user = create_user('pay_viewer')
    create_scoped_role(user, 'viewers_group')
    resp = auth(user).get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit'})
    assert resp.status_code == 403
    body = resp.json()
    assert '1000' not in str(body)
    assert 'average' not in body


@pytest.mark.django_db
def test_summary_draft_period_is_empty(scene, auth, create_user):
    client = auth(create_user('pay_admin2', is_superuser=True))
    resp = client.get(SUMMARY, {'period_end': '2026-10-31', 'dimension': 'org_unit'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['breakdown'] == []
    assert data['run_ids'] == []
    assert any('No committed pay lines' in c for c in data['caveats'])


@pytest.mark.django_db
def test_summary_omits_duplicate_lines(scene, auth, create_user):
    PayslipLine.objects.create(
        payroll_run=scene['committed_a'], employee=scene['emp1'],
        line_type=scene['net'], amount='1111.000',
        rule_id='test', rule_version='1',
    )
    client = auth(create_user('pay_admin3', is_superuser=True))
    resp = client.get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['omitted'] == 1
    by_label = {row['label']: row for row in data['breakdown']}
    assert by_label['Org A']['headcount'] == 1
    assert by_label['Org A']['total'] == '2000.000'
    assert Decimal(by_label['Org A']['total']) != Decimal('4111.000')


@pytest.mark.django_db
def test_summary_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('pay_scoped')
    create_scoped_role(user, 'admins_group', org_unit=scene['org_a'])
    resp = auth(user).get(SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit'})
    assert resp.status_code == 200
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Org A'}


@pytest.mark.django_db
def test_summary_unknown_dimension_400(scene, auth, create_user):
    resp = auth(create_user('pay_admin4', is_superuser=True)).get(
        SUMMARY, {'period_end': '2026-09-30', 'dimension': 'gender'},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_summary_rejects_gosi_line_type(scene, auth, create_user):
    resp = auth(create_user('pay_gosi_block', is_superuser=True)).get(
        SUMMARY, {'period_end': '2026-09-30', 'dimension': 'org_unit', 'line_type': 'gosi'},
    )
    assert resp.status_code == 400
    assert 'gosi' in resp.json()['detail']


@pytest.mark.django_db
def test_list_runs_status_filter(scene, auth, create_user):
    client = auth(create_user('pay_admin5', is_superuser=True))
    committed = client.get(RUNS, {'status': 'committed'})
    assert committed.status_code == 200
    assert {row['status'] for row in committed.json()['results']} == {'committed'}
    draft = client.get(RUNS, {'status': 'draft'})
    assert {row['status'] for row in draft.json()['results']} == {'draft'}
    bad = client.get(RUNS, {'status': 'nope'})
    assert bad.status_code == 400
