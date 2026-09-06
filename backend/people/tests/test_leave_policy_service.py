# File: people/tests/test_leave_policy_service.py
# LPR-2A — leave-policy propagation service + management command tests.
#
# Covers:
#   (a) propagate_policy dry_run returns counts and creates nothing;
#   (b) propagate_policy non-dry creates entitlements and sets the policy FK;
#   (c) an existing entitlement is never overwritten (days + policy preserved);
#   (d) propagate_all_active aggregates across policies and reports per_policy;
#   (e) the management command --dry-run runs without error.

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.leave_policy_service import propagate_all_active, propagate_policy
from people.models import Employee, LeaveEntitlement, LeavePolicy


@pytest.fixture
def leave_type(db):
    rs = ReferenceSet.objects.create(name='leave_type', slug='leave-type')
    return ReferenceValue.objects.create(
        reference_set=rs, code='annual', label='Annual Leave', sort_order=1,
    )


@pytest.fixture
def leave_type2(leave_type):
    return ReferenceValue.objects.create(
        reference_set=leave_type.reference_set, code='sick',
        label='Sick Leave', sort_order=2,
    )


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )


@pytest.fixture
def female_employee(org):
    return Employee.objects.create(
        org_unit=org, employee_no='E-F', full_name='Alice Active',
        basic_salary='1000.000', join_date=date.today() - timedelta(days=400),
        gender='female', is_active=True,
    )


@pytest.fixture
def male_employee(org):
    return Employee.objects.create(
        org_unit=org, employee_no='E-M', full_name='Bob Active',
        basic_salary='2000.000', join_date=date.today() - timedelta(days=400),
        gender='male', is_active=True,
    )


@pytest.fixture
def inactive_employee(org):
    return Employee.objects.create(
        org_unit=org, employee_no='E-I', full_name='Carol Inactive',
        basic_salary='3000.000', join_date=date.today() - timedelta(days=400),
        gender='female', is_active=False,
    )


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


# ── (a) propagate_policy dry_run returns counts, no write ─────────────────

@pytest.mark.django_db
def test_propagate_policy_dry_run_no_write(
    leave_type, female_employee, male_employee, inactive_employee,
):
    policy = _make_policy(leave_type, gender_restriction='female')
    result = propagate_policy(policy, date.today().year, dry_run=True)

    assert result['eligible'] == 1
    assert result['will_create'] == 1
    assert result['will_update'] == 0
    assert result['skipped'] == 1
    assert result['year'] == date.today().year
    assert LeaveEntitlement.objects.count() == 0


# ── (b) propagate_policy non-dry creates + sets policy FK ─────────────────

@pytest.mark.django_db
def test_propagate_policy_creates_and_sets_policy_fk(
    leave_type, female_employee, male_employee, inactive_employee,
):
    policy = _make_policy(leave_type, gender_restriction='female')
    result = propagate_policy(policy, date.today().year)

    assert result['eligible'] == 1
    assert result['created'] == 1
    assert result['updated'] == 0

    ent = LeaveEntitlement.objects.get(
        year=date.today().year, leave_type=leave_type,
    )
    assert ent.employee_id == female_employee.id
    assert ent.entitled_days == Decimal('30.00')
    assert ent.policy_id == policy.id


# ── (c) existing entitlement never overwritten (days + policy) ────────────

@pytest.mark.django_db
def test_propagate_policy_does_not_overwrite_existing(leave_type, female_employee):
    policy = _make_policy(leave_type, default_entitled_days=Decimal('30.00'))
    other_policy = _make_policy(
        leave_type, name='Legacy Manual', default_entitled_days=Decimal('50.00'),
    )
    LeaveEntitlement.objects.create(
        employee=female_employee, year=date.today().year, leave_type=leave_type,
        entitled_days=Decimal('45.00'), policy=other_policy,
    )

    result = propagate_policy(policy, date.today().year)
    assert result['created'] == 0
    assert result['updated'] == 1

    ent = LeaveEntitlement.objects.get(
        employee=female_employee, year=date.today().year, leave_type=leave_type,
    )
    assert ent.entitled_days == Decimal('45.00')
    assert ent.policy_id == other_policy.id


# ── (d) propagate_all_active aggregates + per_policy ──────────────────────

@pytest.mark.django_db
def test_propagate_all_active_aggregates(
    leave_type, leave_type2, female_employee, male_employee, inactive_employee,
):
    policy_f = _make_policy(
        leave_type, name='Female Annual', gender_restriction='female',
    )
    policy_m = _make_policy(
        leave_type2, name='Male Sick', gender_restriction='male',
    )

    result = propagate_all_active(year=date.today().year)

    assert result['year'] == date.today().year
    assert result['eligible'] == 2
    assert result['will_create'] == 2
    assert result['created'] == 2

    by_id = {row['policy_id']: row for row in result['per_policy']}
    assert set(by_id) == {policy_f.id, policy_m.id}
    assert by_id[policy_f.id]['name'] == 'Female Annual'
    assert by_id[policy_f.id]['eligible'] == 1
    assert by_id[policy_f.id]['created'] == 1
    assert by_id[policy_m.id]['eligible'] == 1
    assert by_id[policy_m.id]['created'] == 1

    # One entitlement per (employee, year, leave_type) across the two policies.
    assert LeaveEntitlement.objects.filter(year=date.today().year).count() == 2


# ── (e) management command --dry-run runs without error ───────────────────

@pytest.mark.django_db
def test_management_command_dry_run(
    leave_type, leave_type2, female_employee, male_employee, inactive_employee,
):
    _make_policy(leave_type, name='Female Annual', gender_restriction='female')
    _make_policy(leave_type2, name='Male Sick', gender_restriction='male')

    call_command('propagate_leave_policies', year=date.today().year, dry_run=True)

    # Dry-run must not write anything.
    assert LeaveEntitlement.objects.count() == 0
