#!/usr/bin/env python
"""
Fixed User Seeding Script
==========================
Creates standard users with FIXED credentials that NEVER change:
- admin / admin123 (superuser)
- dataowner1 / owner123 (data owner)
- dataviewer1 / viewer123 (data viewer)

All users are assigned to AAST Carbon project.
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
from accounts.models import Tenant, ScopedRole
from core.models import Project

User = get_user_model()

# FIXED CREDENTIALS - NEVER CHANGE THESE
USERS = [
    {
        'username': 'admin',
        'password': 'admin123',
        'email': 'admin@aastmt.edu.eg',
        'is_superuser': True,
        'is_staff': True,
        'role_name': 'admins_group',
    },
    {
        'username': 'dataowner1',
        'password': 'owner123',
        'email': 'dataowner1@aastmt.edu.eg',
        'is_superuser': False,
        'is_staff': False,
        'role_name': 'dataowners_group',
    },
    {
        'username': 'dataviewer1',
        'password': 'viewer123',
        'email': 'dataviewer1@aastmt.edu.eg',
        'is_superuser': False,
        'is_staff': False,
        'role_name': 'viewers_group',
    },
]


def main():
    print("\n" + "="*70)
    print("FIXED USER SEEDING - AASTMT Carbon Platform")
    print("="*70 + "\n")

    # Get or create AAST tenant
    tenant, _ = Tenant.objects.get_or_create(
        name='AAST'
    )
    print(f"✓ Tenant: {tenant.name}")

    # Get AAST Carbon project
    try:
        project = Project.objects.get(name='AAST Carbon')
        print(f"✓ Project: {project.name}")
    except Project.DoesNotExist:
        print("ERROR: AAST Carbon project not found. Please run seed_rbac first.")
        return

    created_count = 0
    updated_count = 0

    for user_data in USERS:
        username = user_data['username']
        password = user_data['password']
        email = user_data['email']
        is_superuser = user_data['is_superuser']
        is_staff = user_data['is_staff']
        role_name = user_data['role_name']

        # Create or update user
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_superuser': is_superuser,
                'is_staff': is_staff,
                'tenant': tenant,
            }
        )

        if created:
            created_count += 1
            print(f"\n✓ Created user: {username}")
        else:
            updated_count += 1
            print(f"\n✓ Updated user: {username}")
            # Update fields
            user.email = email
            user.is_superuser = is_superuser
            user.is_staff = is_staff
            user.tenant = tenant

        # ALWAYS reset password to ensure it's correct
        user.set_password(password)
        user.save()

        # Get or create the group (role)
        group, _ = Group.objects.get_or_create(name=role_name)

        # Assign project role using ScopedRole
        scoped_role, _ = ScopedRole.objects.get_or_create(
            user=user,
            tenant=tenant,
            project=project,
            module=None,  # Project-level role
            defaults={
                'group': group,
            }
        )
        
        if not created:
            # Update group if it changed
            if scoped_role.group != group:
                scoped_role.group = group
                scoped_role.save()

        print(f"  • Email: {email}")
        print(f"  • Password: {password}")
        print(f"  • Role: {role_name}")
        print(f"  • Superuser: {is_superuser}")
        print(f"  • Project: {project.name}")

    print("\n" + "="*70)
    print(f"COMPLETED")
    print(f"  Created: {created_count}")
    print(f"  Updated: {updated_count}")
    print("="*70)
    print("\n🔑 LOGIN CREDENTIALS (FIXED - NEVER CHANGE):")
    print("-" * 70)
    for user_data in USERS:
        print(f"  {user_data['username']:15} / {user_data['password']:15} ({user_data['role_name']})")
    print("-" * 70)
    print()


if __name__ == '__main__':
    main()
