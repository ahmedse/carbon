# Generated migration — add soft-retire flag to BenefitType (Reference Data manager).
#
# Reference Data items are retired via ``is_active=False`` (soft) rather than
# deleted, so historical EmployeeBenefit bindings keep a valid FK. Hard delete
# remains guarded by ``benefit_type_in_use`` in BenefitTypeDetailView.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('people', '0010_backfill_compensation_basic'),
    ]

    operations = [
        migrations.AddField(
            model_name='benefittype',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
