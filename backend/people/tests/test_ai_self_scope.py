# people/tests/test_ai_self_scope.py
# Self-scoped People reads exposed to the AI (ai.host_executor._people_me).
#
# These verify the permanent "my X" fix: the assistant's self-service reads are
# scoped to the CALLER's own employee record — never the org-wide population —
# and fail closed when no active employee is linked.

from datetime import date

import pytest

from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveRecord

from ai.host_executor import _people_me


@pytest.fixture
def people_world(db, create_user):
    """Org + leave_type + two linked employees, each with one leave record."""
    leave_set = ReferenceSet.objects.create(name='leave_type', slug='leave-type')
    annual = ReferenceValue.objects.create(
        reference_set=leave_set, code='annual', label='Annual Leave', sort_order=1,
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    user_a = create_user('self_a')
    user_b = create_user('self_b')
    emp_a = Employee.objects.create(
        org_unit=org, employee_no='E-A', full_name='Alice',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=user_a, is_active=True,
    )
    emp_b = Employee.objects.create(
        org_unit=org, employee_no='E-B', full_name='Bob',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=user_b, is_active=True,
    )
    LeaveRecord.objects.create(
        employee=emp_a, leave_type=annual, start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 5), days='5', status='approved',
    )
    LeaveRecord.objects.create(
        employee=emp_b, leave_type=annual, start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 3), days='3', status='approved',
    )
    from types import SimpleNamespace
    return SimpleNamespace(
        org=org, user_a=user_a, user_b=user_b, emp_a=emp_a, emp_b=emp_b,
    )


@pytest.mark.django_db
def test_me_profile_returns_own_record(people_world):
    out = _people_me(people_world.user_a, None, 'GET')
    assert out['status_code'] == 200
    assert out['data']['employee_no'] == 'E-A'
    assert out['data']['full_name'] == 'Alice'


@pytest.mark.django_db
def test_me_leave_is_scoped_to_caller(people_world):
    # Alice sees only her own leave record — never Bob's.
    out = _people_me(people_world.user_a, 'leave', 'GET')
    assert out['status_code'] == 200
    assert out['data']['count'] == 1
    days = {str(r['days']) for r in out['data']['results']}
    assert days == {'5.00'} or days == {'5.0'} or days == {'5'}

    out_b = _people_me(people_world.user_b, 'leave', 'GET')
    assert out_b['data']['count'] == 1
    days_b = {str(r['days']) for r in out_b['data']['results']}
    assert days_b == {'3.00'} or days_b == {'3.0'} or days_b == {'3'}


@pytest.mark.django_db
def test_me_fails_closed_without_profile(create_user, db):
    # A user with no linked employee gets a 403 — never another person's data.
    user = create_user('no_profile')
    out = _people_me(user, None, 'GET')
    assert out['status_code'] == 403
    assert 'employee profile' in out['data']['detail'].lower()


@pytest.mark.django_db
def test_me_fails_closed_for_inactive_profile(people_world):
    people_world.emp_a.is_active = False
    people_world.emp_a.save(update_fields=['is_active'])
    out = _people_me(people_world.user_a, None, 'GET')
    assert out['status_code'] == 403


@pytest.mark.django_db
def test_me_is_read_only(people_world):
    out = _people_me(people_world.user_a, 'leave', 'POST')
    assert out['status_code'] == 405


@pytest.mark.django_db
def test_me_unknown_subresource_404(people_world):
    out = _people_me(people_world.user_a, 'nonsense', 'GET')
    assert out['status_code'] == 404
