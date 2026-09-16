"""Signals for ``people`` — mirror terminal correspondence decisions onto subjects.

Layering: the ``correspondence`` app stays people-agnostic (it never imports
``people``). The reverse dependency — correspondence approval → Loan / Leave /
Employee profile-change — lives here in ``people``, which already depends on
``correspondence``.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .loan_service import materialize_loan_installments
from .models import Employee, LeaveRecord, Loan
from .profile_change_service import apply_profile_change


def _profile_change_actor(instance):
    """Resolve the acting user for chronicle/governance.

    Prefer the terminal step's ``decided_by`` on ``approver_chain`` (available
    at ``corr.save()`` time). Fall back to the last approve timeline event,
    then the requester.
    """
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


@receiver(post_save, sender='correspondence.Correspondence')
def sync_loan_status_from_correspondence(sender, instance, **kwargs):
    """Sync the linked ``people.Loan`` when its correspondence resolves.

    Only ``people.Loan`` subjects are handled, and only terminal decisions
    mutate the Loan. The transitions are idempotent by construction: each
    ``.filter(status='draft').update(...)`` no-ops once the Loan has left
    ``draft``, so re-saving the correspondence cannot double-transition it.

    On approve → active, also materialize ``LoanInstallment`` rows (NSR-3A).
    Materialization is skip-if-any idempotent.
    """
    if instance.subject_type != 'people.Loan' or not instance.subject_id:
        return

    if instance.status == 'approved':
        Loan.objects.filter(pk=instance.subject_id, status='draft').update(
            status='active',
        )
        loan = Loan.objects.filter(pk=instance.subject_id, status='active').first()
        if loan is not None:
            materialize_loan_installments(loan)
    elif instance.status in ('rejected', 'cancelled'):
        Loan.objects.filter(pk=instance.subject_id, status='draft').update(
            status='cancelled',
        )


@receiver(post_save, sender='correspondence.Correspondence')
def sync_leave_status_from_correspondence(sender, instance, **kwargs):
    """Sync the linked ``people.LeaveRecord`` when its correspondence resolves.

    Only ``people.LeaveRecord`` subjects are handled. Terminal correspondence
    statuses map 1:1 onto existing ``LeaveRecord.STATUS_CHOICES`` (no new
    enums). ``sent_back`` is non-terminal and leaves the record in ``draft``
    so the requester can revise — no LeaveRecord status exists for send-back.

    Transitions are idempotent: each ``.filter(status='draft').update(...)``
    no-ops once the LeaveRecord has left ``draft``.
    """
    if instance.subject_type != 'people.LeaveRecord' or not instance.subject_id:
        return

    if instance.status == 'approved':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='draft').update(
            status='approved',
        )
    elif instance.status == 'rejected':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='draft').update(
            status='rejected',
        )
    elif instance.status == 'cancelled':
        LeaveRecord.objects.filter(pk=instance.subject_id, status='draft').update(
            status='cancelled',
        )


@receiver(post_save, sender='correspondence.Correspondence')
def apply_profile_change_on_approve(sender, instance, **kwargs):
    """Apply allowlisted Employee fields when a profile_change is approved.

    Guards:
    - ``corr_type.code == 'profile_change'`` and ``subject_type == 'people.Employee'``
    - only ``status == 'approved'`` mutates (reject/cancel are no-ops)
    - unknown payload keys ignored via ``PROFILE_CHANGE_ALLOWLIST``
    """
    if instance.status != 'approved':
        return
    if instance.subject_type != 'people.Employee' or not instance.subject_id:
        return
    if not instance.corr_type_id or instance.corr_type.code != 'profile_change':
        return

    employee = Employee.objects.filter(pk=instance.subject_id).first()
    if employee is None:
        return

    payload = instance.payload if isinstance(instance.payload, dict) else {}
    changes = payload.get('changes')
    apply_profile_change(
        employee=employee,
        changes=changes,
        actor=_profile_change_actor(instance),
    )
