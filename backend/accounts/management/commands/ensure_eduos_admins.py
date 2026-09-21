"""
accounts/management/commands/ensure_eduos_admins.py

Idempotent account provisioning for the EduOS (GradeVance) instance.

Mirrors ensure_nibras_admins for the eduos brand:

  * ahmed / {CARBON_ADMIN_PASSWORD|AdminPa_132}
        UNIVERSAL platform SUPERUSER (same on every brand DB)
  * admin / {EDUOS_ADMIN_PASSWORD|AdmEduos_132}
        EduOS admin (staff, not Django superuser)

Usage:
    python manage.py ensure_eduos_admins
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.constants import ADMINS_GROUP
from accounts.models import ScopedRole


class Command(BaseCommand):
    help = "Ensure EduOS admin accounts (ahmed=superuser, admin=eduos admin) are correctly configured."

    def handle(self, *args, **options):
        brand = getattr(settings, "DJANGO_BRAND", "aastmt")
        if brand != "eduos":
            self.stdout.write(
                f"  Skipping — ensure_eduos_admins is brand-scoped to 'eduos' "
                f"(current brand={brand})."
            )
            return

        User = get_user_model()

        superuser_username = os.environ.get("EDUOS_SUPERUSER_USERNAME", "ahmed")
        superuser_password = os.environ.get("CARBON_ADMIN_PASSWORD", "AdminPa_132")
        admin_username = os.environ.get("EDUOS_ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("EDUOS_ADMIN_PASSWORD", "AdmEduos_132")

        admins_group, _ = Group.objects.get_or_create(name=ADMINS_GROUP)

        ahmed, _ = User.objects.get_or_create(username=superuser_username)
        ahmed.set_password(superuser_password)
        ahmed.is_active = True
        ahmed.is_staff = True
        ahmed.is_superuser = True
        ahmed.save()

        admin, _ = User.objects.get_or_create(username=admin_username)
        admin.set_password(admin_password)
        admin.is_active = True
        admin.is_staff = True
        admin.is_superuser = False
        admin.save()

        for user in (ahmed, admin):
            user.groups.add(admins_group)
            role, _created = ScopedRole.objects.get_or_create(
                user=user,
                group=admins_group,
                org_unit=None,
                module=None,
                defaults={"is_active": True},
            )
            if not role.is_active:
                role.is_active = True
                role.save(update_fields=["is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"✓ EduOS admins ensured (brand={brand}):\n"
            f"    {ahmed.username:8s} superuser=True  staff=True  "
            f"password_ok={ahmed.check_password(superuser_password)}\n"
            f"    {admin.username:8s} superuser=False staff=True  "
            f"password_ok={admin.check_password(admin_password)}\n"
            f"    both in {ADMINS_GROUP} with a global ScopedRole."
        ))
