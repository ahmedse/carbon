# Generated manually for P3-07b (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0038_step_journal'),
    ]

    operations = [
        migrations.CreateModel(
            name='RunJournalEntry',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('run_id', models.TextField(db_index=True)),
                ('step_id', models.TextField()),
                ('step_index', models.IntegerField()),
                ('activity_kind', models.TextField()),
                ('sequence', models.IntegerField()),
                ('operation_id', models.TextField(default='')),
                ('canonical_inputs_json', models.JSONField(blank=True, null=True)),
                ('status', models.TextField(default='planned')),
                ('result_json', models.JSONField(blank=True, null=True)),
                ('error', models.TextField(blank=True, default='')),
                ('attempt', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sequence'],
                'indexes': [
                    models.Index(fields=['run_id', 'step_id'], name='ai_runjournal_step_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('run_id', 'step_id', 'sequence'), name='ai_runjournal_seq_uniq'),
                ],
            },
        ),
    ]
