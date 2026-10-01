from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0034_payroll_retro_lieu_separation"),
    ]

    operations = [
        migrations.AddField(
            model_name="payrollrun",
            name="exceptions",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Named per-employee holds from compute: missing join date, "
                    "leave not priced, or missing verified basic. Other employees "
                    "are still priced."
                ),
            ),
        ),
    ]
