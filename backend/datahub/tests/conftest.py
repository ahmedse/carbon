"""Shared fixtures for the datahub test suite."""
import pytest

from catalog.models import DataDomain
from core.models import Module
from datahub.models import Dataset


@pytest.fixture
def module_a(db):
    return Module.objects.create(name='Module A', description='Unit-test module A')


@pytest.fixture
def module_b(db):
    return Module.objects.create(name='Module B', description='Unit-test module B')


@pytest.fixture
def domain(db):
    return DataDomain.objects.create(name='Finance', slug='finance')


@pytest.fixture
def make_dataset(db):
    """Factory: make_dataset(module, domain=None, **kwargs) -> Dataset"""
    def _make(module, domain=None, **kwargs):
        defaults = {
            'name': 'Payroll Master',
            'slug': 'payroll-master',
            'module': module,
            'description': 'Test dataset',
        }
        defaults.update(kwargs)
        if domain is not None:
            defaults['domain'] = domain
        return Dataset.objects.create(**defaults)
    return _make


@pytest.fixture
def auth_client(api_client, create_user, get_token_for_user):
    """APIClient authenticated as a superuser (bypasses all capability gates)."""
    def _factory(user=None):
        if user is None:
            user = create_user('hub_admin', is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        return api_client
    return _factory


CSV_SAMPLE = b"name,age,department\nAmina,30,Finance\nOmar,28,IT\n"
