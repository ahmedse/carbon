"""accounts/management/commands/backfill_scoped_roles.py

One-time / idempotent backfill for the CBAC (capability-based access control)
migration. The CBAC engine resolves permissions from ScopedRole records only
(see accounts.capabilities.get_user_capabilities), but some legacy seeds and
early users were granted Django auth.Group memberships without an equivalent
ScopedRole. Such users resolve to ZERO capabilities and get denied by the
frontend AdminRoute guard ("Access denied: platform admin role required").

This command migrates every Django auth.Group membership into a GLOBAL
ScopedRole (org_unit=None, module=None, is_active=True) via get_or_create, so
it is safe to run on every deploy. Group memberships are left untouched.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from accounts.models import ScopedRole


class Command(BaseCommand):
    help = (
        "Backfill ScopedRole records from existing Django auth.Group "
        "memberships (global scope). Idempotent."
    )

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for group in Group.objects.all().order_by("name"):
            for user in group.user_set.all().order_by("username"):
                _, was_created = ScopedRole.objects.get_or_create(
                    user=user,
                    group=group,
                    org_unit=None,
                    module=None,
                    defaults={"is_active": True},
                )
                if was_created:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  + {user.username} → {group.name} (global)"
                        )
                    )
                else:
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ ScopedRole backfill complete: {created} created, "
                f"{skipped} already present."
            )
        )
