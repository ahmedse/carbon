# Generated migration — backfill basic salary into the compensation ledger (ADR-0029 §3).
#
# Seeds one open-ended 'basic' CompensationComponent ledger row per employee whose
# ``basic_salary > 0``, so the ledger becomes the single source of truth while
# ``Employee.basic_salary`` is retained as a legacy mirror.

from django.db import migrations
from django.utils import timezone


def backfill_basic_salary(apps, schema_editor):
    CompensationComponent = apps.get_model('people', 'CompensationComponent')
    Employee = apps.get_model('people', 'Employee')
    EmployeeCompensation = apps.get_model('people', 'EmployeeCompensation')

    component, _created = CompensationComponent.objects.get_or_create(
        code='basic',
        defaults={
            'name': 'Basic Salary',
            'direction': 'earning',
            'is_eosi_base': True,
            'is_gosi_base': True,
            'is_wps_relevant': True,
            'is_active': True,
        },
    )

    today = timezone.localdate()
    for employee in Employee.objects.filter(basic_salary__gt=0):
        EmployeeCompensation.objects.create(
            employee=employee,
            component=component,
            amount=employee.basic_salary,
            currency='KWD',
            frequency='monthly',
            effective_start=employee.join_date or today,
            effective_end=None,
            reason_note='Migrated from Employee.basic_salary',
        )


def reverse_backfill(apps, schema_editor):
    EmployeeCompensation = apps.get_model('people', 'EmployeeCompensation')
    EmployeeCompensation.objects.filter(
        component__code='basic',
        reason_note='Migrated from Employee.basic_salary',
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0009_compensation_ledger'),
    ]

    operations = [
        migrations.RunPython(backfill_basic_salary, reverse_backfill),
    ]
