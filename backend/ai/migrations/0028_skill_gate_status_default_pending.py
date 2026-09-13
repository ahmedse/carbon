# P1-05: Skill.gate_status default "pending" + backfill existing NULLs.

from django.db import migrations, models


def backfill_gate_status(apps, schema_editor):
    """Backfill NULL gate_status → 'pending' so the admission sweep picks them up."""
    Skill = apps.get_model("ai", "Skill")
    Skill.objects.filter(gate_status__isnull=True).update(gate_status="pending")


def reverse_backfill(apps, schema_editor):
    # No-op: we cannot recover the original NULL values.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0027_add_evidencerecord"),
    ]

    operations = [
        migrations.RunPython(backfill_gate_status, reverse_backfill),
        migrations.AlterField(
            model_name="skill",
            name="gate_status",
            field=models.TextField(blank=True, default="pending"),
        ),
    ]
