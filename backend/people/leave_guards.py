"""Shared leave request guards (balance, overlap, backdating).

Used by ESS submit (``self_views``) and sent_back revise (``leave_revise``).
"""

from decimal import Decimal

from django.db.models import Sum

from correspondence.models import IN_FLIGHT, Correspondence

from .models import LeaveEntitlement, LeaveRecord

SUBJECT_TYPE = 'people.LeaveRecord'

# Retroactive filing is legitimate (sick leave is reported after the fact),
# but only within living memory. Beyond this window a start date is a data
# error — and the request would be scored against a balance year that has closed.
MAX_BACKDATED_LEAVE_DAYS = 30


def linked_in_flight_corr(record) -> bool:
    """True if this leave has a correspondence still in the workflow (incl. sent_back)."""
    return Correspondence.objects.filter(
        subject_type=SUBJECT_TYPE,
        subject_id=record.pk,
        status__in=IN_FLIGHT,
    ).exists()


# Back-compat alias used by older call sites / tests.
linked_actionable_corr = linked_in_flight_corr


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
    return linked_in_flight_corr(record)


def compute_balance(profile, code, year):
    """Return ``(entitled, carried_forward, used, pending, remaining)`` Decimals.

    ``used`` and ``pending`` are scoped to ``start_date`` in ``year`` so
    cross-year leave does not drain the wrong entitlement bucket.
    """
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
    for record in LeaveRecord.objects.filter(
        employee=profile, leave_type__code=code, start_date__year=year,
    ):
        if linked_in_flight_corr(record):
            pending += record.days

    remaining = max(Decimal('0'), opening_balance - used - pending)
    return entitled, carried_forward, used, pending, remaining
