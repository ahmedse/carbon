# Generated manually for P3-04 + P3-05a (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0034_processdefinition'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessInterview',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('process_id', models.TextField(db_index=True)),
                ('questions', models.JSONField(default=list)),
                ('answers', models.JSONField(default=list)),
                ('status', models.TextField(db_index=True, default='open')),
                ('signed_by', models.TextField(default='')),
                ('signed_at', models.DateTimeField(blank=True, null=True)),
                ('signature_digest', models.TextField(default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['process_id', '-created_at'],
                'indexes': [
                    models.Index(fields=['process_id', 'status'], name='ai_interview_lookup_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='AutonomyOverride',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('process_id', models.TextField(db_index=True)),
                ('step_id', models.TextField()),
                ('org_unit', models.TextField(default='')),
                ('autonomy', models.TextField(default='human_only')),
                ('set_by', models.TextField(default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['process_id', 'step_id', 'org_unit'],
                'indexes': [
                    models.Index(fields=['process_id', 'step_id'], name='ai_autonomy_lookup_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('process_id', 'step_id', 'org_unit'), name='ai_autonomy_override_unique'),
                ],
            },
        ),
    ]
