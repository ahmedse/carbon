"""
appregistry/management/commands/register_app.py

App self-registration (DESIGN §7.4). Each domain app declares its manifest at
setup/deploy time via this generic command:

    python manage.py register_app \
        --slug healthy --name "Healthy Foods Factory" --app-version 1.0.0 \
        --entry-route /apps/healthy \
        --required-module healthy-sales --required-module healthy-returns \
        --required-capability healthy:view \
        --consumed-dataset healthy-sales-lines

Idempotent — INSERT-OR-UPDATE on slug (safe to re-run on every deploy).
"""
from django.core.management.base import BaseCommand

from appregistry.services import AppRegistryService


class Command(BaseCommand):
    help = 'Declare (or update) a domain app manifest in the App Registry.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', required=True, help='Unique app slug')
        parser.add_argument('--name', required=True, help='Display name')
        parser.add_argument('--app-version', required=True,
                            help='Semver e.g. 1.0.0 (--version is reserved)')
        parser.add_argument('--description', default='')
        parser.add_argument('--icon', default='')
        parser.add_argument('--entry-route', default='',
                            help='Frontend React router path e.g. /apps/healthy')
        parser.add_argument('--required-module', action='append', default=[],
                            help='Module.name the app needs (repeatable)')
        parser.add_argument('--required-capability', action='append', default=[],
                            help='Capability.key users need (repeatable)')
        parser.add_argument('--consumed-dataset', action='append', default=[],
                            help='Dataset.slug the app reads (repeatable, informational)')
        parser.add_argument('--is-system', action='store_true',
                            help='System apps (e.g. emissions) cannot be deactivated')

    def handle(self, *args, **options):
        manifest, created = AppRegistryService.register_manifest(
            slug=options['slug'],
            name=options['name'],
            version=options['app_version'],
            description=options['description'],
            icon=options['icon'],
            entry_route=options['entry_route'],
            required_modules=options['required_module'],
            required_capabilities=options['required_capability'],
            consumed_datasets=options['consumed_dataset'],
            is_system=options['is_system'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Registered' if created else 'Updated'}: {manifest}"
            )
        )
