#!/usr/bin/env python
"""
Fixed User Seeding Script — Carbon Platform (July 2026)
========================================================
Creates standard users with FIXED credentials.
Project model is REMOVED — roles are assigned via ScopedRole (org_unit, module).

FIXED CREDENTIALS (NEVER change):
  admin         / admin123    — superuser, global admins_group
  dataowner1    / owner123    — data owner, dataowners_group (global)
  analyst1      / analyst123  — analyst, analysts_group (global, read-only)
  viewer1       / viewer123   — viewer, viewers_group (global, read-only)
  transport_officer / transport123 — scoped data owner for Transport org unit

Run: python seed_users.py
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from accounts.models import ScopedRole

User = get_user_model()

# ── FIXED CREDENTIALS ──────────────────────────────────────────────────
USERS = [
    {
        'username': 'admin',
        'password': 'admin123',
        'email': 'admin@aastmt.edu.eg',
        'is_superuser': True,
        'is_staff': True,
        'role_name': 'admins_group',
        'scoped': False,   # global admin (org_unit=None, module=None)
    },
    {
        'username': 'dataowner1',
        'password': 'owner123',
        'email': 'dataowner1@aastmt.edu.eg',
        'is_superuser': False,
        'is_staff': False,
        'role_name': 'dataowners_group',
        'scoped': False,   # global data owner
    },
    {
        'username': 'analyst1',
        'password': 'analyst123',
        'email': 'analyst1@aastmt.edu.eg',
        'is_superuser': False,
        'is_staff': False,
        'role_name': 'analysts_group',
        'scoped': False,   # global analyst
    },
    {
        'username': 'viewer1',
        'password': 'viewer123',
        'email': 'viewer1@aastmt.edu.eg',
        'is_superuser': False,
        'is_staff': False,
        'role_name': 'viewers_group',
        'scoped': False,   # global viewer
    },
    {
        'username': 'transport_officer',
        'password': 'transport123',
        'email': 'transport@aastmt.edu.eg',
        'is_superuser': False,
        'is_staff': False,
        'role_name': 'dataowners_group',
        'scoped': True,    # org-scoped: only Transport org unit
        'org_unit_name': 'Transport',
    },
]


def main():
    print("\n" + "=" * 70)
    print("FIXED USER SEEDING — Carbon Platform")
    print("=" * 70 + "\n")

    created_count = 0
    updated_count = 0

    for user_data in USERS:
        username = user_data['username']
        password = user_data['password']
        email = user_data['email']
        is_superuser = user_data['is_superuser']
        is_staff = user_data['is_staff']
        role_name = user_data['role_name']
        is_scoped = user_data.get('scoped', False)
        org_unit_name = user_data.get('org_unit_name')

        # Create or update user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_superuser': is_superuser,
                'is_staff': is_staff,
            }
        )

        prefix = "✓ Created" if created else "✓ Updated"
        print(f"\n{prefix} user: {username}")

        # Always sync fields and reset password
        user.email = email
        user.is_superuser = is_superuser
        user.is_staff = is_staff
        user.set_password(password)
        user.save()

        if created:
            created_count += 1
        else:
            updated_count += 1

        # Get or create the group (role)
        group, _ = Group.objects.get_or_create(name=role_name)

        # Resolve org_unit if scoped role
        org_unit = None
        if is_scoped and org_unit_name:
            from mdm.models import OrgUnit
            org_unit = OrgUnit.objects.filter(name__iexact=org_unit_name).first()
            if not org_unit:
                print(f"  ⚠ WARNING: OrgUnit '{org_unit_name}' not found — assigning global role")

        # Assign ScopedRole (global: org_unit=None, module=None)
        scoped_role, sc_created = ScopedRole.objects.get_or_create(
            user=user,
            group=group,
            org_unit=org_unit,
            module=None,
            defaults={'is_active': True},
        )

        if not sc_created:
            # Ensure active
            if not scoped_role.is_active:
                scoped_role.is_active = True
                scoped_role.save()

        scope_desc = f"OrgUnit: {org_unit_name}" if org_unit else "global"
        print(f"  • Email: {email}")
        print(f"  • Password: {password}")
        print(f"  • Role: {role_name} ({scope_desc})")
        print(f"  • Superuser: {is_superuser}")

    print("\n" + "=" * 70)
    print("COMPLETED")
    print(f"  Created: {created_count}")
    print(f"  Updated: {updated_count}")
    print("=" * 70)
    print("\n🔑 LOGIN CREDENTIALS (FIXED):")
    print("-" * 70)
    for user_data in USERS:
        scope = f"({user_data.get('org_unit_name', 'global')})" if user_data.get('scoped') else "(global)"
        print(f"  {user_data['username']:20} / {user_data['password']:16} {user_data['role_name']} {scope}")
    print("-" * 70)
    print()


if __name__ == '__main__':
    main()
