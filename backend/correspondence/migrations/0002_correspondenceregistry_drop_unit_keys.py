"""Drop the per-unit keys from CorrespondenceRegistry (schema only).

``Correspondence.reference_no`` is globally unique but the registry was keyed on
``(corr_type, org_unit, year)`` while the numbering format carries no org/type
discriminator — so two org units would both allocate ``CRS-<year>-0001`` and
collide. This migration removes the per-unit key columns; the counter data is
consolidated in the next migration.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('correspondence', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='correspondenceregistry',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='correspondenceregistry',
            name='corr_type',
        ),
        migrations.RemoveField(
            model_name='correspondenceregistry',
            name='org_unit',
        ),
    ]
