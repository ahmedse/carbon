"""Named loan-book GET — outstanding principal, compensation-gated."""
from datetime import date
from decimal import Decimal

import pytest

from catalog.models import GovernanceEvent
from mdm.models import OrgUnit
from people.loan_book import RETURNS, summarize_loan_book
from people.models import Employee, Loan, LoanInstallment
from people.tests.ref_helpers import ensure_ref

SUMMARY = '/carbon-api/people/loans/summary/'


def test_list_loans_catalog_returns_match_serializer():
    from pathlib import Path

    import yaml

    from people.serializers import LoanSerializer

    inst = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "ai" / "engine" / "instances"
         / "nibras" / "instance.yaml").read_text(encoding="utf-8")
    )
    entry = next(
        e for e in (inst.get("api_catalog") or [])
        if isinstance(e, dict) and e.get("name") == "list_loans"
    )
    host = set(LoanSerializer.Meta.fields)
    claimed = set(entry.get("returns") or [])
    assert claimed <= host
    assert "remaining_balance" not in host
    assert "monthly_installment" not in host


@pytest.fixture
def deployment_root(db):
    return OrgUnit.objects.create(
        name='Deployment Root', slug='lb-root', org_type='company',
    )


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='lb-org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='lb-org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def scene(org_a, org_b):
    emergency = ensure_ref('loan_type', 'emergency', 'Emergency')
    housing = ensure_ref('loan_type', 'housing', 'Housing')
    emp1 = Employee.objects.create(
        org_unit=org_a, employee_no='LB-1', full_name='One',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    emp2 = Employee.objects.create(
        org_unit=org_a, employee_no='LB-2', full_name='Two',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    emp3 = Employee.objects.create(
        org_unit=org_b, employee_no='LB-3', full_name='Three',
        basic_salary='1.000', join_date=date(2026, 1, 1), is_active=True,
    )
    scheduled = Loan.objects.create(
        employee=emp1, loan_type=emergency, principal=Decimal('1000.000'),
        term_months=2, start_date=date(2026, 8, 1), status='active',
    )
    LoanInstallment.objects.create(
        loan=scheduled, installment_no=1, due_date=date(2026, 8, 31),
        amount=Decimal('400.000'), principal_portion=Decimal('400.000'),
        interest_portion=Decimal('0.000'), status='paid',
    )
    LoanInstallment.objects.create(
        loan=scheduled, installment_no=2, due_date=date(2026, 9, 30),
        amount=Decimal('600.000'), principal_portion=Decimal('600.000'),
        interest_portion=Decimal('0.000'), status='scheduled',
    )
    Loan.objects.create(
        employee=emp2, loan_type=housing, principal=Decimal('500.000'),
        term_months=6, start_date=date(2026, 9, 1), status='active',
    )
    Loan.objects.create(
        employee=emp3, loan_type=emergency, principal=Decimal('2000.000'),
        term_months=1, start_date=date(2026, 1, 1), status='paid_off',
    )
    return {'org_a': org_a, 'org_b': org_b}


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


@pytest.mark.django_db
def test_book_returns_declared_money_fields(scene, auth, create_user):
    client = auth(create_user('lb_admin', is_superuser=True))
    resp = client.get(SUMMARY, {'as_of': '2026-09-15', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['as_of'] == '2026-09-15'
    assert data['dimension'] == 'org_unit'
    by_label = {row['label']: row for row in data['breakdown']}
    org_a = by_label['Org A']
    assert org_a['count'] == 2
    assert org_a['principal_total'] == '1500.000'
    assert org_a['remaining_total'] == '1100.000'  # 600 unpaid + 500 no schedule
    assert set(org_a) == set(RETURNS)
    org_b = by_label['Org B']
    assert org_b['count'] == 1
    assert org_b['remaining_total'] == '0.000'
    assert GovernanceEvent.objects.filter(action='view_compensation').count() == 1


@pytest.mark.django_db
def test_book_by_status(scene, auth, create_user):
    resp = auth(create_user('lb_status', is_superuser=True)).get(
        SUMMARY, {'as_of': '2026-09-15', 'dimension': 'status'},
    )
    by_label = {row['label']: row for row in resp.json()['breakdown']}
    assert by_label['paid_off']['remaining_total'] == '0.000'
    assert by_label['active']['count'] == 2


@pytest.mark.django_db
def test_book_403_without_compensation(scene, auth, create_user, create_scoped_role):
    user = create_user('lb_viewer')
    create_scoped_role(user, 'viewers_group')
    resp = auth(user).get(SUMMARY, {'as_of': '2026-09-15', 'dimension': 'org_unit'})
    assert resp.status_code == 403
    body = resp.json()
    assert '1000' not in str(body)
    assert body.get('breakdown') is None


@pytest.mark.django_db
def test_book_org_scope(scene, auth, create_user, create_scoped_role):
    user = create_user('lb_scoped')
    create_scoped_role(user, 'admins_group', org_unit=scene['org_a'])
    resp = auth(user).get(SUMMARY, {'as_of': '2026-09-15', 'dimension': 'org_unit'})
    assert resp.status_code == 200, resp.content
    labels = {row['label'] for row in resp.json()['breakdown']}
    assert labels == {'Org A'}


@pytest.mark.django_db
def test_book_empty(auth, create_user, db):
    resp = auth(create_user('lb_empty', is_superuser=True)).get(
        SUMMARY, {'as_of': '2026-09-15', 'dimension': 'org_unit'},
    )
    assert resp.status_code == 200
    assert resp.json()['breakdown'] == []


@pytest.mark.django_db
def test_http_matches_summarize(scene, auth, create_user):
    user = create_user('lb_match', is_superuser=True)
    code, payload = summarize_loan_book(user, as_of='2026-09-15', dimension='org_unit')
    resp = auth(user).get(SUMMARY, {'as_of': '2026-09-15', 'dimension': 'org_unit'})
    assert resp.status_code == code
    assert resp.json()['breakdown'] == payload['breakdown']


@pytest.mark.django_db
def test_in_process_uses_same_view(scene, create_user):
    from asgiref.sync import async_to_sync
    from ai.host_executor import CarbonHostExecutor

    user = create_user('lb_inproc', is_superuser=True)
    exe = CarbonHostExecutor(
        db=None, instance_config={},
        user_token=f"inproc:nibras:{user.pk}", host_user_id=str(user.pk),
    )
    out = async_to_sync(exe._people_in_process)(
        method="GET", params={"as_of": "2026-09-15", "dimension": "org_unit"}, body={},
        endpoint="carbon-api/people/loans/summary",
    )
    assert out["status_code"] == 200, out
    assert out["data"]["as_of"] == "2026-09-15"
