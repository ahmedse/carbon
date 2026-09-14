"""accounts/management/commands/provision_alamein_rbac.py

Idempotent provisioning for the Alamein Campus Data Trust journey
(see alamein-campus/ALAMEIN_TEST_JOURNEY.md — "USERS & RBAC", "1.2 Create
Department Org Units", "1.3 Create Users").

Creates the five department org units under the Alamein Campus and provisions
the five ``alamein.*`` users with the correct group membership + ScopedRole(s).
Every step is find-or-create, so the command is safe to run repeatedly.

Group names are imported from accounts.constants (never hardcoded).
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.text import slugify

from accounts.constants import CARBON_LEAD_GROUP, DATAOWNERS_GROUP
from accounts.models import ScopedRole
from mdm.models import OrgUnit

# The Alamein Campus parent org unit (exists in the dev DB as id=2).
CAMPUS_NAME = "فرع العلمين — Alamein Campus"
CAMPUS_ORG_UNIT_ID = 2
CAMPUS_CODE = "ALAMEIN"

# Alamein test-user password comes from backend/.env — never hardcoded in source.
DEFAULT_PASSWORD = os.environ.get("ALAMEIN_USER_PASSWORD", "")

# (name, code)
DEPARTMENTS = [
    ("College of Medicine / كلية الطب", "MED"),
    ("Financial Affairs / الشؤون المادية", "FIN"),
    ("Transportation / النقل", "ALTRANS"),
    ("Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر", "HOTELS"),
    ("Educational Hospital / المستشفى التعليمي", "HOSPITAL"),
]

# (username, email, group_name, [org_unit_names or empty for global scope])
USER_SPECS = [
    ("alamein.admin", "alamein.admin@aast.edu", CARBON_LEAD_GROUP, []),
    (
        "alamein.medical",
        "alamein.medical@aast.edu",
        DATAOWNERS_GROUP,
        [
            "College of Medicine / كلية الطب",
            "Educational Hospital / المستشفى التعليمي",
        ],
    ),
    (
        "alamein.finance",
        "alamein.finance@aast.edu",
        DATAOWNERS_GROUP,
        ["Financial Affairs / الشؤون المادية"],
    ),
    (
        "alamein.transport",
        "alamein.transport@aast.edu",
        DATAOWNERS_GROUP,
        ["Transportation / النقل"],
    ),
    (
        "alamein.hotels",
        "alamein.hotels@aast.edu",
        DATAOWNERS_GROUP,
        ["Student Hotels — Sakan Masr / فنادق الطلبة في عمارات سكن مصر"],
    ),
]


class Command(BaseCommand):
    help = (
        "Provision Alamein Campus department org units and alamein.* users "
        "with RBAC (idempotent)."
    )

    def _get_or_create_org_unit(self, name, org_type, parent=None, code=""):
        """Find an OrgUnit by exact name, else create it (slug keyed per repo convention)."""
        org_unit = OrgUnit.objects.filter(name=name).first()
        if org_unit is not None:
            self.stdout.write(f"  = OrgUnit: {name} (already present)")
            return org_unit
        slug = f"{parent.slug}-{slugify(name)}" if parent else slugify(name)
        org_unit, _ = OrgUnit.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "org_type": org_type,
                "parent": parent,
                "code": code,
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"  + OrgUnit: {name}"))
        return org_unit

    def handle(self, *args, **options):
        if not DEFAULT_PASSWORD:
            raise CommandError(
                "ALAMEIN_USER_PASSWORD is not set — add it to backend/.env (see backend/.env.example)."
            )
        User = get_user_model()

        # 1. Alamein Campus parent (exact name first, then legacy id, then create).
        campus = OrgUnit.objects.filter(name=CAMPUS_NAME).first()
        if campus is None:
            campus = OrgUnit.objects.filter(pk=CAMPUS_ORG_UNIT_ID).first()
        if campus is None:
            campus, _ = OrgUnit.objects.get_or_create(
                slug=slugify(CAMPUS_NAME),
                defaults={
                    "name": CAMPUS_NAME,
                    "org_type": "campus",
                    "code": CAMPUS_CODE,
                    "parent": None,
                    "is_active": True,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"  + OrgUnit: {CAMPUS_NAME} (campus)"))
        else:
            self.stdout.write(f"  = OrgUnit: {campus.name} (campus, already present)")

        # 2. Department org units under the campus.
        departments = {}
        for name, code in DEPARTMENTS:
            departments[name] = self._get_or_create_org_unit(
                name, "department", parent=campus, code=code
            )

        # 3. Groups (canonical names from accounts.constants).
        carbon_lead, _ = Group.objects.get_or_create(name=CARBON_LEAD_GROUP)
        dataowners, _ = Group.objects.get_or_create(name=DATAOWNERS_GROUP)
        groups = {CARBON_LEAD_GROUP: carbon_lead, DATAOWNERS_GROUP: dataowners}

        # 4. Users + group membership + ScopedRole(s).
        for username, email, group_name, org_unit_names in USER_SPECS:
            group = groups[group_name]
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "is_active": True},
            )
            changed = False
            if created:
                user.set_password(DEFAULT_PASSWORD)
                changed = True
            else:
                if not user.is_active:
                    user.is_active = True
                    changed = True
                if not user.check_password(DEFAULT_PASSWORD):
                    user.set_password(DEFAULT_PASSWORD)
                    changed = True
                if not user.email:
                    user.email = email
                    changed = True
            if changed:
                user.save()

            user.groups.add(group)

            if org_unit_names:
                for ou_name in org_unit_names:
                    org_unit = departments[ou_name]
                    _, role_created = ScopedRole.objects.get_or_create(
                        user=user,
                        group=group,
                        org_unit=org_unit,
                        module=None,
                        defaults={"is_active": True},
                    )
                    self.stdout.write(
                        f"  {'+' if role_created else '='} ScopedRole: "
                        f"{username} -> {group_name} @ {ou_name}"
                    )
            else:
                _, role_created = ScopedRole.objects.get_or_create(
                    user=user,
                    group=group,
                    org_unit=None,
                    module=None,
                    defaults={"is_active": True},
                )
                self.stdout.write(
                    f"  {'+' if role_created else '='} ScopedRole: "
                    f"{username} -> {group_name} (global)"
                )

        self.stdout.write(
            self.style.SUCCESS("✓ Alamein RBAC provisioning complete (idempotent).")
        )
