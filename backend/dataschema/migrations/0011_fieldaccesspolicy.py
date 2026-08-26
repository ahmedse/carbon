# Generated migration for FieldAccessPolicy model (EPH-4A: Column-Level RBAC)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dataschema', '0010_datatable_last_data_updated_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldAccessPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('required_capability', models.CharField(help_text='Users WITHOUT this capability are denied/masked. E.g. catalog:view_pii', max_length=100)),
                ('action', models.CharField(choices=[('deny', 'Deny (hide field entirely)'), ('mask', 'Mask (redact value, show field name)')], default='deny', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_field_access_policies', to=settings.AUTH_USER_MODEL)),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_policies', to='dataschema.datafield')),
            ],
            options={
                'unique_together': {('field', 'required_capability')},
            },
        ),
    ]
