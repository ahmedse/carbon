"""Signals for dataschema — keep DataTable freshness metadata in sync."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import DataRow, DataTable


@receiver(post_save, sender=DataRow)
def touch_table_last_data_updated_at(sender, instance, **kwargs):
    """Mark the owning table as updated whenever a row is written.

    Uses a QuerySet.update() so we bypass ``DataTable.save()`` (name
    normalization) and do not recurse through any table signals.
    """
    if instance.data_table_id is None:
        return
    DataTable.objects.filter(pk=instance.data_table_id).update(
        last_data_updated_at=timezone.now(),
    )
