#!/usr/bin/env python
"""
Test: Org-scoped admins cannot mutate governance resources.
Run: python test_governance_rbac.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import ScopedRole
from accounts.rbac_utils import ADMIN_ROLES
from django.contrib.auth.models import Group
from mdm.models import OrgUnit
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from accounts.permissions import ReadAnyWriteGlobalAdmin

User = get_user_model()


def setup_user(username, email, org_unit=None):
    user, _ = User.objects.get_or_create(username=username, defaults={'email': email})
    admins_group, _ = Group.objects.get_or_create(name='admins_group')
    role, created = ScopedRole.objects.get_or_create(
        user=user,
        group=admins_group,
        org_unit=org_unit,
        module=None,
        defaults={'is_active': True},
    )
    if not created and not role.is_active:
        role.is_active = True
        role.save(update_fields=['is_active'])
    return user


def get_org_unit(pk):
    return OrgUnit.objects.filter(pk=pk).first()


def test_governance_rbac():
    print('=' * 60)
    print('TEST: Governance RBAC (Global vs Org-Scoped Admin)')
    print('=' * 60)

    global_admin = setup_user('global_admin', 'global@test.com', org_unit=None)
    org_unit = get_org_unit(5)
    if not org_unit:
        org_unit = OrgUnit.objects.create(name='Test College', code='TEST', org_type='college')
    org_admin = setup_user('org_admin', 'org@test.com', org_unit=org_unit)

    print(f'Global admin: {global_admin.username} (global)')
    print(f'Org-scoped admin: {org_admin.username} (org_unit={org_unit.id})')

    factory = APIRequestFactory()
    perm = ReadAnyWriteGlobalAdmin()

    req_global_write = Request(factory.post('/test/'))
    req_global_write.user = global_admin
    global_can_write = perm.has_permission(req_global_write, None)
    print(f'Global admin can write: {global_can_write}')
    assert global_can_write, 'Global admin should have write permission'

    req_org_write = Request(factory.post('/test/'))
    req_org_write.user = org_admin
    org_can_write = perm.has_permission(req_org_write, None)
    print(f'Org-scoped admin can write: {org_can_write}')
    assert not org_can_write, 'Org-scoped admin should NOT have write permission'

    req_global_read = Request(factory.get('/test/'))
    req_global_read.user = global_admin
    req_org_read = Request(factory.get('/test/'))
    req_org_read.user = org_admin
    global_can_read = perm.has_permission(req_global_read, None)
    org_can_read = perm.has_permission(req_org_read, None)
    print(f'Global admin can read: {global_can_read}')
    print(f'Org-scoped admin can read: {org_can_read}')
    assert global_can_read and org_can_read, 'Both should have read permission'

    print('\nALL TESTS PASSED ✅')
    print('=' * 60)


if __name__ == '__main__':
    test_governance_rbac()
