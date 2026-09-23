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


def entitlement_years(profile, code) -> set[int]:
    """Calendar years that already have an entitlement row for this type."""
    return set(
        LeaveEntitlement.objects.filter(
            employee=profile, leave_type__code=code,
        ).values_list("year", flat=True)
    )


def resolve_balance_year(profile, code, start_date, *, open_years: set[int] | None = None) -> int:
    """Year whose entitlement pays for leave starting on ``start_date``.

    The balance screen is the open year (usually this calendar year). A request
    in a later year that has no entitlement row yet is still scored against
    that open bucket — otherwise the employee sees 90 days and submit says
    remaining 0.
    """
    year = start_date.year
    years = open_years if open_years is not None else entitlement_years(profile, code)
    if year in years:
        return year
    prior = [y for y in years if y <= year]
    return max(prior) if prior else year


def compute_balance(profile, code, year):
    """Return ``(entitled, carried_forward, used, pending, remaining)`` Decimals.

    ``used`` and ``pending`` include leave charged to ``year``: a start in
    ``year``, or a later year whose entitlement is not opened yet.
    """
    years = entitlement_years(profile, code)
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
    pending = Decimal('0')
    for record in LeaveRecord.objects.filter(
        employee=profile, leave_type__code=code,
    ):
        if resolve_balance_year(
            profile, code, record.start_date, open_years=years,
        ) != year:
            continue
        if record.status == 'approved' or linked_approved_corr(record):
            used += record.days
        elif linked_in_flight_corr(record):
            pending += record.days

    remaining_signed = opening_balance - used - pending
    remaining = max(Decimal('0'), remaining_signed)
    return entitled, carried_forward, used, pending, remaining


def remaining_identity(entitled, carried_forward, used, pending):
    """Accounting remaining (may be negative) and the floored display value."""
    signed = (
        Decimal(str(entitled or 0))
        + Decimal(str(carried_forward or 0))
        - Decimal(str(used or 0))
        - Decimal(str(pending or 0))
    )
    display = max(Decimal('0'), signed)
    return signed, display
