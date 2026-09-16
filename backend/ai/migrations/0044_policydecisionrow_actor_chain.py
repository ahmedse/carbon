# Generated manually for PEC-ID-1 (ADR-0033 identity propagation).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0043_seed_deepseek_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="policydecisionrow",
            name="actor_chain",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="policydecisionrow",
            name="instance_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="policydecisionrow",
            name="request_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
    ]
