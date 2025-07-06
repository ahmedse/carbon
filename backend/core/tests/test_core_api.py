import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from accounts.models import Tenant, User
from core.models import Project, Module, Cycle

@pytest.fixture
def tenant():
    return Tenant.objects.create(name="T")

@pytest.fixture
def user(tenant):
    return User.objects.create_user(username="user", password="pass", tenant=tenant)

@pytest.fixture
def project(tenant):
    return Project.objects.create(name="Proj", tenant=tenant)

@pytest.fixture
def module(project):
    return Module.objects.create(name="Mod", project=project)

@pytest.fixture
def cycle(project):
    return Cycle.objects.create(name="Cycle 1", project=project)

@pytest.fixture
def api_client():
    return APIClient()

def get_token(api_client, username, password):
    url = reverse('token_obtain_pair')
    response = api_client.post(url, {"username": username, "password": password})
    assert response.status_code == 200
    return response.data['access']

def auth_client(api_client, token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client

@pytest.mark.django_db
def test_project_list(api_client, user, project):
    token = get_token(api_client, user.username, "pass")
    client = auth_client(api_client, token)
    resp = client.get(reverse('project-list'))
    print(f"[API] project-list status: {resp.status_code}, projects: {resp.data}")
    assert resp.status_code == 200
    assert any(p['name'] == project.name for p in resp.data)

@pytest.mark.django_db
def test_module_list(api_client, user, module):
    token = get_token(api_client, user.username, "pass")
    client = auth_client(api_client, token)
    resp = client.get(reverse('module-list'))
    print(f"[API] module-list status: {resp.status_code}, modules: {resp.data}")
    assert resp.status_code == 200
    assert any(m['name'] == module.name for m in resp.data)

@pytest.mark.django_db
def test_cycle_list(api_client, user, cycle):
    token = get_token(api_client, user.username, "pass")
    client = auth_client(api_client, token)
    resp = client.get('/api/core/cycles/')
    print(f"[API] cycle-list status: {resp.status_code}, cycles: {resp.data}")
    assert resp.status_code == 200
    assert any(c['name'] == cycle.name for c in resp.data)