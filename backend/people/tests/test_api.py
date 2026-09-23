# File: people/tests/test_api.py
# NIR-3E API surface regression tests (RULE_11).
#
# Covers:
#   1. unauthenticated → 401 on a people route.
#   2. user without ``people:view`` → 403.
#   3. org-scoped (RULE_12) non-admin user cannot see another org's employees.
#   4. Tier-1 write gate: a bound ``not_null`` rule blocks an Employee write
#      with HTTP 422 and does NOT persist the row.
#   5. Payroll run lifecycle happy path (compute → validate → commit).
#   6. Illegal run transition → HTTP 409.

from datetime import date

import pytest
from rest_framework.test import APIClient

from dq.models import DQRule, ModelRuleAssignment
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue

from people.models import (
    BenefitType,
    CompensationComponent,
    ComplianceRule,
    Employee,
    EmployeeBenefit,
    EmployeeCompensation,
    LeaveRecord,
    PayrollRun,
    PayrollRunValidation,
    Position,
)
from people.tests.ref_helpers import ensure_ref

PEOPLE_API = '/carbon-api/people/'
EMPLOYEES_URL = PEOPLE_API + 'employees/'
POSITIONS_URL = PEOPLE_API + 'positions/'
PAYROLL_RUNS_URL = PEOPLE_API + 'payroll-runs/'
LEAVE_RECORDS_URL = PEOPLE_API + 'leave-records/'
BENEFIT_TYPES_URL = PEOPLE_API + 'benefit-types/'


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def deployment_root(db):
    """ADR-0028: one active parent=None root; org_a/org_b are siblings under it."""
    return OrgUnit.objects.create(name='Deployment Root', slug='deploy-root', org_type='company')


@pytest.fixture
def org_a(deployment_root):
    return OrgUnit.objects.create(
        name='Org A', slug='org-a', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def org_b(deployment_root):
    return OrgUnit.objects.create(
        name='Org B', slug='org-b', parent=deployment_root, org_type='division',
    )


@pytest.fixture
def employee_a(org_a):
    emp = Employee.objects.create(
        org_unit=org_a, employee_no='E-A', full_name='Alice', basic_salary='1000.000',
        join_date=date(2026, 1, 1),
    )
    component, _ = CompensationComponent.objects.get_or_create(
        code='basic',
        defaults={
            'name': 'Basic Salary',
            'direction': 'earning',
            'is_wps_relevant': True,
            'sort_order': 10,
            'is_active': True,
        },
    )
    EmployeeCompensation.objects.create(
        employee=emp,
        component=component,
        amount='1000.000',
        frequency='monthly',
        effective_start=date(2024, 1, 1),
        is_verified=True,
    )
    return emp


@pytest.fixture
def employee_b(org_b):
    return Employee.objects.create(
        org_unit=org_b, employee_no='E-B', full_name='Bob', basic_salary='2000.000',
        join_date=date(2026, 1, 1),
    )


@pytest.fixture
def leave_type_annual(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type')
    return ReferenceValue.objects.create(
        reference_set=rs, code='annual', label='Annual Leave',
    )


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
        )
        return api_client
    return _factory


# ── 1. Authentication (401) ────────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('url', [EMPLOYEES_URL, POSITIONS_URL])
def test_unauthenticated_gets_401(api_client, url):
    assert api_client.get(url).status_code == 401


# ── 2. No-capability user → 403 ────────────────────────────────────────────

@pytest.mark.django_db
def test_no_capability_user_gets_403(auth, create_user):
    client = auth(create_user('people_nothing'))
    assert client.get(POSITIONS_URL).status_code == 403
    assert client.get(EMPLOYEES_URL).status_code == 403


# ── 3. Org scoping (RULE_12) ───────────────────────────────────────────────

@pytest.mark.django_db
def test_org_scoped_user_sees_only_own_org(
    auth, create_user, create_scoped_role, org_a, employee_a, employee_b,
):
    user = create_user('people_org_viewer')
    create_scoped_role(user, 'viewers_group', org_unit=org_a)
    client = auth(user)
    resp = client.get(EMPLOYEES_URL)
    assert resp.status_code == 200
    employee_nos = [e['employee_no'] for e in resp.json()['results']]
    assert employee_nos == ['E-A']


@pytest.mark.django_db
def test_employee_list_query_budget_is_bounded(auth, create_user, org_a):
    """List must not N+1 per employee (SIM-QA N-HR-UI-01 / nibras_dev timeout)."""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    nat = ensure_ref('nationality', 'KW')
    et = ensure_ref('employment_type', 'permanent')
    ct = ensure_ref('contract_type', 'unlimited')
    gender = ensure_ref('gender', 'male')
    for i in range(25):
        Employee.objects.create(
            org_unit=org_a,
            employee_no=f'E-Q{i:02d}',
            full_name=f'Query Budget {i}',
            basic_salary='1000.000',
            join_date=date(2026, 1, 1),
            nationality=nat,
            employment_type=et,
            contract_type=ct,
            gender=gender,
        )

    client = auth(create_user('people_list_budget', is_superuser=True))
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(EMPLOYEES_URL, {'page_size': 50})
    assert resp.status_code == 200
    assert resp.json()['count'] >= 25
    # Constant-ish: auth/scope + one SELECT + count. Must not grow with N rows.
    assert len(ctx) < 40, f'employee list issued {len(ctx)} queries (N+1 regression)'


@pytest.mark.django_db
def test_employee_detail_includes_org_unit_name(auth, create_user, org_a, employee_a):
    client = auth(create_user('people_org_label', is_superuser=True))
    resp = client.get(EMPLOYEES_URL + f'{employee_a.pk}/')
    assert resp.status_code == 200
    assert resp.json()['org_unit_label'] == 'Org A'


@pytest.mark.django_db
def test_employee_list_honors_page_size(auth, create_user, org_a):
    """page_size must cap results (NB-P0-EMP-PAGE — was ignored / unbounded)."""
    for i in range(12):
        Employee.objects.create(
            org_unit=org_a,
            employee_no=f'E-P{i:02d}',
            full_name=f'Page Cap {i}',
            basic_salary='1000.000',
            join_date=date(2026, 1, 1),
        )
    client = auth(create_user('people_list_page', is_superuser=True))
    resp = client.get(EMPLOYEES_URL, {'page_size': 5, 'page': 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body['count'] >= 12
    assert body['page_size'] == 5
    assert body['page'] == 1
    assert len(body['results']) == 5
    page2 = client.get(EMPLOYEES_URL, {'page_size': 5, 'page': 2}).json()
    assert len(page2['results']) == 5
    assert {r['id'] for r in body['results']}.isdisjoint(
        {r['id'] for r in page2['results']},
    )


# ── 4. Tier-1 write gate ───────────────────────────────────────────────────

def _nationality_not_null_rule():
    """Bind a write-time ``not_null`` rule to ``people.Employee.nationality``."""
    rule = DQRule.objects.create(
        name="nationality-required",
        rule_type="not_null",
        rule_level="field_validation",
        is_active=True,
        definition={
            "schema_version": 1,
            "name": "nationality-required",
            "level": "field",
            "dimension": "completeness",
            "type": "not_null",
            "severity": "error",
            "params": {},
            "enforcement": {"on_write": True},
            "active": True,
        },
    )
    ModelRuleAssignment.objects.create(
        rule=rule,
        model_label="people.Employee",
        field_name="nationality",
        is_active=True,
    )


@pytest.mark.django_db
def test_tier1_write_gate_blocks_and_does_not_persist(auth, create_user, org_a, employee_a):
    _nationality_not_null_rule()
    before = Employee.objects.count()

    client = auth(create_user('people_gate_writer', is_superuser=True))
    payload = {
        'org_unit': org_a.id,
        'employee_no': 'E-GATE',
        'full_name': 'Gate Test',
        'basic_salary': '1500.000',
        'join_date': '2026-01-01',
        # nationality omitted → not_null rule fires → write blocked.
    }
    resp = client.post(EMPLOYEES_URL, payload, format='json')
    assert resp.status_code == 422
    assert resp.json()['detail'] == 'DQ validation blocked this write'
    assert Employee.objects.count() == before


# ── 5 & 6. Run lifecycle ──────────────────────────────────────────────────

def _gross_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-gross-test", version="2026.1",
        name="[TEST ONLY] Gross pay", category=ensure_ref('compliance_category', 'payroll'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["basic"],
            "formula": {
                "type": "sum",
                "params": {"components": ["basic"], "base_input": "basic"},
            },
        },
        is_authoritative=True,
    )


def _gosi_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-gosi-test", version="2026.1",
        name="[TEST ONLY] GOSI", category=ensure_ref('compliance_category', 'gosi'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["gross_salary", "employee_age"],
            "formula": {
                "type": "gosi",
                "params": {
                    "employee_bands": [{"max_age": None, "rate": "0.10"}],
                    "employer_bands": [{"max_age": None, "rate": "0.10"}],
                },
            },
        },
        is_authoritative=True,
    )


def _loan_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-loan-test", version="2026.1",
        name="[TEST ONLY] Loan schedule", category=ensure_ref('compliance_category', 'other'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["principal", "interest_rate", "term_months"],
            "formula": {
                "type": "loan_schedule",
                "params": {
                    "method": "flat",
                    "rate_is_annual": True,
                    "rate_is_percent": False,
                },
            },
        },
        is_authoritative=True,
    )


def _net_rule():
    return ComplianceRule.objects.create(
        rule_id="kw-netpay-test", version="2026.1",
        name="[TEST ONLY] Net pay", category=ensure_ref('compliance_category', 'other'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["gross", "deductions"],
            "formula": {"type": "net_pay", "params": {}},
        },
        is_authoritative=True,
    )


def _wps_rule(authoritative=True):
    return ComplianceRule.objects.create(
        rule_id="kw-wps-test", version="2026.1",
        name="[TEST ONLY] WPS", category=ensure_ref('compliance_category', 'wps'), jurisdiction=ensure_ref('jurisdiction', 'KW'),
        effective_date=date(2026, 1, 1),
        inputs_schema={
            "inputs": ["net"],
            "formula": {
                "type": "wps",
                "params": {
                    "field_map": {
                        "employee_number": "employee_no",
                        "employee_name": "employee_name",
                        "salary": "basic_salary",
                    },
                    "amount_components": ["net"],
                },
            },
        },
        is_authoritative=authoritative,
    )


@pytest.mark.django_db
def test_run_lifecycle_happy_path(auth, create_user, get_token_for_user, org_a, employee_a):
    _gross_rule()
    _gosi_rule()
    _loan_rule()
    _net_rule()

    client = auth(create_user('people_run_writer', is_superuser=True))
    committer = APIClient()
    committer.credentials(HTTP_AUTHORIZATION=(
        'Bearer ' + get_token_for_user(create_user('people_run_committer', is_superuser=True))
    ))
    run = PayrollRun.objects.create(
        org_unit=org_a,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )

    resp = client.post(PAYROLL_RUNS_URL + f'{run.pk}/compute/')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'computed'
    run.refresh_from_db()
    assert run.status == 'computed'

    resp = client.post(PAYROLL_RUNS_URL + f'{run.pk}/validate/')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'validated'
    run.refresh_from_db()
    assert run.status == 'validated'
    assert PayrollRunValidation.objects.filter(payroll_run=run).exists()

    resp = committer.post(PAYROLL_RUNS_URL + f'{run.pk}/commit/')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'committed'
    run.refresh_from_db()
    assert run.status == 'committed'
    assert run.committed_at is not None


@pytest.mark.django_db
def test_illegal_transition_returns_409(auth, create_user, org_a, employee_a):
    _gross_rule()
    _gosi_rule()
    _loan_rule()
    _net_rule()

    client = auth(create_user('people_run_writer2', is_superuser=True))
    run = PayrollRun.objects.create(
        org_unit=org_a,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )

    # commit from draft is illegal → PayrollServiceError → 409.
    resp = client.post(PAYROLL_RUNS_URL + f'{run.pk}/commit/')
    assert resp.status_code == 409
    run.refresh_from_db()
    assert run.status == 'draft'


# ── NIR-5H: WPS export endpoint ────────────────────────────────────────────

def _commit_run(client, run, committer=None):
    client.post(PAYROLL_RUNS_URL + f'{run.pk}/compute/')
    client.post(PAYROLL_RUNS_URL + f'{run.pk}/validate/')
    (committer or client).post(PAYROLL_RUNS_URL + f'{run.pk}/commit/')


@pytest.mark.django_db
def test_wps_export_happy_path(auth, create_user, get_token_for_user, org_a, employee_a):
    _gross_rule()
    _gosi_rule()
    _net_rule()
    _wps_rule(authoritative=True)

    client = auth(create_user('people_wps_writer', is_superuser=True))
    committer = APIClient()
    committer.credentials(HTTP_AUTHORIZATION=(
        'Bearer ' + get_token_for_user(create_user('people_wps_committer', is_superuser=True))
    ))
    run = PayrollRun.objects.create(
        org_unit=org_a,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    _commit_run(client, run, committer)
    run.refresh_from_db()
    assert run.status == 'committed'

    resp = client.get(PAYROLL_RUNS_URL + f'{run.pk}/wps/')
    assert resp.status_code == 200
    assert resp['Content-Type'].startswith('text/csv')
    assert 'attachment' in resp['Content-Disposition']

    body = resp.content.decode('utf-8')
    assert 'employee_number' in body
    assert 'E-A' in body
    assert 'amount' in body


@pytest.mark.django_db
def test_wps_export_refuses_non_committed(auth, create_user, org_a):
    _wps_rule(authoritative=True)

    client = auth(create_user('people_wps_draft', is_superuser=True))
    run = PayrollRun.objects.create(
        org_unit=org_a,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )

    resp = client.get(PAYROLL_RUNS_URL + f'{run.pk}/wps/')
    assert resp.status_code == 409


@pytest.mark.django_db
def test_wps_export_refuses_non_authoritative_rule(auth, create_user, org_a, employee_a):
    _gross_rule()
    _gosi_rule()
    _net_rule()
    _wps_rule(authoritative=False)

    client = auth(create_user('people_wps_nonauth', is_superuser=True))
    run = PayrollRun.objects.create(
        org_unit=org_a,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    _commit_run(client, run)

    resp = client.get(PAYROLL_RUNS_URL + f'{run.pk}/wps/')
    assert resp.status_code == 409


# ── NIR-5A: DELETE endpoints (full CRUD) ───────────────────────────────────

@pytest.mark.django_db
class TestDeleteEndpoints:
    """DELETE semantics for every people detail endpoint."""

    def test_employee_soft_delete(self, auth, create_user, employee_a):
        client = auth(create_user('people_del_emp', is_superuser=True))
        resp = client.delete(EMPLOYEES_URL + f'{employee_a.pk}/')
        assert resp.status_code == 204
        employee_a.refresh_from_db()
        assert employee_a.is_active is False
        assert Employee.objects.filter(pk=employee_a.pk).exists()

    def test_payroll_run_delete_guard(self, auth, create_user, org_a):
        client = auth(create_user('people_del_run', is_superuser=True))
        committed = PayrollRun.objects.create(
            org_unit=org_a,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            status='committed',
        )
        draft = PayrollRun.objects.create(
            org_unit=org_a,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            status='draft',
        )

        resp = client.delete(PAYROLL_RUNS_URL + f'{committed.pk}/')
        assert resp.status_code == 400
        assert PayrollRun.objects.filter(pk=committed.pk).exists()

        resp = client.delete(PAYROLL_RUNS_URL + f'{draft.pk}/')
        assert resp.status_code == 204
        assert not PayrollRun.objects.filter(pk=draft.pk).exists()

    def test_position_delete_guard(self, auth, create_user, org_a):
        client = auth(create_user('people_del_pos', is_superuser=True))
        parent = Position.objects.create(org_unit=org_a, code='P1', title='Manager')
        Position.objects.create(org_unit=org_a, code='P2', title='Report', reports_to=parent)

        resp = client.delete(POSITIONS_URL + f'{parent.pk}/')
        assert resp.status_code == 400
        assert Position.objects.filter(pk=parent.pk).exists()

    def test_benefit_type_delete_guard(self, auth, create_user, org_a, employee_a):
        client = auth(create_user('people_del_bt', is_superuser=True))
        benefit_type = BenefitType.objects.create(
            code='VEH', name='Vehicle', category=ensure_ref('benefit_category', 'vehicle'),
        )
        EmployeeBenefit.objects.create(
            employee=employee_a,
            benefit_type=benefit_type,
            monthly_amount='100.000',
            effective_start=date(2026, 1, 1),
        )

        resp = client.delete(BENEFIT_TYPES_URL + f'{benefit_type.pk}/')
        assert resp.status_code == 400
        assert BenefitType.objects.filter(pk=benefit_type.pk).exists()

    def test_leave_record_hard_delete(self, auth, create_user, employee_a, leave_type_annual):
        client = auth(create_user('people_del_lr', is_superuser=True))
        record = LeaveRecord.objects.create(
            employee=employee_a,
            leave_type=leave_type_annual,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 5),
            days='5.00',
            status='draft',
        )

        resp = client.delete(LEAVE_RECORDS_URL + f'{record.pk}/')
        assert resp.status_code == 204
        assert not LeaveRecord.objects.filter(pk=record.pk).exists()

    def test_delete_unauthenticated_401(self, api_client, employee_a):
        resp = api_client.delete(EMPLOYEES_URL + f'{employee_a.pk}/')
        assert resp.status_code == 401

    def test_delete_no_capability_403(self, auth, create_user, employee_a):
        client = auth(create_user('people_del_nothing'))
        resp = client.delete(EMPLOYEES_URL + f'{employee_a.pk}/')
        assert resp.status_code == 403

    def test_org_scoped_manager_cannot_delete_other_org(
        self, monkeypatch, auth, create_user, create_scoped_role,
        org_a, employee_a, employee_b,
    ):
        from accounts.capabilities import GROUP_CAPABILITIES, PEOPLE_MANAGE

        monkeypatch.setitem(
            GROUP_CAPABILITIES,
            'viewers_group',
            GROUP_CAPABILITIES['viewers_group'] | {PEOPLE_MANAGE.key},
        )

        user = create_user('people_org_manager')
        create_scoped_role(user, 'viewers_group', org_unit=org_a)
        client = auth(user)

        # Own org → soft delete succeeds.
        resp = client.delete(EMPLOYEES_URL + f'{employee_a.pk}/')
        assert resp.status_code == 204

        # Another org → 404 (RULE_12 scoping), not 403/204.
        resp = client.delete(EMPLOYEES_URL + f'{employee_b.pk}/')
        assert resp.status_code == 404
