# ComplianceRule lifecycle. Existing authoritative rows become Authoritative.
# Formula JSON is not rewritten.

from django.db import migrations, models


def mark_authoritative(apps, schema_editor):
    ComplianceRule = apps.get_model("people", "ComplianceRule")
    ComplianceRule.objects.filter(is_authoritative=True).update(lifecycle="authoritative")


def unmark(apps, schema_editor):
    ComplianceRule = apps.get_model("people", "ComplianceRule")
    ComplianceRule.objects.filter(lifecycle="authoritative").update(lifecycle="draft")


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0031_payrollrun_one_active_period"),
    ]

    operations = [
        migrations.AddField(
            model_name="compliancerule",
            name="lifecycle",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("in_review", "In review"),
                    ("authoritative", "Authoritative"),
                    ("superseded", "Superseded"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
            ),
        ),
        migrations.RunPython(mark_authoritative, unmark),
    ]
