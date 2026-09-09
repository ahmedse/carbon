"""Consolidate CorrespondenceRegistry counters into one global row per year."""

import re

from django.db import migrations, models


def consolidate_global_registry(apps, schema_editor):
    Registry = apps.get_model('correspondence', 'CorrespondenceRegistry')
    Correspondence = apps.get_model('correspondence', 'Correspondence')

    max_counter = {}
    for row in Registry.objects.all():
        max_counter[row.year] = max(max_counter.get(row.year, 0), row.counter)

    # Also derive from any already-issued reference numbers (in case seeds or
    # tests created correspondence rows without going through the registry), so
    # no number is ever re-used.
    ref_re = re.compile(r'^[A-Za-z]+-(\d{4})-(\d+)$')
    for reference_no in Correspondence.objects.values_list('reference_no', flat=True):
        match = ref_re.match(reference_no or '')
        if not match:
            continue
        year = int(match.group(1))
        seq = int(match.group(2))
        max_counter[year] = max(max_counter.get(year, 0), seq)

    Registry.objects.all().delete()
    for year, counter in sorted(max_counter.items()):
        Registry.objects.create(year=year, counter=counter)


def reverse_consolidate(apps, schema_editor):
    # Reversing a data consolidation is lossy by nature; keep the global rows.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('correspondence', '0002_correspondenceregistry_drop_unit_keys'),
    ]

    operations = [
        migrations.RunPython(consolidate_global_registry, reverse_consolidate),
        migrations.AlterField(
            model_name='correspondenceregistry',
            name='year',
            field=models.PositiveSmallIntegerField(unique=True),
        ),
    ]
