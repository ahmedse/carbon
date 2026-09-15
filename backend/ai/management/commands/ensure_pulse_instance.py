"""Ensure the active brand's Instance row exists (idempotent).

This command creates an Instance row for the current brand if it doesn't exist.
Idempotent: safe to re-run; second call does nothing and reports created=False.

Usage:
    python manage.py ensure_pulse_instance                    # resolve from DJANGO_BRAND
    python manage.py ensure_pulse_instance --instance nibras  # override instance id
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.conf import settings

from ai.instance_registry import resolve_instance_id
from ai.models.core import Instance


class Command(BaseCommand):
    help = "Ensure the active brand's Pulse Instance row exists (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--instance",
            type=str,
            default=None,
            help="Instance id to ensure (default: resolve from DJANGO_BRAND).",
        )

    def handle(self, *args, **options):
        instance_id = options.get("instance") or resolve_instance_id()

        # Resolve display_name: try DJANGO_INSTANCE_NAME, then DJANGO_PLATFORM_NAME,
        # fallback to title-cased instance_id.
        display_name = (
            getattr(settings, "INSTANCE_NAME", None)
            or getattr(settings, "PLATFORM_NAME", None)
            or self._title_case(instance_id)
        )

        # Resolve host_api_url from DJANGO_API_PREFIX (fallback /carbon-api/).
        host_api_url = getattr(settings, "API_PREFIX", "/carbon-api/")

        # host_db_url is empty (modular monolith — engine uses shared store).
        host_db_url = ""

        # Idempotent: get_or_create by id with sensible defaults.
        instance, created = Instance.objects.get_or_create(
            id=instance_id,
            defaults={
                "name": instance_id,
                "display_name": display_name,
                "host_api_url": host_api_url,
                "host_db_url": host_db_url,
                "status": "active",
            },
        )

        self.stdout.write(
            f"ensured instance {instance_id} (created={created})"
        )

    @staticmethod
    def _title_case(s: str) -> str:
        """Simple title case: capitalize first letter, leave rest unchanged."""
        return s[0].upper() + s[1:] if s else s
