"""
Idempotent AASTMT staff accounts for local and production testing.

  ahmed            Dr. Ahmed Saied          platform superuser (existing)
  mostafa.kamel    Eng. Mostafa Kamel       carbon lead (academy admin)
  mostafa.saad     Dr. Mostafa Saad         carbon lead (academy admin)
  ismael.ghafar    Dr. Ismael Abdel Ghafar  president (read-only viewer)
  data.<campus>    one data owner per AASTMT campus

ahmed keeps CARBON_ADMIN_PASSWORD or AdminPa_132.
Every other account uses AAST_STAFF_PASSWORD or AASTcarbonPa_132.
A password that matches neither that default nor the previous shared
default AdminPa_132 is left alone.
--force-change (or CARBON_FORCE_PASSWORD_CHANGE=1) marks accounts that
still hold AASTcarbonPa_132 so the next sign-in must replace it.
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from accounts.constants import CARBON_LEAD_GROUP, DATAOWNERS_GROUP, VIEWERS_GROUP
from accounts.models import PasswordPolicy, ScopedRole
from mdm.models import OrgUnit

CAMPUS_OWNERS = (
    ("data.abuqir", "abqir", "Abu Qir"),
    ("data.dokki", "dokki", "Giza Dokki"),
    ("data.smartvillage", "smart-village", "Smart Village"),
    ("data.heliopolis", "heliopolis", "Cairo Heliopolis"),
    ("data.alamein", "alamein", "New Alamein"),
    ("data.miami", "miami", "Alexandria Miami"),
    ("data.latakia", "latakia", "Syria Latakia"),
    ("data.portsaid", "port-said", "Port Said"),
    ("data.southvalley", "south-valley", "Aswan South Valley"),
)


class Command(BaseCommand):
    help = "Ensure AASTMT test accounts: carbon leads, president, and one data owner per campus."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-change",
            action="store_true",
            help="Require a new password on next sign-in while the shared password is still in use.",
        )

    def handle(self, *args, **options):
        brand = getattr(settings, "DJANGO_BRAND", "aastmt")
        if brand != "aastmt":
            self.stdout.write(
                f"  Skipping — ensure_aastmt_staff is brand-scoped to 'aastmt' "
                f"(current brand={brand})."
            )
            return

        ahmed_password = os.environ.get("CARBON_ADMIN_PASSWORD", "AdminPa_132")
        staff_password = os.environ.get("AAST_STAFF_PASSWORD", "AASTcarbonPa_132")
        force = bool(options["force_change"]) or os.environ.get("CARBON_FORCE_PASSWORD_CHANGE") == "1"
        User = get_user_model()

        self._align_policy()
        lead = Group.objects.get_or_create(name=CARBON_LEAD_GROUP)[0]
        viewers = Group.objects.get_or_create(name=VIEWERS_GROUP)[0]
        owners = Group.objects.get_or_create(name=DATAOWNERS_GROUP)[0]

        roster = []

        ahmed = self._ensure_user(
            User,
            username="ahmed",
            first_name="Ahmed",
            last_name="Saied",
            email="ahmed@aast.edu",
            password=ahmed_password,
            force=False,
            repair_password=True,
        )
        ahmed.is_superuser = True
        ahmed.is_staff = True
        ahmed.is_active = True
        ahmed.save()
        roster.append((ahmed.username, "superuser", "academy"))

        for username, first, last in (
            ("mostafa.kamel", "Mostafa", "Kamel"),
            ("mostafa.saad", "Mostafa", "Saad"),
        ):
            user = self._ensure_user(
                User,
                username=username,
                first_name=first,
                last_name=last,
                email=f"{username}@aast.edu",
                password=staff_password,
                force=force,
                previous=("AdminPa_132",),
            )
            self._grant(user, lead, None)
            roster.append((user.username, "carbon lead", "academy"))

        president = self._ensure_user(
            User,
            username="ismael.ghafar",
            first_name="Ismael",
            last_name="Abdel Ghafar",
            email="ismael.ghafar@aast.edu",
            password=staff_password,
            force=force,
            previous=("AdminPa_132",),
        )
        self._grant(president, viewers, None)
        roster.append((president.username, "president", "academy"))

        for username, code, label in CAMPUS_OWNERS:
            campus = OrgUnit.objects.filter(code=code, parent__code="AASTMT", is_active=True).first()
            if campus is None:
                raise CommandError(f"AASTMT campus with code {code!r} was not found.")
            user = self._ensure_user(
                User,
                username=username,
                first_name=label,
                last_name="Data owner",
                email=f"{username}@aast.edu",
                password=staff_password,
                force=force,
                previous=("AdminPa_132",),
            )
            self._grant(user, owners, campus)
            roster.append((user.username, "data owner", campus.name))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("AASTMT test accounts"))
        self.stdout.write(f"  ahmed password: {ahmed_password}")
        self.stdout.write(f"  staff password: {staff_password}")
        self.stdout.write(
            "  change required: "
            + ("yes, while the staff password is still in use" if force else "no (dev)")
        )
        for username, role, scope in roster:
            self.stdout.write(f"  {username:<22} {role:<14} {scope}")

    def _align_policy(self):
        policy = PasswordPolicy.load()
        policy.min_length = 10
        policy.require_uppercase = False
        policy.require_lowercase = True
        policy.require_number = True
        policy.require_special = False
        policy.save()

    def _ensure_user(self, User, *, username, first_name, last_name, email, password, force, repair_password=False, previous=()):
        user, created = User.objects.get_or_create(username=username)
        holds_default = user.check_password(password) if user.has_usable_password() else False
        holds_previous = any(user.check_password(old) for old in previous) if user.has_usable_password() else False
        if created or not user.has_usable_password() or holds_previous or (repair_password and not holds_default):
            user.set_password(password)
            holds_default = True
        user.first_name = first_name
        user.last_name = last_name
        if created or not user.email:
            user.email = email
        user.is_active = True
        if created:
            user.is_staff = False
            user.is_superuser = False
        elif username != "ahmed":
            user.is_superuser = False
        if holds_default:
            user.must_change_password = force
        user.save()
        return user

    def _grant(self, user, group, org_unit):
        user.groups.add(group)
        role = ScopedRole.objects.filter(
            user=user, group=group, org_unit=org_unit, module=None,
        ).first()
        if role is None:
            ScopedRole.objects.create(
                user=user,
                group=group,
                org_unit=org_unit,
                module=None,
                provenance=ScopedRole.PROVENANCE_EXCEPTION,
                is_active=True,
            )
        elif not role.is_active:
            role.is_active = True
            role.save(update_fields=["is_active"])
