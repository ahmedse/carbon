# Rewritten for Phase P1C — Dataset Hub adoption, SELF-CONTAINED in catalog.
#
# The former datahub app is fully removed; catalog owns the models and the
# tables. This migration creates the 6 models (Dataset, DatasetVersion,
# DatasetVersionMember, DataContract, DataContractViolation, DatasetAccessPolicy)
# directly in catalog's state, transcribed field-for-field from the former
# datahub 0001_initial + 0002 (the authoritative auto-generated state), with FK
# targets pointing at catalog/core/connections/dataschema/auth. The M2M through
# table (Dataset_tags) is created implicitly by CreateModel(Dataset).
#
# On databases where the previous version of this migration already ran (with
# RunSQL renames datahub_* -> catalog_*), the tables already exist as catalog_*;
# the migration is recorded as applied and is skipped. Fresh databases create
# the catalog_* tables directly.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_remove_assetprofile_assetprof_active_domain_idx_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('connections', '0001_initial'),
        ('core', '0014_backfill_domain_attributes'),
        ('dataschema', '0005_add_dq_flags'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Catalog state adoption (CreateModel, transcribed verbatim) ──
                migrations.CreateModel(
                    name='Dataset',
                    fields=[
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('name', models.CharField(max_length=200)),
                        ('slug', models.SlugField(max_length=220, unique=True)),
                        ('description', models.TextField(blank=True)),
                        ('classification', models.CharField(choices=[('public', 'Public'), ('internal', 'Internal'), ('confidential', 'Confidential'), ('pii', 'PII'), ('sensitive', 'Sensitive')], default='internal', max_length=20)),
                        ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('deprecated', 'Deprecated'), ('archived', 'Archived')], default='draft', max_length=20)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_datasets', to=settings.AUTH_USER_MODEL)),
                        ('domain', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='datasets', to='catalog.datadomain')),
                        ('module', models.ForeignKey(help_text='CBAC scope anchor — controls which ScopedRole grants access.', on_delete=django.db.models.deletion.PROTECT, related_name='datasets', to='core.module')),
                        ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_datasets', to=settings.AUTH_USER_MODEL)),
                        ('steward', models.ForeignKey(blank=True, help_text='Data steward accountable for this data product (advisory).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stewarded_datasets', to=settings.AUTH_USER_MODEL)),
                        ('source', models.ForeignKey(blank=True, help_text='Origin connection (ERP, CSV, API). Null = manually entered.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='datasets', to='connections.datasource')),
                        ('tags', models.ManyToManyField(blank=True, related_name='datasets', to='catalog.tag')),
                    ],
                    options={
                        'ordering': ['-updated_at'],
                    },
                ),
                migrations.CreateModel(
                    name='DatasetVersion',
                    fields=[
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('version_number', models.PositiveIntegerField()),
                        ('row_count', models.BigIntegerField(blank=True, null=True)),
                        ('schema_snapshot', models.JSONField(default=dict)),
                        ('health_score', models.FloatField(blank=True, null=True)),
                        ('health_detail', models.JSONField(default=dict, help_text='{"completeness": 0.98, "validity": 0.95, "freshness": 1.0}')),
                        ('dq_job_id', models.CharField(blank=True, max_length=200)),
                        ('lineage', models.JSONField(default=dict)),
                        ('status', models.CharField(choices=[('pending', 'Pending DQ Review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                        ('approved_at', models.DateTimeField(blank=True, null=True)),
                        ('rejection_reason', models.TextField(blank=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_dataset_versions', to=settings.AUTH_USER_MODEL)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_dataset_versions', to=settings.AUTH_USER_MODEL)),
                        ('data_table', models.ForeignKey(help_text='The DataTable holding the rows for this version.', on_delete=django.db.models.deletion.PROTECT, related_name='dataset_versions', to='dataschema.datatable')),
                        ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='catalog.dataset')),
                    ],
                    options={
                        'ordering': ['-version_number'],
                        'unique_together': {('dataset', 'version_number')},
                    },
                ),
                migrations.AddField(
                    model_name='dataset',
                    name='current_version',
                    field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='current_for_dataset', to='catalog.datasetversion'),
                ),
                migrations.CreateModel(
                    name='DatasetVersionMember',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('order', models.PositiveIntegerField(default=0)),
                        ('label', models.CharField(blank=True, help_text='Semantic name within the product, e.g. "orders", "customers".', max_length=120)),
                        ('row_count', models.IntegerField(default=0)),
                        ('schema_snapshot', models.JSONField(blank=True, default=dict)),
                        ('health_score', models.FloatField(blank=True, null=True)),
                        ('health_detail', models.JSONField(blank=True, default=dict)),
                        ('dq_job_id', models.CharField(blank=True, max_length=64)),
                        ('data_table', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='dataset_version_members', to='dataschema.datatable')),
                        ('version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='catalog.datasetversion')),
                    ],
                    options={
                        'verbose_name': 'dataset version member',
                        'verbose_name_plural': 'dataset version members',
                        'ordering': ['order', 'id'],
                        'unique_together': {('version', 'data_table')},
                    },
                ),
                migrations.CreateModel(
                    name='DataContract',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('required_fields', models.JSONField(default=list, help_text='Field names that must always be present.')),
                        ('min_completeness', models.FloatField(blank=True, null=True)),
                        ('min_validity', models.FloatField(blank=True, null=True)),
                        ('min_health_score', models.FloatField(blank=True, null=True)),
                        ('freshness_hours', models.PositiveIntegerField(blank=True, help_text='If set, a version older than this many hours triggers a freshness violation.', null=True)),
                        ('consumer_apps', models.JSONField(default=list, help_text='App slugs (from AppManifest) that consume this dataset.')),
                        ('is_active', models.BooleanField(default=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                        ('dataset', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='contract', to='catalog.dataset')),
                    ],
                ),
                migrations.CreateModel(
                    name='DataContractViolation',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('violation_type', models.CharField(choices=[('schema', 'Schema — missing required field'), ('quality', 'Quality — score below minimum SLA'), ('freshness', 'Freshness — version too old')], max_length=20)),
                        ('detail', models.JSONField(default=dict)),
                        ('detected_at', models.DateTimeField(auto_now_add=True)),
                        ('resolved_at', models.DateTimeField(blank=True, null=True)),
                        ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                        ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='violations', to='catalog.datacontract')),
                        ('dataset_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contract_violations', to='catalog.datasetversion')),
                    ],
                    options={
                        'ordering': ['-detected_at'],
                    },
                ),
                migrations.CreateModel(
                    name='DatasetAccessPolicy',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('can_view', models.BooleanField(default=True)),
                        ('can_ingest', models.BooleanField(default=False)),
                        ('can_approve', models.BooleanField(default=False)),
                        ('granted_at', models.DateTimeField(auto_now_add=True)),
                        ('note', models.TextField(blank=True)),
                        ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_policies', to='catalog.dataset')),
                        ('granted_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='granted_dataset_policies', to=settings.AUTH_USER_MODEL)),
                        ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dataset_policies', to='auth.group')),
                        ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dataset_policies', to=settings.AUTH_USER_MODEL)),
                    ],
                ),
    ]
