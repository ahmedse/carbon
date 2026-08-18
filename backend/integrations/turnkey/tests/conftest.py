"""Shared fixtures for the integrations.turnkey test suite.

Mirrors datahub/tests/conftest.py: module + dataset factories, plus TurnKey
bridge factories (config / link) and a signed-callback helper for the HMAC
endpoints.
"""
import hashlib
import hmac
import json

import pytest
from django.conf import settings

from catalog.models import DataDomain
from core.models import Module
from datahub.models import DataContract, Dataset, DatasetVersion
from dataschema.models import DataTable
from integrations.turnkey.models import TurnKeyConfig, TurnKeyModelLink


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
def make_table(db):
    """Factory: make_table(module, **kwargs) -> DataTable"""
    def _make(module, **kwargs):
        defaults = {'title': 'Payroll Rows', 'name': 'payroll_rows', 'module': module}
        defaults.update(kwargs)
        return DataTable.objects.create(**defaults)
    return _make


@pytest.fixture
def make_version(db):
    """Factory: make_version(dataset, data_table, **kwargs) -> DatasetVersion"""
    def _make(dataset, data_table, **kwargs):
        defaults = {
            'dataset': dataset,
            'version_number': 1,
            'data_table': data_table,
            'status': 'approved',
            'health_score': 0.95,
        }
        defaults.update(kwargs)
        return DatasetVersion.objects.create(**defaults)
    return _make


@pytest.fixture
def make_config(db):
    """Factory: make_config(**kwargs) -> TurnKeyConfig (no API key by default)."""
    def _make(**kwargs):
        defaults = {'name': 'default-turnkey', 'base_url': 'https://turnkey.example'}
        defaults.update(kwargs)
        return TurnKeyConfig.objects.create(**defaults)
    return _make


@pytest.fixture
def make_link(db):
    """Factory: make_link(dataset_version, config, **kwargs) -> TurnKeyModelLink."""
    def _make(dataset_version, config, **kwargs):
        defaults = {
            'dataset_version': dataset_version,
            'turnkey_config': config,
            'turnkey_model_id': 'm_001',
            'turnkey_model_name': 'payroll-forecast',
            'purpose': 'inference',
            'status': 'registered',
        }
        defaults.update(kwargs)
        return TurnKeyModelLink.objects.create(**defaults)
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


def sign_body(body: bytes) -> str:
    """HMAC-SHA256 hex signature over the raw request body."""
    return hmac.new(
        settings.TURNKEY_CALLBACK_SECRET.encode(), body, hashlib.sha256,
    ).hexdigest()


def signed_post(client, url, payload):
    """POST a JSON payload with a valid X-TurnKey-Signature header."""
    body = json.dumps(payload).encode('utf-8')
    return client.post(
        url, data=body, content_type='application/json',
        HTTP_X_TURNKEY_SIGNATURE=sign_body(body),
    )
