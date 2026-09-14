# Generated manually for P3-08 (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0036_runmachine'),
    ]

    operations = [
        migrations.AddField(
            model_name='runstep',
            name='operation_id',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.CreateModel(
            name='ReconciliationEscalation',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('run_id', models.TextField(db_index=True)),
                ('step_id', models.TextField()),
                ('process_id', models.TextField(default='')),
                ('operation_id', models.TextField(default='')),
                ('read_back_status', models.TextField(default='unknown')),
                ('read_back_detail', models.TextField(blank=True, default='')),
                ('reason', models.TextField(blank=True, default='')),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'constraints': [
                    models.UniqueConstraint(fields=('run_id', 'step_id'), name='ai_reconcile_step_uniq'),
                ],
            },
        ),
    ]
