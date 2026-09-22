"""Shared leave request guards (balance, overlap, backdating).

Used by ESS submit (``self_views``) and sent_back revise (``leave_revise``).
"""

from decimal import Decimal

from django.db.models import Sum

from correspondence.models import ACTIONABLE, Correspondence

from .models import LeaveEntitlement, LeaveRecord

SUBJECT_TYPE = 'people.LeaveRecord'

# Retroactive filing is legitimate (sick leave is reported after the fact),
# but only within living memory. Beyond this window a start date is a data
# error — and the request would be scored against a balance year that has closed.
MAX_BACKDATED_LEAVE_DAYS = 30


def linked_actionable_corr(record) -> bool:
    """True if this leave record has a workflow correspondence awaiting action."""
    return Correspondence.objects.filter(
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status__in=ACTIONABLE,
    ).exists()


def linked_approved_corr(record) -> bool:
    """True if this leave record has an approved workflow correspondence."""
    return Correspondence.objects.filter(
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status='approved',
    ).exists()


def record_blocks_overlap(record) -> bool:
    """Whether an existing leave record should block a new/revised request."""
    if record.status in ('approved', 'submitted'):
        return True
    return linked_actionable_corr(record)


def compute_balance(profile, code, year):
    """Return ``(entitled, carried_forward, used, pending, remaining)`` Decimals."""
    agg = LeaveEntitlement.objects.filter(
        employee=profile, year=year, leave_type__code=code,
    ).aggregate(
        total_entitled=Sum('entitled_days'),
        total_carried=Sum('carried_forward'),
    )
    entitled = agg['total_entitled'] or Decimal('0')
    carried_forward = agg['total_carried'] or Decimal('0')
    opening_balance = entitled + carried_forward

    used = Decimal('0')
    for record in LeaveRecord.objects.filter(
        employee=profile, leave_type__code=code, start_date__year=year,
    ):
        if record.status == 'approved' or linked_approved_corr(record):
            used += record.days

    pending = Decimal('0')
    for record in LeaveRecord.objects.filter(employee=profile, leave_type__code=code):
        if linked_actionable_corr(record):
            pending += record.days

    remaining = max(Decimal('0'), opening_balance - used - pending)
    return entitled, carried_forward, used, pending, remaining
