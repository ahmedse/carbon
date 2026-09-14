from django.core.management.base import BaseCommand
from accounts.models import User

# Group → ScopedRole mapping: global (org_unit=None, module=None) so demo users
# have platform-wide visibility without requiring explicit org-unit assignments.
_ROLE_GROUPS = {
    'admin':      'admins_group',
    'auditor':    'auditors_group',
    'data-owner': 'auditors_group',
}

class Command(BaseCommand):
    help = 'Populate the database with demo users'

    def handle(self, *args, **kwargs):
        from django.contrib.auth.models import Group
        from accounts.models import ScopedRole

        users_data = [
            {'username': 'admin1', 'password': 'adminpass', 'role': 'admin'},
            {'username': 'admin2', 'password': 'adminpass', 'role': 'admin'},
            {'username': 'auditor1', 'password': 'auditorpass', 'role': 'auditor'},
            {'username': 'auditor2', 'password': 'auditorpass', 'role': 'auditor'},
            {'username': 'owner1', 'password': 'ownerpass', 'role': 'data-owner'},
            {'username': 'owner2', 'password': 'ownerpass', 'role': 'data-owner'},
        ]

        for u in users_data:
            if not User.objects.filter(username=u['username']).exists():
                user = User.objects.create_user(
                    username=u['username'],
                    password=u['password'],
                    role=u['role']
                )
                self.stdout.write(self.style.SUCCESS(f"Created user {u['username']} [{u['role']}]"))
            else:
                user = User.objects.get(username=u['username'])
                self.stdout.write(self.style.WARNING(f"User {u['username']} already exists."))

            # Ensure global ScopedRole so the user has platform-wide module visibility.
            group_name = _ROLE_GROUPS.get(u['role'])
            if group_name:
                group = Group.objects.filter(name=group_name).first()
                if group:
                    _, created = ScopedRole.objects.get_or_create(
                        user=user, group=group, org_unit=None, module=None,
                        defaults={'is_active': True},
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(
                            f"  → global {group_name} ScopedRole for {u['username']}"
                        ))