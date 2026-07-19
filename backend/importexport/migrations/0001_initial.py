# Generated migration for importexport app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('dataschema', '0003_tablerelation'),
        ('connections', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('slug', models.SlugField(blank=True, max_length=140, unique=True)),
                ('description', models.TextField(blank=True)),
                ('format', models.CharField(choices=[('csv', 'CSV'), ('excel', 'Excel'), ('json', 'JSON')], default='excel', max_length=20)),
                ('filters', models.JSONField(blank=True, default=dict, help_text='Field-level filters, date range, etc.')),
                ('schedule', models.CharField(choices=[('manual', 'Manual'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='manual', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('data_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_projects', to='dataschema.datatable')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_export_projects', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ImportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='imports/%Y/%m/')),
                ('format', models.CharField(choices=[('csv', 'CSV'), ('excel', 'Excel')], default='excel', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('done', 'Done'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('row_count', models.IntegerField(blank=True, null=True)),
                ('error_count', models.IntegerField(blank=True, null=True)),
                ('log', models.JSONField(blank=True, default=list, help_text='List of {row, error} objects')),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('data_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='import_jobs', to='dataschema.datatable')),
                ('source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_jobs', to='connections.datasource')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ExportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('format', models.CharField(choices=[('csv', 'CSV'), ('excel', 'Excel'), ('json', 'JSON')], max_length=20)),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('file', models.FileField(blank=True, null=True, upload_to='exports/%Y/%m/')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('ready', 'Ready'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('row_count', models.IntegerField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('data_table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='export_jobs', to='dataschema.datatable')),
                ('export_project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='jobs', to='importexport.exportproject')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='export_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
