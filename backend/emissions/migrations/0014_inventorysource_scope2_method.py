from django.db import migrations, models


def persist_scope2_location_based(apps, schema_editor):
    InventorySource = apps.get_model('emissions', 'InventorySource')
    Calculation = apps.get_model('emissions', 'Calculation')
    InventorySource.objects.filter(scope=2).filter(
        models.Q(scope2_method__isnull=True) | models.Q(scope2_method=''),
    ).update(scope2_method='location_based')
    InventorySource.objects.exclude(scope=2).update(scope2_method='')
    Calculation.objects.filter(scope=2).filter(
        models.Q(scope2_method__isnull=True) | models.Q(scope2_method=''),
    ).update(scope2_method='location_based')


class Migration(migrations.Migration):

    dependencies = [
        ('emissions', '0013_inventorysource_coverageaction_inventorysourcestatus_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventorysource',
            name='scope2_method',
            field=models.CharField(
                blank=True,
                choices=[('location_based', 'Location-based'), ('market_based', 'Market-based')],
                default='',
                help_text='Required for Scope 2: location_based or market_based. Blank for Scope 1/3.',
                max_length=20,
            ),
        ),
        migrations.RunPython(persist_scope2_location_based, migrations.RunPython.noop),
    ]
