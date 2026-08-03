# File: emissions/signals.py
# Signal handlers for auto-calculation and stale marking (E3-3, E3-4).

import logging
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from dataschema.models import DataRow
from .models import EmissionFactor, Calculation, CalculationRule

logger = logging.getLogger(__name__)

# Guard against recursive auto-calculate loops
_auto_calc_in_progress = set()


@receiver(post_save, sender=DataRow)
def auto_calculate_on_row_save(sender, instance, created, **kwargs):
    """E3-4: Trigger recalculation when DataRow is saved.

    Only fires when:
      - settings.EMISSIONS_AUTO_CALC is True
      - The DataRow's table has an active CalculationRule with auto_calculate=True
      - We are not already inside an auto-calc (recursion guard)

    Uses transaction.on_commit to ensure the DataRow is persisted before
    calculations run.
    """
    if not getattr(settings, 'EMISSIONS_AUTO_CALC', False):
        return

    table_id = instance.data_table_id
    if not table_id:
        return

    # Prevent re-entrant loops
    guard_key = f"row:{instance.id}"
    if guard_key in _auto_calc_in_progress:
        return

    def _run():
        if guard_key in _auto_calc_in_progress:
            return
        _auto_calc_in_progress.add(guard_key)
        try:
            rules = CalculationRule.objects.filter(
                data_table_id=table_id,
                is_active=True,
                auto_calculate=True,
            ).select_related('emission_factor', 'activity_field')
            if not rules.exists():
                return

            row = DataRow.objects.filter(id=instance.id).first()
            if not row or row.is_archived:
                return

            created_count = 0
            for rule in rules:
                # Skip if already calculated for this rule+data_row
                existing = Calculation.objects.filter(
                    data_row=row,
                    emission_factor=rule.emission_factor,
                    superseded_by__isnull=True,  # only count non-superseded
                ).exists()
                if existing:
                    continue

                try:
                    calc = rule.calculate_for_row(row)
                    if calc:
                        created_count += 1
                except Exception:
                    logger.exception(
                        "Auto-calc failed for rule %s on row %s", rule.id, row.id
                    )

            if created_count > 0:
                logger.info(
                    "Auto-calc: %s calculations created for row %s", created_count, row.id
                )
        finally:
            _auto_calc_in_progress.discard(guard_key)

    transaction.on_commit(_run)


@receiver(pre_save, sender=EmissionFactor)
def mark_calculations_stale_on_factor_edit(sender, instance, **kwargs):
    """E3-3: When an EmissionFactor's factor_value changes, mark all
    non-superseded Calculations using that factor as stale.
    """
    if not instance.pk:
        return  # New factor — nothing to mark stale

    try:
        old = EmissionFactor.objects.only('factor_value').get(pk=instance.pk)
    except EmissionFactor.DoesNotExist:
        return

    if old.factor_value != instance.factor_value:
        count = Calculation.objects.filter(
            emission_factor=instance,
            superseded_by__isnull=True,
            is_stale=False,
        ).update(is_stale=True)
        if count > 0:
            logger.info(
                "Factor '%s' edited: %s calculations marked stale", instance.code, count
            )
