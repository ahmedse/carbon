"""
accounts/management/commands/ensure_nibras_admins.py

Idempotent account provisioning for the Nibras HRMS instance.

`bootstrap_platform._assign_superusers()` only mirrors `is_superuser=True`
accounts into a global `admins_group` ScopedRole (the CBAC source of truth the
frontend reads in me/context + my-roles). The Nibras brand admin is deliberately
NOT a Django superuser, so this command maintains it separately.

Guarantees, on every run (no-op unless DJANGO_BRAND == "nibras"):

  * ahmed / {CARBON_ADMIN_PASSWORD|AdminPa_132}
        UNIVERSAL platform SUPERUSER (same on every brand DB)
        → is_superuser=True, is_staff=True, active,
                              admins_group + global ScopedRole
  * admin / {NIBRAS_ADMIN_PASSWORD|AdmNibras_132}
        Nibras admin        → is_superuser=False, is_staff=True, active,
                              admins_group + global ScopedRole
                              (resolves to global admin via user_is_global_admin)
  * Employees (ESS) — not provisioned here; forever-dev password is
        emp_* / {EMPLOYEE_DEFAULT_PASSWORD|mozafNibrasPa_132}
        (canonical demo: emp_1067)

Credentials are read from the environment with the documented defaults; nothing
new is hardcoded beyond those defaults (matching existing practice in the repo).

Usage:
    python manage.py ensure_nibras_admins
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from accounts.constants import ADMINS_GROUP
from accounts.models import ScopedRole


class Command(BaseCommand):
    help = "Ensure Nibras admin accounts (ahmed=superuser, admin=nibras admin) are correctly configured."

    def handle(self, *args, **options):
        brand = getattr(settings, "DJANGO_BRAND", "aastmt")
        if brand != "nibras":
            self.stdout.write(
                f"  Skipping — ensure_nibras_admins is brand-scoped to 'nibras' "
                f"(current brand={brand})."
            )
            return

        User = get_user_model()

        superuser_username = os.environ.get("NIBRAS_SUPERUSER_USERNAME", "ahmed")
        superuser_password = os.environ.get("CARBON_ADMIN_PASSWORD", "AdminPa_132")
        admin_username = os.environ.get("NIBRAS_ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("NIBRAS_ADMIN_PASSWORD", "AdmNibras_132")

        admins_group, _ = Group.objects.get_or_create(name=ADMINS_GROUP)

        # ── 1. ahmed → platform SUPERUSER ─────────────────────────────────────
        # Only set_password when the hash does not already match — unconditional
        # rehash on every ensure/entrypoint run looks like "password keeps changing".
        ahmed, _ = User.objects.get_or_create(username=superuser_username)
        ahmed_pwd_touched = False
        if not ahmed.check_password(superuser_password):
            ahmed.set_password(superuser_password)
            ahmed_pwd_touched = True
        ahmed.is_active = True
        ahmed.is_staff = True
        ahmed.is_superuser = True
        ahmed.save()

        # ── 2. admin → Nibras admin (NOT a superuser) ────────────────────────
        admin, _ = User.objects.get_or_create(username=admin_username)
        admin_pwd_touched = False
        if not admin.check_password(admin_password):
            admin.set_password(admin_password)
            admin_pwd_touched = True
        admin.is_active = True
        admin.is_staff = True
        admin.is_superuser = False
        admin.save()

        # ── 3. Mirror both into admins_group + global CBAC ScopedRole ─────────
        for user in (ahmed, admin):
            user.groups.add(admins_group)
            role, created = ScopedRole.objects.get_or_create(
                user=user,
                group=admins_group,
                org_unit=None,
                module=None,
                defaults={"is_active": True},
            )
            if not role.is_active:
                role.is_active = True
                role.save(update_fields=["is_active"])

        # ── 4. Leave-type MDM aliases (عارضة→emergency, …) ───────────────────
        # Idempotent SSOT for ESS + Chat recovery (people.leave_type_resolve).
        aliases_updated = 0
        try:
            from people.leave_type_resolve import ensure_leave_type_aliases

            aliases_updated = ensure_leave_type_aliases()
        except Exception as exc:  # noqa: BLE001 — never block admin ensure
            self.stdout.write(self.style.WARNING(
                f"  leave_type aliases skipped: {exc}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"✓ Nibras admins ensured (brand={brand}):\n"
            f"    {ahmed.username:8s} superuser=True  staff=True  "
            f"password_ok={ahmed.check_password(superuser_password)}  "
            f"pwd_updated={ahmed_pwd_touched}\n"
            f"    {admin.username:8s} superuser=False staff=True  "
            f"password_ok={admin.check_password(admin_password)}  "
            f"pwd_updated={admin_pwd_touched}\n"
            f"    both in {ADMINS_GROUP} with a global ScopedRole.\n"
            f"    leave_type aliases updated={aliases_updated}."
        ))
