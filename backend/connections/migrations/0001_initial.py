# Generated migration for connections app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalog', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DataSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=140, unique=True)),
                ('source_type', models.CharField(choices=[('excel', 'Excel / CSV'), ('database', 'Database'), ('api', 'REST API'), ('mdm', 'MDM System'), ('iot', 'IoT / Sensor'), ('manual', 'Manual Entry')], max_length=20)),
                ('description', models.TextField(blank=True)),
                ('connection_config', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('error', 'Error')], default='active', max_length=20)),
                ('last_tested_at', models.DateTimeField(blank=True, null=True)),
                ('last_test_status', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('domain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='data_sources', to='catalog.datadomain')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_sources', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ConsumingConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=140, unique=True)),
                ('system_type', models.CharField(choices=[('pulse', 'Pulse AI'), ('powerbi', 'Power BI'), ('tableau', 'Tableau'), ('api_key', 'API Client'), ('webhook', 'Webhook')], max_length=20)),
                ('description', models.TextField(blank=True)),
                ('api_key_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('api_key_salt', models.CharField(blank=True, max_length=32)),
                ('scopes', models.JSONField(blank=True, default=list, help_text='List of DataTable IDs or domain slugs')),
                ('is_active', models.BooleanField(default=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_connections', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
