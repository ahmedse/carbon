from people.tests.ref_helpers import ensure_ref
# File: people/tests/test_employee_onboard.py
# NSR-4A — hire/onboarding hooks: leave entitlement propagation + optional
# opening basic compensation ledger line (never fabricated).

from datetime import date, timedelta
from decimal import Decimal

import pytest

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue

from people.employee_onboard_service import onboard_employee
from people.models import (
    CompensationComponent,
    Employee,
    EmployeeCompensation,
    LeaveEntitlement,
    LeavePolicy,
)

EMPLOYEES_URL = '/carbon-api/people/employees/'


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(
        name='Ops', slug='ops', code='OPS', org_type='department',
    )


@pytest.fixture
def leave_type(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type')
    return ReferenceValue.objects.create(
        reference_set=rs, code='annual', label='Annual Leave', sort_order=1,
    )


@pytest.fixture
def basic_component(db):
    """Production assumes seed; tests create code='basic' explicitly."""
    return CompensationComponent.objects.create(
        code='basic', name='Basic Salary', direction='earning',
    )


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
        )
        return api_client
    return _factory


def _make_policy(leave_type, **overrides):
    fields = {
        'leave_type': leave_type,
        'name': 'Annual Standard',
        'description': 'Standard annual leave',
        'status': 'active',
        'default_entitled_days': Decimal('30.00'),
        'gender_restriction': 'any',
        'min_service_days': 0,
        'is_active': True,
    }
    fields.update(overrides)
    return LeavePolicy.objects.create(**fields)


# ── Service: policies → entitlements ──────────────────────────────────────

@pytest.mark.django_db
def test_onboard_creates_entitlements_when_policies_apply(org, leave_type):
    policy = _make_policy(leave_type, gender_restriction='female')
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-ONB-1', full_name='Onboard Alice',
        basic_salary='1000.000', join_date=date.today() - timedelta(days=10),
        gender=ensure_ref('gender', 'female'), is_active=True,
    )

    result = onboard_employee(employee)

    assert result['leave']['created'] == 1
    assert result['opening_line'] is None
    ent = LeaveEntitlement.objects.get(
        employee=employee, year=date.today().year, leave_type=leave_type,
    )
    assert ent.entitled_days == Decimal('30.00')
    assert ent.policy_id == policy.id


@pytest.mark.django_db
def test_onboard_skips_ineligible_policies(org, leave_type):
    _make_policy(leave_type, gender_restriction='male')
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-ONB-2', full_name='Onboard Bob',
        basic_salary='1000.000', join_date=date.today(),
        gender=ensure_ref('gender', 'female'), is_active=True,
    )

    result = onboard_employee(employee)

    assert result['leave']['created'] == 0
    assert result['leave']['ineligible'] == 1
    assert LeaveEntitlement.objects.filter(employee=employee).count() == 0


@pytest.mark.django_db
def test_onboard_without_join_date_creates_no_entitlements(org, leave_type):
    """J-EMP-06: null join_date = unknown service start → zero entitlements."""
    _make_policy(leave_type)
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-ONB-NULL-JOIN', full_name='No Join Date',
        basic_salary='1000.000', join_date=None,
        gender=ensure_ref('gender', 'female'), is_active=True,
    )

    result = onboard_employee(employee)

    assert result['leave']['created'] == 0
    assert LeaveEntitlement.objects.filter(employee=employee).count() == 0


# ── Service: opening_basic → unverified ledger line ───────────────────────

@pytest.mark.django_db
def test_onboard_opening_basic_appends_unverified_ledger(
    org, basic_component, create_user,
):
    user = create_user('onboard_hr')
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-ONB-3', full_name='Onboard Carol',
        basic_salary='0.000', join_date=date(2026, 3, 1),
        is_active=True,
    )

    result = onboard_employee(
        employee, opening_basic=Decimal('850.500'), currency='KWD', user=user,
    )

    line = result['opening_line']
    assert line is not None
    assert line.component_id == basic_component.id
    assert line.amount == Decimal('850.500')
    assert line.currency == 'KWD'
    assert line.frequency == 'monthly'
    assert line.effective_start == date(2026, 3, 1)
    assert line.is_verified is False
    assert EmployeeCompensation.objects.filter(employee=employee).count() == 1


@pytest.mark.django_db
def test_onboard_without_opening_basic_fabricates_no_salary(org, basic_component):
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-ONB-4', full_name='Onboard Dan',
        basic_salary='2000.000', join_date=date(2026, 1, 1),
        is_active=True,
    )

    result = onboard_employee(employee)

    assert result['opening_line'] is None
    assert EmployeeCompensation.objects.filter(employee=employee).count() == 0


# ── API: create wires onboard hooks ───────────────────────────────────────

@pytest.mark.django_db
def test_api_create_with_policies_creates_entitlements(
    auth, create_user, org, leave_type,
):
    from people.tests.ref_helpers import ensure_ref
    ensure_ref('gender', 'female')
    _make_policy(leave_type)
    client = auth(create_user('onboard_api', is_superuser=True))

    resp = client.post(EMPLOYEES_URL, {
        'org_unit': org.id,
        'employee_no': 'E-ONB-API-1',
        'full_name': 'API Hire',
        'basic_salary': '1200.000',
        'join_date': '2026-02-01',
        'gender': 'female',
    }, format='json')

    assert resp.status_code == 201
    emp = Employee.objects.get(employee_no='E-ONB-API-1')
    assert LeaveEntitlement.objects.filter(
        employee=emp, year=date.today().year, leave_type=leave_type,
    ).exists()


@pytest.mark.django_db
def test_api_create_with_opening_basic_creates_ledger(
    auth, create_user, org, basic_component,
):
    client = auth(create_user('onboard_api2', is_superuser=True))

    resp = client.post(EMPLOYEES_URL, {
        'org_unit': org.id,
        'employee_no': 'E-ONB-API-2',
        'full_name': 'API Hire Pay',
        'basic_salary': '0.000',
        'join_date': '2026-04-15',
        'opening_basic': '975.000',
    }, format='json')

    assert resp.status_code == 201
    body = resp.json()
    assert 'opening_basic' not in body  # write-only
    emp = Employee.objects.get(employee_no='E-ONB-API-2')
    line = EmployeeCompensation.objects.get(employee=emp, component=basic_component)
    assert line.amount == Decimal('975.000')
    assert line.is_verified is False
    assert line.effective_start == date(2026, 4, 15)


@pytest.mark.django_db
def test_api_create_without_opening_basic_no_ledger(
    auth, create_user, org, basic_component,
):
    client = auth(create_user('onboard_api3', is_superuser=True))

    resp = client.post(EMPLOYEES_URL, {
        'org_unit': org.id,
        'employee_no': 'E-ONB-API-3',
        'full_name': 'API Hire No Pay',
        'basic_salary': '1500.000',
        'join_date': '2026-05-01',
    }, format='json')

    assert resp.status_code == 201
    emp = Employee.objects.get(employee_no='E-ONB-API-3')
    assert EmployeeCompensation.objects.filter(employee=emp).count() == 0
