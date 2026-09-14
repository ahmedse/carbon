# Generated manually for P3-07b (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0037_reconciliation_escalation'),
    ]

    operations = [
        migrations.AddField(
            model_name='runstep',
            name='step_kind',
            field=models.TextField(default='activity'),
        ),
        migrations.CreateModel(
            name='StepJournalEntry',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('run_id', models.TextField(db_index=True)),
                ('step_id', models.TextField()),
                ('event_type', models.TextField()),
                ('sequence', models.IntegerField()),
                ('payload', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['run_id', 'sequence'],
                'indexes': [
                    models.Index(fields=['run_id', 'sequence'], name='ai_journal_run_seq_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('run_id', 'sequence'), name='ai_journal_run_seq_uniq'),
                ],
            },
        ),
    ]
