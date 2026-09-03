# Data migration — dedupe the compensation ledger and personnel chronicle.
#
# Root cause of the "Basic Salary shown twice" / "timeline event shown 5×"
# anomalies seen on Employee 360:
#   1. Migration 0010 backfilled an open-ended 'basic' EmployeeCompensation row
#      per employee at ``join_date`` ("Migrated from Employee.basic_salary"),
#      AND seed_gofsco later materialised another open 'basic' row at
#      2024-01-01 ("Seeded from GOFSCO HR records"). Because the ledger is
#      additive (current = sum of all open rows), Basic Salary double-counted.
#   2. seed_gofsco appends PersonnelEvent rows via record_event() on every run
#      without --clear, so each salary_change / contract_renewed event was
#      duplicated once per re-seed.
#
# This migration is a one-time repair: for every (employee, component) keep the
# most recent open row and close the older ones (effective_end = kept.start),
# and for every (entity, kind, effective_date) keep only the earliest event.

from django.db import migrations
from django.db.models import Count, Min


def dedupe_compensation(apps, schema_editor):
    EmployeeCompensation = apps.get_model('people', 'EmployeeCompensation')

    # Every (employee, component) with more than one open-ended row.
    dup_groups = (
        EmployeeCompensation.objects
        .filter(effective_end__isnull=True)
        .values('employee_id', 'component_id')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
    )
    for group in dup_groups:
        rows = list(
            EmployeeCompensation.objects
            .filter(
                employee_id=group['employee_id'],
                component_id=group['component_id'],
                effective_end__isnull=True,
            )
            .order_by('-effective_start', '-id')
        )
        kept = rows[0]
        for stale in rows[1:]:
            # Close the older row at the start of the row that supersedes it.
            stale.effective_end = kept.effective_start
            stale.save(update_fields=['effective_end'])


def dedupe_events(apps, schema_editor):
    PersonnelEvent = apps.get_model('people', 'PersonnelEvent')

    dup_groups = (
        PersonnelEvent.objects
        .values('entity_type', 'entity_id', 'event_kind', 'effective_date')
        .annotate(n=Count('id'), first_id=Min('id'))
        .filter(n__gt=1)
    )
    for group in dup_groups:
        PersonnelEvent.objects.filter(
            entity_type=group['entity_type'],
            entity_id=group['entity_id'],
            event_kind=group['event_kind'],
            effective_date=group['effective_date'],
        ).exclude(id=group['first_id']).delete()


def forwards(apps, schema_editor):
    dedupe_compensation(apps, schema_editor)
    dedupe_events(apps, schema_editor)


def backwards(apps, schema_editor):
    # Reopening deleted ledger rows / re-materialising deleted events is not
    # reconstructible — this is a destructive dedupe. No-op on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0012_employeebenefit_notes'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
