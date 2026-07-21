import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import Group

# Ensure Django's test client host is always allowed
if 'testserver' not in django_settings.ALLOWED_HOSTS:
    django_settings.ALLOWED_HOSTS.append('testserver')
if 'localhost' not in django_settings.ALLOWED_HOSTS:
    django_settings.ALLOWED_HOSTS.append('localhost')
import uuid

from accounts.models import ScopedRole

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user():
    def _create_user(username, password="pass", groups=None, is_staff=False, is_superuser=False):
        user = User.objects.create_user(username=username, password=password)
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
    def _create_scoped_role(user, group_name, org_unit=None, module=None, is_active=True):
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name=group_name)
        return ScopedRole.objects.create(
            user=user, group=group, org_unit=org_unit,
            module=module, is_active=is_active
        )
    return _create_scoped_role

@pytest.fixture
def get_token_for_user():
    def _get_token(user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    return _get_token