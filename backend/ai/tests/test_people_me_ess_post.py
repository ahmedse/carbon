"""In-process /me POST for leave/loan/attendance ESS (host_executor)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ai.host_executor import _people_me
from correspondence.models import WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveEntitlement, LeaveRecord, Loan


@pytest.fixture
def ess_users(db, create_user):
    corr_set, _ = ReferenceSet.objects.get_or_create(
        name='correspondence_type',
        defaults={'slug': 'correspondence-type-he', 'is_active': True},
    )
    for code, label in (
        ('leave_request', 'Leave'),
        ('loan_request', 'Loan'),
        ('attendance_permission', 'Attendance'),
    ):
        ReferenceValue.objects.get_or_create(
            reference_set=corr_set, code=code, defaults={'label': label},
        )
    leave_set, _ = ReferenceSet.objects.get_or_create(
        name='leave_type', defaults={'slug': 'leave-type-he', 'is_active': True},
    )
    annual, _ = ReferenceValue.objects.get_or_create(
        reference_set=leave_set, code='annual', defaults={'label': 'Annual'},
    )
    loan_set, _ = ReferenceSet.objects.get_or_create(
        name='loan_type', defaults={'slug': 'loan-type-he', 'is_active': True},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=loan_set, code='emergency', defaults={'label': 'Emergency'},
    )
    perm_set, _ = ReferenceSet.objects.get_or_create(
        name='permission_type', defaults={'slug': 'perm-type-he', 'is_active': True},
    )
    ReferenceValue.objects.get_or_create(
        reference_set=perm_set, code='personal', defaults={'label': 'Personal'},
    )
    org = OrgUnit.objects.create(
        name='HE Org', slug='he-org', code='HE', org_type='department',
    )
    mgr_u = create_user('he_mgr')
    req_u = create_user('he_req')
    mgr = Employee.objects.create(
        org_unit=org, employee_no='HE-MGR', full_name='Mgr',
        basic_salary='1000', join_date=date(2026, 1, 1), user=mgr_u, is_active=True,
    )
    emp = Employee.objects.create(
        org_unit=org, employee_no='HE-REQ', full_name='Req',
        basic_salary='1000', join_date=date(2026, 1, 1), user=req_u,
        manager=mgr, is_active=True,
    )
    LeaveEntitlement.objects.create(
        employee=emp, year=date.today().year, leave_type=annual, entitled_days=Decimal('20'),
    )
    for code in ('leave_request', 'loan_request', 'attendance_permission'):
        ct = ReferenceValue.objects.get(reference_set=corr_set, code=code)
        policy, _ = WorkflowPolicy.objects.update_or_create(
            corr_type=ct, org_unit=None, version='1.0.0',
            defaults={'name': f'{code} HE', 'is_active': True,
                      'numbering_format': '{PREFIX}-{YEAR}-{SEQ:04d}'},
        )
        WorkflowPolicyStep.objects.update_or_create(
            policy=policy, order=1,
            defaults={'role': 'manager', 'intent': 'approve',
                      'skip_if_self': True, 'is_active': True},
        )
    return req_u, emp


@pytest.mark.django_db
def test_people_me_payslips_empty_is_200_not_fake_403(ess_users):
    """F-LIVE-9: ESS me/payslips matches HTTP self view — empty is 200."""
    user, _ = ess_users
    out = _people_me(user, "payslips", "GET")
    assert out["status_code"] == 200, out
    assert out["data"]["count"] == 0
    assert out["data"]["results"] == []
    assert out.get("unauthorized") is not True


@pytest.mark.django_db
def test_people_me_post_leave(ess_users):
    user, _ = ess_users
    start = date.today() + timedelta(days=10)
    out = _people_me(
        user, 'leave', 'POST',
        body={
            'leave_type': 'annual',
            'start_date': start.isoformat(),
            'end_date': start.isoformat(),
            'days': 1,
            'note': 'he-test',
        },
    )
    assert out['status_code'] == 201, out
    assert out['data']['subject_type'] == 'people.LeaveRecord'
    assert LeaveRecord.objects.filter(employee__user=user).exists()


@pytest.mark.django_db
def test_people_me_post_loan(ess_users):
    user, _ = ess_users
    start = (date.today().replace(day=1) + timedelta(days=32)).replace(day=1)
    out = _people_me(
        user, 'loan', 'POST',
        body={
            'loan_type': 'emergency',
            'principal': '50.000',
            'interest_rate': '0',
            'term_months': 3,
            'start_date': start.isoformat(),
        },
    )
    assert out['status_code'] == 201, out
    assert out['data']['subject_type'] == 'people.Loan'
    assert Loan.objects.filter(employee__user=user).exists()


@pytest.mark.django_db
def test_people_me_post_attendance(ess_users):
    user, _ = ess_users
    day = date.today() + timedelta(days=5)
    out = _people_me(
        user, 'attendance-permissions', 'POST',
        body={
            'date': day.isoformat(),
            'permission_type': 'personal',
            'hours': '2.00',
            'notes': 'he-att',
        },
    )
    assert out['status_code'] == 201, out
    assert out['data']['subject_type'] == 'people.AttendancePermission'
