# accounts/management/commands/seed_rbac.py

from django.core.management.base import BaseCommand
from accounts.models import Permission, Role

PERMISSIONS = [
    ("manage_schema", "Can create, edit, or delete tables/fields"),
    ("manage_data", "Can create, update, or delete rows"),
    ("view_schema", "Can view tables and fields"),
    ("view_data", "Can view data in tables"),
    ("manage_project", "Can edit project settings"),
    ("manage_module", "Can edit module settings"),
]

ROLE_PERMISSIONS = {
    "admin": ["manage_schema", "manage_data", "view_schema", "view_data", "manage_project", "manage_module"],
    "auditor": ["view_schema", "view_data", "manage_data"],
    "dataowner": ["manage_schema", "manage_data", "view_schema", "view_data", "manage_module"],
}

class Command(BaseCommand):
    help = "Seeds the RBAC permissions and roles"

    def handle(self, *args, **kwargs):
        # Create Permissions
        perms = {}
        for code, desc in PERMISSIONS:
            perm, created = Permission.objects.get_or_create(code=code, defaults={"description": desc})
            perms[code] = perm

        # Create Roles and assign permissions
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role, created = Role.objects.get_or_create(name=role_name)
            role.permissions.set([perms[code] for code in perm_codes])
            role.save()

        self.stdout.write(self.style.SUCCESS("Permissions and roles seeded successfully."))