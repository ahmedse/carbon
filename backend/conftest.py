import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import Group
import uuid

from accounts.models import Tenant, ScopedRole  # <-- Add ScopedRole import

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_tenant():
    def _create_tenant(name=None):
        if name is None:
            name = "TestTenant_" + str(uuid.uuid4())
        return Tenant.objects.create(name=name)
    return _create_tenant

@pytest.fixture
def create_user(create_tenant):
    def _create_user(username, password="pass", groups=None, is_staff=False, is_superuser=False, tenant=None):
        if tenant is None:
            tenant = create_tenant()
        user = User.objects.create_user(username=username, password=password, tenant=tenant)
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
        if groups:
            for group in groups:
                g, _ = Group.objects.get_or_create(name=group)
                user.groups.add(g)
        return user
    return _create_user

@pytest.fixture
def create_scoped_role():
    def _create_scoped_role(user, group_name, tenant=None, project=None, module=None, is_active=True):
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name=group_name)
        if tenant is None:
            tenant = user.tenant
        return ScopedRole.objects.create(
            user=user, group=group, tenant=tenant,
            project=project, module=module, is_active=is_active
        )
    return _create_scoped_role

@pytest.fixture
def get_token_for_user():
    def _get_token(user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    return _get_token