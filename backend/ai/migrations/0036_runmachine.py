# Generated manually for P3-07a (mirrors ``makemigrations ai`` output).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0035_processinterview_autonomyoverride'),
    ]

    operations = [
        migrations.AddField(
            model_name='run',
            name='run_state',
            field=models.TextField(default='planned'),
        ),
        migrations.AddField(
            model_name='run',
            name='definition_id',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='run',
            name='definition_version',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='run',
            name='idempotency_key',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='run',
            name='kill_switched_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='runstep',
            name='step_state',
            field=models.TextField(default='planned'),
        ),
        migrations.AddField(
            model_name='runstep',
            name='step_id',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='runstep',
            name='idempotency_key',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='runstep',
            name='outcome',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='runstep',
            name='retry_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='runstep',
            name='last_error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddIndex(
            model_name='runstep',
            index=models.Index(fields=['run_id', 'step_id'], name='ai_runstep_lookup_idx'),
        ),
        migrations.AddConstraint(
            model_name='runstep',
            constraint=models.UniqueConstraint(
                condition=models.Q(('step_id__gt', '')),
                fields=('run_id', 'step_id'),
                name='ai_runstep_run_step_uniq',
            ),
        ),
    ]
