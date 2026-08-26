import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_datadomain_search_vector_and_more'),
        ('dataschema', '0010_datatable_last_data_updated_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='FreshnessPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_level', models.CharField(choices=[('info', 'Info'), ('warning', 'Warning'), ('error', 'Error')], default='warning', max_length=10)),
                ('enabled', models.BooleanField(default=True)),
                ('last_alerted_at', models.DateTimeField(blank=True, null=True)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('max_age_hours', models.PositiveIntegerField(default=24)),
                ('table', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='freshness_policy', to='dataschema.datatable')),
            ],
        ),
    ]
