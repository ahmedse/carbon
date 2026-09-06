"""Reference-number allocation registry.

Gap-free, concurrency-safe reference number generation per
``(corr_type, org_unit, year)``.
"""

from django.db import transaction
from django.utils import timezone

from .models import CorrespondenceRegistry


def allocate_reference_no(*, corr_type, org_unit, numbering_format, prefix='CRS') -> str:
    """Atomically allocate a gap-free reference number.

    Locks/creates the CorrespondenceRegistry row for (corr_type, org_unit, year)
    with select_for_update(), increments counter, and formats numbering_format
    with keys PREFIX, YEAR, SEQ. The unique_together=(corr_type, org_unit, year)
    constraint is the race backstop. Returns e.g. 'CRS-2026-0001'.
    """
    year = timezone.now().year
    with transaction.atomic():
        try:
            reg = CorrespondenceRegistry.objects.select_for_update().get(
                corr_type=corr_type, org_unit=org_unit, year=year)
            reg.counter += 1
            reg.save(update_fields=['counter'])
        except CorrespondenceRegistry.DoesNotExist:
            reg = CorrespondenceRegistry.objects.create(
                corr_type=corr_type, org_unit=org_unit, year=year, counter=1)
        return numbering_format.format(PREFIX=prefix, YEAR=year, SEQ=reg.counter)
