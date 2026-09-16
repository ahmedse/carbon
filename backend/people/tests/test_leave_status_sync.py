# people/tests/test_leave_status_sync.py
# NSR-1B — correspondence approval/rejection must propagate to the linked
# LeaveRecord status so the HR Leave grid does not show eternal ``draft``.

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from correspondence import fsm
from correspondence.models import Correspondence
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue
from people.models import Employee, LeaveRecord


@pytest.fixture
def leave_workflow(db, create_user):
    """Minimal org, leave_request corr_type, leave_type, requester/approver
    users and an employee — enough to drive the correspondence FSM and
    exercise the correspondence → LeaveRecord status sync signal."""
    corr_set = ReferenceSet.objects.create(
        name='correspondence_type', slug='correspondence-type',
    )
    leave_corr = ReferenceValue.objects.create(
        reference_set=corr_set, code='leave_request', label='Leave Request',
    )
    leave_set = ReferenceSet.objects.create(
        name='leave_type', slug='leave-type',
    )
    leave_annual = ReferenceValue.objects.create(
        reference_set=leave_set, code='annual', label='Annual Leave',
    )
    org = OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )
    requester_user = create_user('leave_sync_requester')
    approver_user = create_user('leave_sync_manager')
    employee = Employee.objects.create(
        org_unit=org, employee_no='E-LEAVE-SYNC', full_name='Sync Requester',
        basic_salary='1000.000', join_date=date(2026, 1, 1), user=requester_user,
        is_active=True,
    )
    return SimpleNamespace(
        org=org, corr_type=leave_corr, leave_type=leave_annual,
        requester_user=requester_user, approver_user=approver_user,
        employee=employee,
    )


def _make_leave(employee, leave_type):
    start = date.today() + timedelta(days=5)
    return LeaveRecord.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start,
        end_date=start + timedelta(days=4),
        days=Decimal('5.00'),
        status='draft',
    )


def _submitted_correspondence(wf, leave, reference_no):
    """A single-step (manager) correspondence sitting at the actionable step,
    exactly as ``fsm.submit_correspondence`` would leave it."""
    return Correspondence.objects.create(
        corr_type=wf.corr_type,
        subject_type='people.LeaveRecord',
        subject_id=leave.pk,
        org_unit=wf.org,
        requester=wf.requester_user,
        title='Leave request annual 5',
        payload={},
        status='submitted',
        reference_no=reference_no,
        current_step=0,
        current_approver_ids=[wf.approver_user.id],
        approver_chain=[
            {
                'order': 0,
                'role': 'manager',
                'intent': 'approve',
                'user_ids': [wf.approver_user.id],
            },
        ],
    )


@pytest.mark.django_db
def test_approve_leave_correspondence_approves_leave(leave_workflow):
    wf = leave_workflow
    leave = _make_leave(wf.employee, wf.leave_type)
    corr = _submitted_correspondence(wf, leave, 'LEAVE-SYNC-APPROVE-1')

    fsm.approve(corr, wf.approver_user)

    corr.refresh_from_db()
    leave.refresh_from_db()
    assert corr.status == 'approved'
    assert leave.status == 'approved'


@pytest.mark.django_db
def test_reject_leave_correspondence_rejects_leave(leave_workflow):
    wf = leave_workflow
    leave = _make_leave(wf.employee, wf.leave_type)
    corr = _submitted_correspondence(wf, leave, 'LEAVE-SYNC-REJECT-1')

    fsm.reject(corr, wf.approver_user, 'Insufficient documentation')

    corr.refresh_from_db()
    leave.refresh_from_db()
    assert corr.status == 'rejected'
    assert leave.status == 'rejected'


@pytest.mark.django_db
def test_cancel_leave_correspondence_cancels_leave(leave_workflow):
    wf = leave_workflow
    leave = _make_leave(wf.employee, wf.leave_type)
    corr = _submitted_correspondence(wf, leave, 'LEAVE-SYNC-CANCEL-1')

    fsm.cancel(corr, wf.requester_user)

    corr.refresh_from_db()
    leave.refresh_from_db()
    assert corr.status == 'cancelled'
    assert leave.status == 'cancelled'


@pytest.mark.django_db
def test_send_back_leaves_leave_record_draft(leave_workflow):
    """``sent_back`` is non-terminal; LeaveRecord has no matching choice, so
    the record stays ``draft`` for the requester to revise and resubmit."""
    wf = leave_workflow
    leave = _make_leave(wf.employee, wf.leave_type)
    corr = _submitted_correspondence(wf, leave, 'LEAVE-SYNC-SENDBACK-1')

    fsm.send_back(corr, wf.approver_user, 'Fix the dates')

    corr.refresh_from_db()
    leave.refresh_from_db()
    assert corr.status == 'sent_back'
    assert leave.status == 'draft'


@pytest.mark.django_db
def test_approved_correspondence_does_not_resurrect_rejected_leave(leave_workflow):
    """Guard: sync is scoped to ``status='draft'``, so a late approval cannot
    overwrite a leave that was already rejected."""
    wf = leave_workflow
    leave = _make_leave(wf.employee, wf.leave_type)
    leave.status = 'rejected'
    leave.save(update_fields=['status'])
    corr = _submitted_correspondence(wf, leave, 'LEAVE-SYNC-GUARD-1')

    fsm.approve(corr, wf.approver_user)

    leave.refresh_from_db()
    assert corr.status == 'approved'
    assert leave.status == 'rejected'
