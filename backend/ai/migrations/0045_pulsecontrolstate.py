# Generated manually for ADR-0036 Pulse Control Plane

from django.db import migrations, models
import ai.models.base


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0044_policydecisionrow_actor_chain"),
    ]

    operations = [
        migrations.CreateModel(
            name="PulseControlState",
            fields=[
                (
                    "id",
                    models.CharField(
                        default=ai.models.base.generate_uuid,
                        max_length=36,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("instance_id", models.CharField(db_index=True, max_length=64, unique=True)),
                (
                    "containment_level",
                    models.CharField(db_index=True, default="normal", max_length=32),
                ),
                ("autonomy_ceiling", models.CharField(blank=True, default="", max_length=32)),
                ("learning_admissions_frozen", models.BooleanField(default=False)),
                ("daily_budget_usd", models.FloatField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.CharField(blank=True, default="", max_length=150)),
            ],
            options={
                "app_label": "ai",
            },
        ),
    ]
