# Generated migration for E3 enterprise features:
# - Calculation.superseded_by (nullable FK to self)
# - Calculation.is_stale (flag for stale calculations)
# - ExportAudit model (who/when/config hash/format)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emissions', '0008_sbtitarget_created_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='calculation',
            name='superseded_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='supersedes',
                to='emissions.calculation',
                help_text='Points to the replacement Calculation that supersedes this one',
            ),
        ),
        migrations.AddField(
            model_name='calculation',
            name='is_stale',
            field=models.BooleanField(
                default=False,
                help_text='True if the emission factor used has been edited since this calculation was created',
            ),
        ),
        migrations.CreateModel(
            name='ExportAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exported_at', models.DateTimeField(auto_now_add=True)),
                ('exported_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('report_format', models.CharField(max_length=20, help_text="e.g., 'xlsx', 'csv', 'json'")),
                ('config_hash', models.CharField(max_length=64, help_text='SHA-256 hash of the report config parameters')),
                ('period_id', models.PositiveIntegerField(blank=True, null=True)),
                ('org_unit_id', models.PositiveIntegerField(blank=True, null=True)),
                ('year', models.PositiveIntegerField(blank=True, null=True)),
                ('grouping', models.CharField(blank=True, default='scope', max_length=20)),
                ('row_count', models.PositiveIntegerField(default=0)),
                ('file_size_bytes', models.PositiveIntegerField(default=0, help_text='Size of the generated file in bytes')),
            ],
            options={
                'verbose_name': 'Export Audit',
                'verbose_name_plural': 'Export Audits',
                'ordering': ['-exported_at'],
                'indexes': [
                    models.Index(fields=['-exported_at'], name='export_audit_exported_at_idx'),
                    models.Index(fields=['exported_by', '-exported_at'], name='export_audit_exported_by_idx'),
                ],
            },
        ),
        migrations.AddIndex(
            model_name='calculation',
            index=models.Index(fields=['is_stale'], name='calc_is_stale_idx'),
        ),
    ]
