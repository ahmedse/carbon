# accounts/tests/test_role_audit_log.py
# F22 — RoleAssignmentAuditLog is written on ScopedRole create/update/delete.

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import RoleAssignmentAuditLog, ScopedRole
from mdm.models import OrgUnit


def _auth(api_client, user, get_token_for_user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')


@pytest.mark.django_db
def test_scoped_role_create_writes_assigned_audit_log(
    api_client, create_user, get_token_for_user,
):
    admin = create_user('audit_admin', is_superuser=True)
    target = create_user('audit_target')
    group = Group.objects.get_or_create(name='dataowners_group')[0]

    _auth(api_client, admin, get_token_for_user)
    resp = api_client.post(reverse('access-control-list'), {
        'user': target.id,
        'group': group.id,
        'is_active': True,
    }, format='json')

    assert resp.status_code == 201

    log = RoleAssignmentAuditLog.objects.filter(
        action='assigned', user_id=target.id, actor_id=admin.id,
    ).get()
    assert log.group_id == group.id
    assert log.org_unit_id is None
    assert log.module_id is None


@pytest.mark.django_db
def test_scoped_role_update_writes_modified_audit_log(
    api_client, create_user, get_token_for_user,
):
    admin = create_user('audit_admin_upd', is_superuser=True)
    target = create_user('audit_target_upd')
    group = Group.objects.get_or_create(name='dataowners_group')[0]
    role = ScopedRole.objects.create(user=target, group=group, is_active=True)

    _auth(api_client, admin, get_token_for_user)
    resp = api_client.patch(
        reverse('access-control-detail', args=[role.id]),
        {'is_active': False}, format='json',
    )
    assert resp.status_code == 200

    log = RoleAssignmentAuditLog.objects.filter(
        action='modified', user_id=target.id, actor_id=admin.id,
    ).get()
    assert log.group_id == group.id


@pytest.mark.django_db
def test_scoped_role_delete_writes_removed_audit_log(
    api_client, create_user, get_token_for_user,
):
    admin = create_user('audit_admin_del', is_superuser=True)
    target = create_user('audit_target_del')
    group = Group.objects.get_or_create(name='dataowners_group')[0]
    org = OrgUnit.objects.create(
        name='Audit Org', slug='audit-org', code='AUD', org_type='department',
    )
    role = ScopedRole.objects.create(
        user=target, group=group, org_unit=org, is_active=True,
    )

    _auth(api_client, admin, get_token_for_user)
    resp = api_client.delete(reverse('access-control-detail', args=[role.id]))
    assert resp.status_code == 204

    log = RoleAssignmentAuditLog.objects.filter(
        action='removed', user_id=target.id, actor_id=admin.id,
    ).get()
    assert log.group_id == group.id
    assert log.org_unit_id == org.id
    # The ScopedRole is gone, but the audit row (FKs are SET_NULL) persists.
    assert not ScopedRole.objects.filter(id=role.id).exists()
