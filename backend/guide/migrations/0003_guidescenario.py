# Generated for the camp drama: per-user progress through a stage's scenario.
# Kept apart from GuideProgress so a drama answer never marks a lesson done.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('guide', '0002_guideprogress_step'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GuideScenario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pack_id', models.CharField(max_length=40)),
                ('stage_key', models.CharField(max_length=40)),
                ('beat', models.PositiveSmallIntegerField(default=0, help_text='Drama beats answered honestly so far (0 = none).')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='guide_scenarios', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['user', 'pack_id'], name='guide_guide_user_id_5a1f4d_idx')],
                'constraints': [models.UniqueConstraint(fields=('user', 'pack_id', 'stage_key'), name='uniq_guide_user_pack_stage')],
            },
        ),
    ]
