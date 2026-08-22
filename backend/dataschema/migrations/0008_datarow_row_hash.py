"""Add DataRow.row_hash (content dedup key for the ingest watermark).

Backfills hashes for pre-existing rows so incremental re-runs can dedup
against rows ingested before this migration.
"""
import hashlib
import json

from django.db import migrations, models


def _row_hash_of(values):
    normalized = {str(k).lower(): v for k, v in (values or {}).items()}
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(',', ':'),
                   default=str).encode('utf-8')
    ).hexdigest()


def backfill_row_hashes(apps, schema_editor):
    DataRow = apps.get_model('dataschema', 'DataRow')
    batch = []
    for row in DataRow.objects.all().iterator(chunk_size=2000):
        row.row_hash = _row_hash_of(row.values)
        batch.append(row)
        if len(batch) >= 1000:
            DataRow.objects.bulk_update(batch, ['row_hash'])
            batch = []
    if batch:
        DataRow.objects.bulk_update(batch, ['row_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('dataschema', '0007_datarow_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='datarow',
            name='row_hash',
            field=models.CharField(
                max_length=64, db_index=True, blank=True, default=''),
        ),
        migrations.RunPython(backfill_row_hashes, migrations.RunPython.noop),
    ]
