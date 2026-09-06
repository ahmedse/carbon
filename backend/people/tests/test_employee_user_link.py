# File: people/tests/test_employee_user_link.py
# OF-1 — Employee <-> accounts.User OneToOne link + IsActiveEmployee permission.

from datetime import date
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

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
