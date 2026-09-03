# File: people/tests/test_compensation.py
# Compensation ledger regression tests (ADR-0029 / NIR-7A).
#
# Covers: model ordering/str/effective-dated resolution, CompensationService
# (append closes prior open row; Decimal-exact totals), and the API surface
# (GET/POST/verify authorization + RULE_12 org scoping).

from datetime import date
from decimal import Decimal

import pytest

from mdm.models import OrgUnit

from catalog.models import GovernanceEvent

from people.compensation_service import CompensationService
from people.models import (
    CompensationComponent,
    Employee,
    EmployeeCompensation,
    PersonnelEvent,
)

EMPLOYEES_URL = '/carbon-api/people/employees/'


def comp_url(employee):
    return EMPLOYEES_URL + f'{employee.pk}/compensation/'


def verify_url(employee, line):
    return EMPLOYEES_URL + f'{employee.pk}/compensation/{line.pk}/verify/'


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def org_a(db):
    return OrgUnit.objects.create(name='Org A', slug='org-a')


@pytest.fixture
def org_b(db):
    return OrgUnit.objects.create(name='Org B', slug='org-b')


@pytest.fixture
def employee_a(org_a):
    return Employee.objects.create(
        org_unit=org_a, employee_no='E-A', full_name='Alice',
        basic_salary='1000.000', join_date=date(2026, 1, 1),
    )


@pytest.fixture
def employee_b(org_b):
    return Employee.objects.create(
        org_unit=org_b, employee_no='E-B', full_name='Bob',
        basic_salary='2000.000', join_date=date(2026, 1, 1),
    )


@pytest.fixture
def earning_component(db):
    return CompensationComponent.objects.create(
        code='basic', name='Basic Salary', direction='earning',
    )


@pytest.fixture
def deduction_component(db):
    return CompensationComponent.objects.create(
        code='gosi', name='GOSI', direction='deduction',
    )


@pytest.fixture
def auth(api_client, get_token_for_user):
    def _factory(user):
        api_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}',
        )
        return api_client
    return _factory


# ── Model: __str__, ordering, effective-dated resolution ────────────────────

@pytest.mark.django_db
def test_compensation_line_str(employee_a, earning_component):
    line = EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1000.000',
        effective_start=date(2026, 1, 1),
    )
    assert str(line) == 'E-A — Alice | basic | 1000.000 KWD | 2026-01-01→∞'


@pytest.mark.django_db
def test_compensation_ordering(employee_a, earning_component):
    older = EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1000.000',
        effective_start=date(2026, 1, 1),
    )
    newer = EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1200.000',
        effective_start=date(2026, 7, 1),
    )
    lines = list(EmployeeCompensation.objects.all())
    assert [line.pk for line in lines] == [newer.pk, older.pk]


@pytest.mark.django_db
def test_current_lines_effective_dated(employee_a, earning_component):
    EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1000.000',
        effective_start=date(2026, 1, 1), effective_end=date(2026, 6, 30),
    )
    EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1200.000',
        effective_start=date(2026, 7, 1), effective_end=None,
    )

    march = list(CompensationService.current_lines(employee_a, as_of=date(2026, 3, 1)))
    assert [c.amount for c in march] == [Decimal('1000.000')]

    september = list(CompensationService.current_lines(employee_a, as_of=date(2026, 9, 1)))
    assert [c.amount for c in september] == [Decimal('1200.000')]


# ── Service: append closes prior line; Decimal-exact totals ─────────────────

@pytest.mark.django_db
def test_append_line_closes_previous(employee_a, earning_component, create_user):
    user = create_user('comp_writer')
    first = CompensationService.append_line(
        employee_a,
        component=earning_component,
        amount=Decimal('1000.000'),
        currency='KWD',
        frequency='monthly',
        effective_start=date(2026, 1, 1),
        user=user,
    )
    second = CompensationService.append_line(
        employee_a,
        component=earning_component,
        amount=Decimal('1200.000'),
        currency='KWD',
        frequency='monthly',
        effective_start=date(2026, 7, 1),
        user=user,
    )

    first.refresh_from_db()
    assert first.effective_end == date(2026, 7, 1)
    assert second.effective_end is None
    assert EmployeeCompensation.objects.count() == 2
    assert PersonnelEvent.objects.filter(
        entity_type='Employee', entity_id=employee_a.pk, event_kind='salary_change',
    ).count() == 2
    # The audit trail now persists (not just "no error"): one governance event
    # per appended line, with the open per-domain action verb.
    assert GovernanceEvent.objects.filter(
        entity_type='Employee', entity_id=employee_a.pk,
        action='compensation_change',
    ).count() == 2


@pytest.mark.django_db
def test_ledger_totals_decimal(employee_a, earning_component, deduction_component):
    EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='2000.000',
        effective_start=date(2026, 1, 1), frequency='monthly',
    )
    EmployeeCompensation.objects.create(
        employee=employee_a, component=deduction_component, amount='300.000',
        effective_start=date(2026, 1, 1), frequency='monthly',
    )
    # Annual line is excluded from monthly totals.
    EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='5000.000',
        effective_start=date(2026, 1, 1), frequency='annual',
    )

    totals = CompensationService.ledger_totals(employee_a)
    assert totals['monthly_earnings'] == Decimal('2000.000')
    assert totals['monthly_deductions'] == Decimal('300.000')
    assert totals['net_monthly'] == Decimal('1700.000')


# ── API: authorization + org scoping ────────────────────────────────────────

@pytest.mark.django_db
def test_get_compensation_403_without_view_cap(
    auth, create_user, create_scoped_role, employee_a,
):
    user = create_user('people_viewer')
    create_scoped_role(user, 'viewers_group')
    client = auth(user)
    resp = client.get(comp_url(employee_a))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_post_compensation_403_without_manage(
    auth, create_user, create_scoped_role, employee_a, earning_component,
):
    user = create_user('people_viewer')
    create_scoped_role(user, 'viewers_group')
    client = auth(user)
    resp = client.post(
        comp_url(employee_a),
        {
            'component': earning_component.pk,
            'amount': '1500.000',
            'effective_start': '2026-07-01',
        },
        format='json',
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_post_appends_and_closes_previous(auth, create_user, employee_a, earning_component):
    client = auth(create_user('comp_admin', is_superuser=True))
    payload = {
        'component': earning_component.pk,
        'amount': '1500.000',
        'currency': 'KWD',
        'frequency': 'monthly',
        'effective_start': '2026-01-01',
    }
    first = client.post(comp_url(employee_a), payload, format='json')
    assert first.status_code == 201

    second = client.post(
        comp_url(employee_a),
        {**payload, 'amount': '1800.000', 'effective_start': '2026-07-01'},
        format='json',
    )
    assert second.status_code == 201

    lines = list(EmployeeCompensation.objects.filter(employee=employee_a).order_by('effective_start'))
    assert len(lines) == 2
    assert lines[0].effective_end == date(2026, 7, 1)
    assert lines[1].effective_end is None
    assert lines[1].amount == Decimal('1800.000')


@pytest.mark.django_db
def test_verify_requires_manage(
    auth, create_user, create_scoped_role, employee_a, earning_component,
):
    line = EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1000.000',
        effective_start=date(2026, 1, 1),
    )
    user = create_user('people_viewer')
    create_scoped_role(user, 'viewers_group')
    client = auth(user)

    resp = client.post(verify_url(employee_a, line))
    assert resp.status_code == 403

    line.refresh_from_db()
    assert line.is_verified is False


@pytest.mark.django_db
def test_verify_succeeds_with_manage(auth, create_user, employee_a, earning_component):
    line = EmployeeCompensation.objects.create(
        employee=employee_a, component=earning_component, amount='1000.000',
        effective_start=date(2026, 1, 1),
    )
    client = auth(create_user('comp_admin', is_superuser=True))

    resp = client.post(verify_url(employee_a, line))
    assert resp.status_code == 200

    line.refresh_from_db()
    assert line.is_verified is True
    assert line.verified_at is not None
    # Verification also persists a governance event (action = compensation_verified).
    assert GovernanceEvent.objects.filter(
        entity_type='Employee', entity_id=employee_a.pk,
        action='compensation_verified',
    ).exists()


@pytest.mark.django_db
def test_cannot_reveal_other_org_employee(
    auth, create_user, create_scoped_role, org_a, employee_a, employee_b,
):
    # A scoped admins_group role carries view (incl. view_compensation) but not
    # write, and is org-scoped to org_a — so only org_a employees are visible.
    user = create_user('people_hr')
    create_scoped_role(user, 'admins_group', org_unit=org_a)
    client = auth(user)

    own = client.get(comp_url(employee_a))
    assert own.status_code == 200

    other = client.get(comp_url(employee_b))
    assert other.status_code == 404
