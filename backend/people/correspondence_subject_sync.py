"""Mirror correspondence lifecycle onto domain subjects (ADR-0030).

``correspondence`` never imports ``people``. Terminal / admin transitions land
here via ``post_save`` so leave, loan, attendance, and profile_change stay
aligned with the workflow spine.

Transitions
-----------
- approve / reject / cancel — same as historical terminal sync
- reopen (terminal → submitted) — reset subject so a later approve can apply
- void (terminal → archived) — unwind an approved grant; leave other terminals

Loan reopen/void with **paid** installments: demote/cancel the loan header and
delete only unpaid ``scheduled`` rows; paid rows stay for payroll audit.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .loan_service import materialize_loan_installments
from .models import (
    AttendancePermission,
    Employee,
    LeaveEntitlement,
    LeaveRecord,
    Loan,
    LoanInstallment,
)
from .profile_change_service import apply_profile_change, reverse_profile_change
from .leave_guards import compute_balance

logger = logging.getLogger(__name__)

_TERMINAL_FOR_REOPEN = frozenset({'approved', 'rejected', 'cancelled', 'expired'})
_ATTR_PREV = '_people_prev_status'


def _refresh_leave_entitlement_used(record: LeaveRecord) -> None:
    """Denormalize ``LeaveEntitlement.used_days`` from approved records.

    Balance APIs use ``compute_balance`` (approved records). Admin grids still
    read ``used_days`` — keep the ledger column in sync on every terminal leave
    transition so Plane A honesty holds (ADR-0045).
    """
    if record is None or not record.employee_id or not record.leave_type_id:
        return
    year = record.start_date.year if record.start_date else None
    if year is None:
        return
    code = record.leave_type.code
    _entitled, _cf, used, _pending, _rem = compute_balance(
        record.employee, code, year,
    )
    LeaveEntitlement.objects.filter(
        employee_id=record.employee_id,
        year=year,
        leave_type_id=record.leave_type_id,
    ).update(used_days=used)


def _profile_change_actor(instance):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    chain = instance.approver_chain or []
    for step in reversed(chain):
        if not isinstance(step, dict):
            continue
        if step.get('decision') == 'approved' and step.get('decided_by'):
            user = User.objects.filter(pk=step['decided_by']).first()
            if user is not None:
                return user
    event = (
        instance.events.filter(event_type='approved')
        .order_by('-seq')
        .select_related('actor')
        .first()
    )
    if event is not None and event.actor_id:
        return event.actor
    return instance.requester


def _sync_leave(instance, *, prev_status: str | None):
    if instance.subject_type != 'people.LeaveRecord' or not instance.subject_id:
        return

    def _after_status_change():
        record = LeaveRecord.objects.filter(pk=instance.subject_id).select_related(
            'leave_type', 'employee',
        ).first()
        if record is not None:
            _refresh_leave_entitlement_used(record)

    if instance.status == 'approved':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='draft').update(
            status='approved',
        )
        _after_status_change()
        return
    if instance.status == 'rejected':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='draft').update(
            status='rejected',
        )
        _after_status_change()
        return
    if instance.status == 'cancelled':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='draft').update(
            status='cancelled',
        )
        _after_status_change()
        return

    if instance.status == 'submitted' and prev_status in _TERMINAL_FOR_REOPEN:
        # Admin reopen — return subject to draft so a later approve can apply.
        LeaveRecord.objects.filter(
            pk=instance.subject_id,
            status__in=('approved', 'rejected', 'cancelled'),
        ).update(status='draft')
        _after_status_change()
        return

    if instance.status == 'archived' and prev_status == 'approved':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='approved').update(
            status='cancelled',
        )
        _after_status_change()


def _purge_unpaid_installments(loan_id: int) -> None:
    LoanInstallment.objects.filter(loan_id=loan_id, status='scheduled').delete()


def _sync_loan(instance, *, prev_status: str | None):
    if instance.subject_type != 'people.Loan' or not instance.subject_id:
        return

    if instance.status == 'approved':
        Loan.objects.filter(pk=instance.subject_id, status='draft').update(
            status='active',
        )
        loan = Loan.objects.filter(pk=instance.subject_id, status='active').first()
        if loan is not None:
            materialize_loan_installments(loan)
        return

    if instance.status in ('rejected', 'cancelled'):
        Loan.objects.filter(pk=instance.subject_id, status='draft').update(
            status='cancelled',
        )
        return

    if instance.status == 'submitted' and prev_status in _TERMINAL_FOR_REOPEN:
        updated = Loan.objects.filter(
            pk=instance.subject_id,
            status__in=('active', 'cancelled'),
        ).update(status='draft')
        if updated:
            _purge_unpaid_installments(instance.subject_id)
        return

    if instance.status == 'archived' and prev_status == 'approved':
        updated = Loan.objects.filter(
            pk=instance.subject_id, status='active',
        ).update(status='cancelled')
        if updated:
            _purge_unpaid_installments(instance.subject_id)


def _set_attendance_status(pk: int, status: str, *, only_from=None) -> None:
    qs = AttendancePermission.objects.filter(pk=pk)
    if only_from is not None:
        qs = qs.filter(status__in=only_from)
    qs.update(status=status, approved=(status == 'approved'))


def _sync_attendance(instance, *, prev_status: str | None):
    if instance.subject_type != 'people.AttendancePermission' or not instance.subject_id:
        return

    if instance.status == 'approved':
        _set_attendance_status(
            instance.subject_id, 'approved', only_from=('pending',),
        )
        return
    if instance.status == 'rejected':
        _set_attendance_status(
            instance.subject_id, 'rejected', only_from=('pending',),
        )
        return
    if instance.status == 'cancelled':
        _set_attendance_status(
            instance.subject_id, 'cancelled', only_from=('pending',),
        )
        return

    if instance.status == 'submitted' and prev_status in _TERMINAL_FOR_REOPEN:
        _set_attendance_status(
            instance.subject_id,
            'pending',
            only_from=('approved', 'rejected', 'cancelled'),
        )
        return

    if instance.status == 'archived' and prev_status == 'approved':
        _set_attendance_status(
            instance.subject_id, 'cancelled', only_from=('approved',),
        )


def _sync_profile_change(instance, *, prev_status: str | None):
    is_pc = (
        instance.subject_type == 'people.Employee'
        and instance.subject_id
        and instance.corr_type_id
        and instance.corr_type.code == 'profile_change'
    )
    if not is_pc:
        return

    payload = instance.payload if isinstance(instance.payload, dict) else {}
    changes = payload.get('changes')
    employee = Employee.objects.filter(pk=instance.subject_id).first()
    if employee is None:
        return

    if instance.status == 'approved':
        apply_profile_change(
            employee=employee,
            changes=changes,
            actor=_profile_change_actor(instance),
        )
        return

    if instance.status == 'submitted' and prev_status == 'approved':
        reverse_profile_change(
            employee=employee,
            changes=changes,
            actor=_profile_change_actor(instance),
            reason='Reverted on admin reopen of profile_change correspondence',
        )
        return

    if instance.status == 'archived' and prev_status == 'approved':
        reverse_profile_change(
            employee=employee,
            changes=changes,
            actor=_profile_change_actor(instance),
            reason='Reverted on admin void of profile_change correspondence',
        )


@receiver(pre_save, sender='correspondence.Correspondence')
def stash_correspondence_prev_status(sender, instance, **kwargs):
    if not instance.pk:
        setattr(instance, _ATTR_PREV, None)
        return
    try:
        prev = sender.objects.values_list('status', flat=True).get(pk=instance.pk)
    except sender.DoesNotExist:
        prev = None
    setattr(instance, _ATTR_PREV, prev)


@receiver(post_save, sender='correspondence.Correspondence')
def sync_domain_subjects_from_correspondence(sender, instance, **kwargs):
    prev = getattr(instance, _ATTR_PREV, None)
    with transaction.atomic():
        _sync_leave(instance, prev_status=prev)
        _sync_loan(instance, prev_status=prev)
        _sync_attendance(instance, prev_status=prev)
        _sync_profile_change(instance, prev_status=prev)
