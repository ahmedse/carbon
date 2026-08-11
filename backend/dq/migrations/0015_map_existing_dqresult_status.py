# Generated manually — TASK-DQ-CORE-P4-PULSE deliverable 4 (fail-visible).
# Data migration: map existing DQResult rows to the new `status` column
# introduced by 0014 (which defaulted all existing rows to 'passed').
#   passed=True  → 'passed'
#   passed=False → 'failed'
#   passed=None  → 'skipped_unavailable' (only possible post-0014 in dev;
#                  pre-P4 the column was non-null, so legacy rows are True/False)
# Run AFTER the schema migration so `status` exists. Reversible no-op.
from django.db import migrations


def map_existing_results(apps, schema_editor):
    DQResult = apps.get_model('dq', 'DQResult')
    DQResult.objects.filter(passed=True).update(status='passed')
    DQResult.objects.filter(passed=False).update(status='failed')
    DQResult.objects.filter(passed__isnull=True).update(status='skipped_unavailable')


def unmap_existing_results(apps, schema_editor):
    # Reverse is a no-op — `status` carries real meaning now; dropping it
    # would lose information, so we only reverse the schema field, not data.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('dq', '0014_dqresult_status_alter_dqjob_job_type_and_more'),
    ]

    operations = [
        migrations.RunPython(map_existing_results, unmap_existing_results),
    ]
