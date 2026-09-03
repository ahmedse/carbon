# Benefit → salary reflection (ADR-0029 additive ledger).
#
# Adds:
#   * EmployeeBenefit.reflect_in_salary — opt-in flag.
#   * EmployeeBenefit.component       — which earning component to mirror into.
#   * EmployeeCompensation.source_benefit — provenance link back to the benefit.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0013_dedupe_compensation_and_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeebenefit',
            name='reflect_in_salary',
            field=models.BooleanField(
                default=False,
                help_text='When True, mirror monthly_amount into the compensation ledger as an earning line.',
            ),
        ),
        migrations.AddField(
            model_name='employeebenefit',
            name='component',
            field=models.ForeignKey(
                blank=True,
                help_text='Earning compensation component this benefit reflects into.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='benefit_lines',
                to='people.compensationcomponent',
            ),
        ),
        migrations.AddField(
            model_name='employeecompensation',
            name='source_benefit',
            field=models.ForeignKey(
                blank=True,
                help_text='EmployeeBenefit this line mirrors (benefit → salary reflection)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='compensation_lines',
                to='people.employeebenefit',
            ),
        ),
    ]
