"""Register the Healthy Foods Factory app (idempotent).

Creates, in order:
  1. AppManifest + AppActivation via AppRegistryService.
  2. The 5 healthy modules (core.Module).
  3. The read-only ERP DataSource (connections.DataSource).
  4. The 5 pipeline datasets + DataContracts (catalog).

Safe to re-run: every step uses get_or_create / update_or_create.
"""
from django.core.management.base import BaseCommand

from healthy.services import (
    MODULES, PIPELINES, ERPSnapshotService, HealthyPipelineService,
)


class Command(BaseCommand):
    help = 'Register the Healthy Foods Factory app (manifest, modules, DataSource, datasets).'

    def handle(self, *args, **options):
        from appregistry.services import AppRegistryService
        from core.models import Module

        # 1. AppManifest (+ activation record).
        manifest, _created = AppRegistryService.register_manifest(
            slug='healthy',
            name='Healthy Foods Factory',
            version='1.0.0',
            description=(
                'Fresh-food operations: returns/load-out, churn, demand, '
                'AR collections, and a transaction classifier.'
            ),
            icon='FactoryIcon',
            entry_route='/apps/healthy',
            required_modules=[m['name'] for m in MODULES],
            required_capabilities=['healthy:view'],
            consumed_datasets=[p['dataset_slug'] for p in PIPELINES.values()],
            is_system=False,
            is_active=True,
        )
        self.stdout.write(f'Registered app manifest: {manifest.slug}')

        # 2. Modules.
        for spec in MODULES:
            module, created = Module.objects.get_or_create(
                name=spec['name'], defaults={'description': spec['description']},
            )
            self.stdout.write(f"{'Created' if created else 'Found'} module: {module.name}")

        # 3. Read-only ERP DataSource.
        data_source = ERPSnapshotService().get_data_source()
        self.stdout.write(f'DataSource ready: {data_source.name}')

        # 4. Pipeline datasets + contracts.
        svc = HealthyPipelineService()
        for key, spec in PIPELINES.items():
            dataset, _ = svc.ensure_dataset(spec)
            self.stdout.write(f"Dataset ready: {dataset.slug} ({key})")

        self.stdout.write(self.style.SUCCESS(
            'Healthy Foods Factory registered (1 manifest, 5 modules, '
            '1 DataSource, 5 datasets).'
        ))
