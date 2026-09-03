# Data migration — backfill benefit → salary reflection.
#
# With the reflect_in_salary / component / source_benefit plumbing in place
# (0014), existing seeded benefits (ACCOM, TICKETS, VEHICLE) were still just a
# standalone M5 C&B ledger with no compensation lines — so they never showed up
# in the Pay tab.
#
# This migration turns on reflection for every existing benefit that carries a
# positive monthly_amount (zero-amount benefits like MEDICAL have nothing to
# mirror), maps it to the default 'other_allowance' earning component, and
# materialises the mirrored EmployeeCompensation line tagged with source_benefit
# for auditability. Benefits already reflected (reflect_in_salary=True or an
# existing source_benefit line) are left untouched so re-running is idempotent.

from django.db import migrations


def forwards(apps, schema_editor):
    EmployeeBenefit = apps.get_model('people', 'EmployeeBenefit')
    EmployeeCompensation = apps.get_model('people', 'EmployeeCompensation')
    CompensationComponent = apps.get_model('people', 'CompensationComponent')

    component, _ = CompensationComponent.objects.get_or_create(
        code='other_allowance',
        defaults={
            'name': 'Other Allowance',
            'name_ar': 'بدل آخر',
            'direction': 'earning',
            'is_wps_relevant': True,
            'is_variable': True,
            'sort_order': 90,
            'is_active': True,
        },
    )

    for benefit in EmployeeBenefit.objects.filter(monthly_amount__gt=0):
        already_reflected = (
            benefit.reflect_in_salary
            or EmployeeCompensation.objects.filter(source_benefit_id=benefit.pk).exists()
        )
        if already_reflected:
            continue

        benefit.reflect_in_salary = True
        benefit.component_id = component.pk
        benefit.save(update_fields=['reflect_in_salary', 'component'])

        EmployeeCompensation.objects.create(
            employee_id=benefit.employee_id,
            component=component,
            amount=benefit.monthly_amount,
            currency='KWD',
            frequency='monthly',
            effective_start=benefit.effective_start,
            effective_end=benefit.effective_end,
            source_benefit_id=benefit.pk,
            reason_note=f'Benefit: {benefit.benefit_type.name}',
        )


def backwards(apps, schema_editor):
    EmployeeBenefit = apps.get_model('people', 'EmployeeBenefit')
    EmployeeCompensation = apps.get_model('people', 'EmployeeCompensation')

    # Reset reflection for every positive-amount benefit and remove its
    # mirrored lines. Best-effort: this also reverts a manually-reflected
    # benefit if it used the default other_allowance component.
    benefits = EmployeeBenefit.objects.filter(
        monthly_amount__gt=0,
        reflect_in_salary=True,
        component__code='other_allowance',
    )
    ids = list(benefits.values_list('pk', flat=True))
    EmployeeCompensation.objects.filter(source_benefit_id__in=ids).delete()
    benefits.update(reflect_in_salary=False, component=None)


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0014_benefit_reflect_in_salary'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
