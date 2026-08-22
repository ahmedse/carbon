import django.db.models.deletion
from django.db import migrations, models


def migrate_line_items_to_rows(apps, schema_editor):
    """Copy existing LoadoutSheet.line_items JSON into typed LoadoutLine rows."""
    LoadoutSheet = apps.get_model('healthy', 'LoadoutSheet')
    LoadoutLine  = apps.get_model('healthy', 'LoadoutLine')
    lines = []
    for sheet in LoadoutSheet.objects.exclude(line_items=[]).exclude(line_items=None):
        for item in (sheet.line_items or []):
            if not item.get('item_code'):
                continue
            lines.append(LoadoutLine(
                sheet_id=sheet.pk,
                item_code=item['item_code'],
                item_name=item.get('item_name', ''),
                qty_recommended=item.get('qty_recommended', 0) or 0,
                qty_actual=item.get('qty_actual'),
            ))
    if lines:
        LoadoutLine.objects.bulk_create(lines, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('healthy', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoadoutLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_code', models.CharField(max_length=64)),
                ('item_name', models.CharField(blank=True, max_length=200)),
                ('qty_recommended', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('qty_actual', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('sheet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='healthy.loadoutsheet')),
            ],
            options={
                'unique_together': {('sheet', 'item_code')},
            },
        ),
        migrations.AddIndex(
            model_name='loadoutline',
            index=models.Index(fields=['item_code'], name='loadoutline_item_idx'),
        ),
        migrations.CreateModel(
            name='MaterializationCheckpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pipeline_key', models.CharField(max_length=80, unique=True)),
                ('last_row_id', models.BigIntegerField(default=0)),
                ('last_ran_at', models.DateTimeField(blank=True, null=True)),
                ('rows_processed', models.BigIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['pipeline_key'],
            },
        ),
        migrations.RunPython(migrate_line_items_to_rows, reverse_code=migrations.RunPython.noop),
    ]
