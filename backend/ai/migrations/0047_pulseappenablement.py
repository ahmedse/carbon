"""PulseAppEnablement: steward per-app Pulse jail (Platform → Pulse)."""

from django.db import migrations, models
import ai.models.base


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0046_seed_cheap_poe_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="PulseAppEnablement",
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
                ("instance_id", models.CharField(db_index=True, max_length=64)),
                ("app_slug", models.CharField(max_length=64)),
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.CharField(blank=True, default="", max_length=150)),
            ],
            options={
                "app_label": "ai",
                "unique_together": {("instance_id", "app_slug")},
            },
        ),
    ]
