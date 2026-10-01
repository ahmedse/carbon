from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0033_employee_pifss_attendance_class"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="separation_reason",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Governed separation reason. Blank means the employee has not separated.",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="kind",
            field=models.CharField(
                default="regular",
                help_text="regular or retro. A retro run has its own period identity.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="covers_start",
            field=models.DateField(
                blank=True,
                help_text="Original period start a retro reprices. Null on a regular run.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="covers_end",
            field=models.DateField(
                blank=True,
                help_text="Original period end a retro reprices. Null on a regular run.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payrollrun",
            name="source_run",
            field=models.ForeignKey(
                blank=True,
                help_text="Committed run this retro reprices. Null on a regular run.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="retro_runs",
                to="people.payrollrun",
            ),
        ),
        migrations.CreateModel(
            name="LieuDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("days", models.DecimalField(decimal_places=3, max_digits=8)),
                ("rule_id", models.CharField(max_length=120)),
                ("rule_version", models.CharField(max_length=40)),
                ("earned_on", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lieu_days", to="people.employee")),
                ("payroll_run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lieu_days", to="people.payrollrun")),
                ("payslip_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lieu_days", to="people.payslipline")),
            ],
            options={
                "verbose_name": "Lieu day",
                "verbose_name_plural": "Lieu days",
                "ordering": ["id"],
            },
        ),
    ]
