"""Signals for ``people`` — mirror terminal correspondence decisions onto subjects.

Layering: the ``correspondence`` app stays people-agnostic (it never imports
``people``). The reverse dependency — correspondence approval → Loan lifecycle —
lives here in ``people``, which already depends on ``correspondence``.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Loan


@receiver(post_save, sender='correspondence.Correspondence')
def sync_loan_status_from_correspondence(sender, instance, **kwargs):
    """Sync the linked ``people.Loan`` when its correspondence resolves.

    Only ``people.Loan`` subjects are handled, and only terminal decisions
    mutate the Loan. The transitions are idempotent by construction: each
    ``.filter(status='draft').update(...)`` no-ops once the Loan has left
    ``draft``, so re-saving the correspondence cannot double-transition it.
    """
    if instance.subject_type != 'people.Loan' or not instance.subject_id:
        return

    if instance.status == 'approved':
        Loan.objects.filter(pk=instance.subject_id, status='draft').update(
            status='active',
        )
    elif instance.status in ('rejected', 'cancelled'):
        Loan.objects.filter(pk=instance.subject_id, status='draft').update(
            status='cancelled',
        )
