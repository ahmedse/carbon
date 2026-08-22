"""
appregistry/management/commands/activate_apps.py

Per-instance app activation bootstrap (ADR-0015). Each deployment activates only
the domain apps it needs; every other non-system app is deactivated. This is the
ONLY per-instance difference in the codebase — one codebase, many isolated
deployments.

Usage:

    python manage.py activate_apps --active emissions,people
    python manage.py activate_apps --active healthy
    python manage.py activate_apps --all

Rules:

  * System apps (is_system=True) are ALWAYS activated and never deactivated.
  * Non-system apps not listed in --active are deactivated (unless --all).
  * A slug in --active with no manifest yet is reported (a warning, not an error)
    so deployments can safely list forward-looking apps.
  * Idempotent — safe to run on every deploy.
"""
from django.core.management.base import BaseCommand

from appregistry.models import AppManifest
from appregistry.services import AppRegistryService


class Command(BaseCommand):
    help = 'Activate a per-instance subset of domain apps (deactivate the rest).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--active', default='',
            help='Comma-separated app slugs to activate (e.g. emissions,people).',
        )
        parser.add_argument(
            '--all', action='store_true',
            help='Activate every non-system app (ignores --active).',
        )

    def handle(self, *args, **options):
        activate_all = options['all']
        active_slugs = {
            slug.strip()
            for slug in (options['active'] or '').split(',')
            if slug.strip()
        }

        if not activate_all and not active_slugs:
            self.stdout.write(self.style.WARNING(
                'No --active or --all given. Pass --active <slugs> to activate a '
                'subset, or --all to activate everything. Nothing changed.'
            ))
            return

        manifests = list(AppManifest.objects.all())
        if not manifests:
            self.stdout.write(self.style.WARNING('No AppManifests registered yet.'))
            return

        activated, deactivated, system = [], [], []

        for app in manifests:
            if app.is_system:
                AppRegistryService.activate(app)
                system.append(app.slug)
                continue
            if activate_all or app.slug in active_slugs:
                AppRegistryService.activate(app)
                activated.append(app.slug)
            else:
                AppRegistryService.deactivate(app)
                deactivated.append(app.slug)

        if not activate_all:
            known = {app.slug for app in manifests}
            missing = sorted(active_slugs - known)
            if missing:
                self.stdout.write(self.style.WARNING(
                    f'No manifest yet for: {", ".join(missing)} '
                    '(will activate once registered).'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Activated {len(activated)}: {", ".join(sorted(activated)) or "-"}'
        ))
        if deactivated:
            self.stdout.write(
                f'Deactivated {len(deactivated)}: {", ".join(sorted(deactivated))}'
            )
        if system:
            self.stdout.write(
                f'System apps (always active): {", ".join(sorted(system))}'
            )
