"""
accounts/management/commands/apply_brand.py

Switch the instance brand in one step:  `python manage.py apply_brand nibras`

Applies the BRAND_APP_PRESETS entry for the target brand to PlatformAppConfig
(domain apps only — core platform apps stay enabled). More surgical than
bootstrap_platform, which also (re)creates groups and reassigns superusers.

Usage:
    python manage.py apply_brand nibras
    python manage.py apply_brand            # uses settings.DJANGO_BRAND
"""

from django.core.management.base import BaseCommand
from django.conf import settings

from accounts.models import PlatformAppConfig


class Command(BaseCommand):
    help = "Apply a brand's app-enablement preset to PlatformAppConfig (domain apps only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "brand",
            nargs="?",
            default=None,
            help="Brand id to apply (defaults to settings.DJANGO_BRAND).",
        )

    def handle(self, *args, **options):
        brand = options["brand"] or getattr(settings, "DJANGO_BRAND", "aastmt")
        presets = getattr(settings, "BRAND_APP_PRESETS", {})
        preset = presets.get(brand)

        if preset is None:
            known = ", ".join(presets.keys()) or "(none)"
            self.stderr.write(self.style.ERROR(
                f"Unknown brand '{brand}'. Known brands: {known}"
            ))
            raise SystemExit(1)

        updated = 0
        for app_id, is_enabled in preset.items():
            PlatformAppConfig.objects.update_or_create(
                app_id=app_id,
                defaults={"is_enabled": is_enabled},
            )
            updated += 1
            self.stdout.write(
                f"  {'✓' if is_enabled else '✗'} {app_id:14s} enabled={is_enabled}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Applied brand '{brand}' — {updated} domain app(s) configured."
        ))
