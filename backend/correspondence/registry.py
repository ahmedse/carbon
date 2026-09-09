"""Reference-number allocation registry.

Gap-free, concurrency-safe reference number generation. The counter is a single
global sequence per year because ``Correspondence.reference_no`` is globally
unique and the numbering format (``{PREFIX}-{YEAR}-{SEQ:04d}``) carries no
org/type discriminator.
"""

from django.db import transaction
from django.utils import timezone

from .models import CorrespondenceRegistry


def allocate_reference_no(*, numbering_format, prefix='CRS') -> str:
    """Atomically allocate a gap-free global reference number.

    Locks/creates the CorrespondenceRegistry row for ``year`` with
    ``select_for_update()``, increments the counter, and formats
    ``numbering_format`` with keys PREFIX, YEAR, SEQ. The ``year`` unique
    constraint is the race backstop. Returns e.g. 'CRS-2026-0001'.
    """
    year = timezone.now().year
    with transaction.atomic():
        try:
            reg = CorrespondenceRegistry.objects.select_for_update().get(year=year)
            reg.counter += 1
            reg.save(update_fields=['counter'])
        except CorrespondenceRegistry.DoesNotExist:
            reg = CorrespondenceRegistry.objects.create(year=year, counter=1)
        return numbering_format.format(PREFIX=prefix, YEAR=year, SEQ=reg.counter)
