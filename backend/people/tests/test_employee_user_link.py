# File: people/tests/test_employee_user_link.py
# OF-1 — Employee <-> accounts.User OneToOne link + IsActiveEmployee permission.

from datetime import date
from io import StringIO
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command

from accounts.models import ScopedRole
from mdm.models import OrgUnit

from people.models import Employee
from people.permissions import IsActiveEmployee

User = get_user_model()


@pytest.fixture
def org(db):
    return OrgUnit.objects.create(name='Test Org', slug='test-org')


def _make_employee(org_unit, user=None, **overrides):
    kwargs = dict(
        org_unit=org_unit,
        employee_no='E-OF1',
        full_name='OF-1 Employee',
        basic_salary='1000.000',
        join_date=date(2026, 1, 1),
        user=user,
    )
    kwargs.update(overrides)
    return Employee.objects.create(**kwargs)


@pytest.mark.django_db
def test_employee_user_one_to_one_roundtrip(create_user, org):
    user = create_user('of1_user')
    employee = _make_employee(org, user=user)

    assert employee.user == user
    assert user.employee_profile == employee


@pytest.mark.django_db
def test_is_active_employee_true_for_active_profile(create_user, org):
    user = create_user('of1_active')
    _make_employee(org, user=user, is_active=True)

    request = SimpleNamespace(user=user)
    assert IsActiveEmployee().has_permission(request, None) is True


@pytest.mark.django_db
def test_is_active_employee_false_without_profile(create_user):
    user = create_user('of1_noprofile')

    request = SimpleNamespace(user=user)
    assert IsActiveEmployee().has_permission(request, None) is False


@pytest.mark.django_db
def test_is_active_employee_false_for_inactive_profile(create_user, org):
    user = create_user('of1_inactive')
    _make_employee(org, user=user, is_active=False)

    request = SimpleNamespace(user=user)
    assert IsActiveEmployee().has_permission(request, None) is False


def test_is_active_employee_false_for_unauthenticated():
    request = SimpleNamespace(user=AnonymousUser())
    assert IsActiveEmployee().has_permission(request, None) is False


@pytest.mark.django_db
def test_unlink_employee_raises_does_not_exist(create_user, org):
    user = create_user('of1_unlink')
    employee = _make_employee(org, user=user)

    employee.user = None
    employee.save()

    with pytest.raises(Employee.DoesNotExist):
        _ = user.employee_profile


# ── link_employee_users command ───────────────────────────────────────────────

@pytest.mark.django_db
def test_link_employee_users_links_and_assigns_groups(org):
    emp = _make_employee(org, employee_no='GF-101')

    call_command(
        'link_employee_users', password='TestPa_132', stdout=StringIO(),
    )

    emp.refresh_from_db()
    assert emp.user is not None
    assert emp.user.username == 'emp_gf_101'
    assert emp.user.check_password('TestPa_132') is True
    assert emp.user.is_active is True

    # Global employee_group (my app) + org-unit employee_group (emp → orgunit).
    assert ScopedRole.objects.filter(
        user=emp.user, group__name='employee_group', org_unit=None
    ).exists()
    assert ScopedRole.objects.filter(
        user=emp.user, group__name='employee_group', org_unit=org
    ).exists()


@pytest.mark.django_db
def test_link_employee_users_assigns_manager_group(org):
    mgr = _make_employee(org, employee_no='GF-MGR')
    _make_employee(org, employee_no='GF-DIR', manager=mgr, user=None)

    call_command('link_employee_users', password='TestPa_132', stdout=StringIO())

    mgr.refresh_from_db()
    assert mgr.user is not None
    assert ScopedRole.objects.filter(
        user=mgr.user, group__name='manager_group', org_unit=org
    ).exists()


@pytest.mark.django_db
def test_link_employee_users_idempotent(org):
    emp = _make_employee(org, employee_no='GF-201')
    call_command('link_employee_users', password='TestPa_132', stdout=StringIO())
    emp.refresh_from_db()
    first_user = emp.user_id

    # Second run reuses the existing user and does not duplicate ScopedRoles.
    call_command('link_employee_users', password='TestPa_132', stdout=StringIO())
    emp.refresh_from_db()
    assert emp.user_id == first_user
    assert ScopedRole.objects.filter(
        user=emp.user, group__name='employee_group', org_unit=None
    ).count() == 1


@pytest.mark.django_db
def test_link_employee_users_dry_run_makes_no_changes(org):
    _make_employee(org, employee_no='GF-301')

    call_command(
        'link_employee_users',
        dry_run=True,
        password='TestPa_132',
        stdout=StringIO(),
    )

    assert Employee.objects.filter(user__isnull=False).count() == 0
