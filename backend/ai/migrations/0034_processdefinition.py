# Generated manually for P3-03 (mirrors ``makemigrations ai`` output).

import ai.models.base
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0033_capability'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessDefinition',
            fields=[
                ('app_identifier', models.CharField(db_index=True, default='carbon', max_length=64)),
                ('org_unit_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('host_user_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('visibility', models.CharField(default='private', max_length=16)),
                ('id', models.CharField(default=ai.models.base.generate_uuid, max_length=36, primary_key=True, serialize=False)),
                ('process_id', models.TextField(db_index=True)),
                ('version', models.TextField(default='')),
                ('owner', models.TextField(default='')),
                ('status', models.TextField(db_index=True, default='draft')),
                ('definition', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['process_id', '-created_at'],
                'indexes': [
                    models.Index(fields=['process_id', 'version'], name='ai_process_lookup_idx'),
                ],
            },
        ),
    ]
