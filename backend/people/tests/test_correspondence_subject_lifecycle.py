# people/tests/test_correspondence_subject_lifecycle.py
# Void / reopen must keep domain subjects aligned with the workflow spine.

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from correspondence import fsm
from correspondence.models import Correspondence, WorkflowPolicy, WorkflowPolicyStep
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import AttendancePermission, Employee, LeaveRecord, Loan
from people.tests.ref_helpers import ensure_ref


@pytest.fixture
def leave_admin_wf(db, create_user):
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type-life',
    )
    leave_corr = ReferenceValue.objects.create(
        reference_set=corr_set, code='leave_request', label='Leave Request',
    )
    leave_set = ReferenceSet.objects.create(name='leave_type', slug='leave-type-life')
    annual = ReferenceValue.objects.create(
        reference_set=leave_set, code='annual', label='Annual',
    )
    org = OrgUnit.objects.create(
        name='Life', slug='life', code='LIFE', org_type='department',
    )
    requester = create_user('life_req')
    manager = create_user('life_mgr')
    admin = create_user('life_admin', is_superuser=True)
    mgr_emp = Employee.objects.create(
        org_unit=org, employee_no='E-LIFE-MGR', full_name='Mgr',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager,
        is_active=True,
    )
    emp = Employee.objects.create(
        org_unit=org, employee_no='E-LIFE-REQ', full_name='Req',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester,
        manager=mgr_emp, is_active=True,
    )
    policy = WorkflowPolicy.objects.create(
        name='Leave Life', corr_type=leave_corr, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve', is_active=True,
    )
    return SimpleNamespace(
        org=org, corr_type=leave_corr, leave_type=annual,
        requester=requester, manager=manager, admin=admin, emp=emp,
    )


def _submit_leave(wf):
    start = date.today() + timedelta(days=20)
    leave = LeaveRecord.objects.create(
        employee=wf.emp, leave_type=wf.leave_type,
        start_date=start, end_date=start, days=Decimal('1'), status='draft',
    )
    corr = Correspondence.objects.create(
        reference_no=f'DRAFT-{leave.pk}',
        corr_type=wf.corr_type, org_unit=wf.org, requester=wf.requester,
        subject_type='people.LeaveRecord', subject_id=leave.pk,
        title='leave', payload={}, status='draft',
    )
    corr = fsm.submit_correspondence(
        corr=corr, by=wf.requester, subject=leave, subject_label='people.LeaveRecord',
    )
    return corr, leave


@pytest.mark.django_db
def test_reopen_after_reject_resets_leave_so_approve_applies(leave_admin_wf):
    wf = leave_admin_wf
    corr, leave = _submit_leave(wf)
    fsm.reject(corr, wf.manager, 'no')
    leave.refresh_from_db()
    assert leave.status == 'rejected'

    corr.refresh_from_db()
    fsm.reopen(corr, wf.admin, 'retry')
    leave.refresh_from_db()
    assert leave.status == 'draft'

    corr.refresh_from_db()
    fsm.approve(corr, wf.manager)
    leave.refresh_from_db()
    assert leave.status == 'approved'


@pytest.mark.django_db
def test_void_after_approve_cancels_leave(leave_admin_wf):
    wf = leave_admin_wf
    corr, leave = _submit_leave(wf)
    fsm.approve(corr, wf.manager)
    leave.refresh_from_db()
    assert leave.status == 'approved'

    corr.refresh_from_db()
    fsm.void(corr, wf.admin, 'payroll error')
    leave.refresh_from_db()
    assert leave.status == 'cancelled'


@pytest.mark.django_db
def test_reopen_after_approve_resets_attendance(db, create_user):
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type-att-life',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='attendance_permission', label='Att',
    )
    personal = ensure_ref('permission_type', 'personal')
    org = OrgUnit.objects.create(
        name='AttLife', slug='att-life', code='ATL', org_type='department',
    )
    requester = create_user('att_life_req')
    manager = create_user('att_life_mgr')
    admin = create_user('att_life_admin', is_superuser=True)
    mgr = Employee.objects.create(
        org_unit=org, employee_no='E-ATL-MGR', full_name='Mgr',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager,
        is_active=True,
    )
    emp = Employee.objects.create(
        org_unit=org, employee_no='E-ATL-REQ', full_name='Req',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester,
        manager=mgr, is_active=True,
    )
    policy = WorkflowPolicy.objects.create(
        name='Att Life', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve', is_active=True,
    )
    day = date.today() + timedelta(days=3)
    record = AttendancePermission.objects.create(
        employee=emp, date=day, permission_type=personal,
        hours=Decimal('2'), status='pending', approved=False,
    )
    corr = Correspondence.objects.create(
        reference_no=f'DRAFT-ATT-{record.pk}',
        corr_type=corr_type, org_unit=org, requester=requester,
        subject_type='people.AttendancePermission', subject_id=record.pk,
        title='att', payload={}, status='draft',
    )
    corr = fsm.submit_correspondence(
        corr=corr, by=requester, subject=record,
        subject_label='people.AttendancePermission',
    )
    fsm.approve(corr, manager)
    record.refresh_from_db()
    assert record.status == 'approved' and record.approved is True

    corr.refresh_from_db()
    fsm.reopen(corr, admin, 'recheck')
    record.refresh_from_db()
    assert record.status == 'pending' and record.approved is False


@pytest.mark.django_db
def test_reject_attendance_sets_rejected_status(db, create_user):
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type-att-rej',
    )
    corr_type = ReferenceValue.objects.create(
        reference_set=corr_set, code='attendance_permission', label='Att',
    )
    personal = ensure_ref('permission_type', 'personal')
    org = OrgUnit.objects.create(
        name='AttRej', slug='att-rej', code='ATR', org_type='department',
    )
    requester = create_user('att_rej_req')
    manager = create_user('att_rej_mgr')
    mgr = Employee.objects.create(
        org_unit=org, employee_no='E-ATR-MGR', full_name='Mgr',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=manager,
        is_active=True,
    )
    emp = Employee.objects.create(
        org_unit=org, employee_no='E-ATR-REQ', full_name='Req',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester,
        manager=mgr, is_active=True,
    )
    policy = WorkflowPolicy.objects.create(
        name='Att Rej', corr_type=corr_type, org_unit=None,
        version='1.0.0', is_active=True,
        numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}',
    )
    WorkflowPolicyStep.objects.create(
        policy=policy, order=1, role='manager', intent='approve', is_active=True,
    )
    record = AttendancePermission.objects.create(
        employee=emp, date=date.today() + timedelta(days=4),
        permission_type=personal, hours=Decimal('1'), status='pending',
    )
    corr = Correspondence.objects.create(
        reference_no=f'DRAFT-ATR-{record.pk}',
        corr_type=corr_type, org_unit=org, requester=requester,
        subject_type='people.AttendancePermission', subject_id=record.pk,
        title='att', payload={}, status='draft',
    )
    corr = fsm.submit_correspondence(
        corr=corr, by=requester, subject=record,
        subject_label='people.AttendancePermission',
    )
    fsm.reject(corr, manager, 'no')
    record.refresh_from_db()
    assert record.status == 'rejected'
    assert record.approved is False


@pytest.mark.django_db
def test_loan_default_is_draft():
    emp_org = OrgUnit.objects.create(
        name='LoanDef', slug='loan-def', code='LDF', org_type='department',
    )
    emp = Employee.objects.create(
        org_unit=emp_org, employee_no='E-LDF', full_name='Loan Def',
        basic_salary='1000.000', join_date=date(2026, 1, 1), is_active=True,
    )
    housing = ensure_ref('loan_type', 'housing')
    loan = Loan.objects.create(
        employee=emp, loan_type=housing, principal=Decimal('1000'),
        term_months=6, start_date=date(2026, 6, 1),
    )
    assert loan.status == 'draft'
