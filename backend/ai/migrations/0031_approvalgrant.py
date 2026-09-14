# Generated manually for P3-06 (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0030_policydecisionrow'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalGrant',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('process_instance', models.CharField(blank=True, db_index=True, max_length=36, null=True)),
                ('object_id', models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ('object_type', models.CharField(blank=True, db_index=True, max_length=128, null=True)),
                ('process_version', models.TextField(default='')),
                ('capability', models.TextField(db_index=True)),
                ('capability_version', models.TextField(default='')),
                ('canonical_args', models.JSONField(default=dict)),
                ('object_revisions', models.JSONField(default=dict)),
                ('evidence_digest', models.TextField(default='')),
                ('effect_limits', models.JSONField(default=dict)),
                ('expires_at', models.DateTimeField()),
                ('status', models.TextField(db_index=True, default='active')),
                ('granted_by', models.TextField(default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['capability', 'status', 'expires_at'], name='ai_approval_active_idx'),
                ],
            },
        ),
    ]
