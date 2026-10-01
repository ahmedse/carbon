"""ensure_people_inbound_templates — idempotent official People InboundTemplate seed.

Creates the three official typed_object templates (identity column maps) if
missing. Never overwrites an existing row's mapping (operator customizations).

Also hooked from backend/entrypoint.sh after migrate (create-only soft-fail),
and at the end of seed_gofsco_rules. Not called from AppConfig.ready().

Usage:
    python manage.py ensure_people_inbound_templates
"""

from django.core.management.base import BaseCommand

from people.official_inbound_templates import ensure_official_inbound_templates


class Command(BaseCommand):
    help = (
        'Ensure official People inbound templates exist '
        '(identity maps; create-only; no mapping overwrite).'
    )

    def handle(self, *args, **options):
        result = ensure_official_inbound_templates()
        self.stdout.write(
            self.style.SUCCESS(
                f"Official People inbound templates: "
                f"created={result['created']} existing={result['existing']} "
                f"expected={result['expected']} keys={','.join(result['keys'])}"
            )
        )
