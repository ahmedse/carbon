# Data migration: backfill Module.domain_attributes from legacy Module.scope.
# Per ADR-0010, carbon's emission scope moves into domain_attributes["carbon"]["scope"].

from django.db import migrations


def backfill_carbon_scope(apps, schema_editor):
    Module = apps.get_model('core', 'Module')
    for module in Module.objects.all().iterator():
        scope = module.scope
        attrs = dict(module.domain_attributes or {})
        attrs.setdefault('carbon', {})
        attrs['carbon'].setdefault('scope', scope)
        if attrs != module.domain_attributes:
            Module.objects.filter(pk=module.pk).update(domain_attributes=attrs)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_module_domain_attributes'),
    ]

    operations = [
        migrations.RunPython(backfill_carbon_scope, noop),
    ]
