# Generated manually for P3-01 (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0032_policydecisionrow_stage'),
    ]

    operations = [
        migrations.CreateModel(
            name='Capability',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('capability_id', models.TextField(unique=True)),
                ('business_name', models.TextField(default='')),
                ('purpose', models.TextField(default='')),
                ('kind', models.TextField(db_index=True, default='read_only')),
                ('inputs', models.JSONField(default=dict)),
                ('preconditions', models.JSONField(default=dict)),
                ('permissions', models.JSONField(default=dict)),
                ('effects', models.JSONField(default=dict)),
                ('side_effects', models.JSONField(default=dict)),
                ('approval_requirements', models.JSONField(default=dict)),
                ('requires_confirmation', models.BooleanField(default=False)),
                ('idempotency', models.TextField(default='')),
                ('verification', models.JSONField(default=dict)),
                ('failure_semantics', models.TextField(default='')),
                ('recovery', models.TextField(default='')),
                ('owner', models.TextField(default='')),
                ('version', models.TextField(default='')),
                ('host_action', models.TextField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['capability_id'],
                'indexes': [
                    models.Index(fields=['kind', 'owner'], name='ai_capability_lookup_idx'),
                ],
            },
        ),
    ]
