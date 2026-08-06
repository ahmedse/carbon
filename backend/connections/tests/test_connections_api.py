# File: connections/tests/test_api.py
# Comprehensive API tests: DataSource CRUD, ConsumingConnection CRUD + key rotation, RBAC

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User, ScopedRole
from django.contrib.auth.models import Group
from connections.models import DataSource, ConsumingConnection
from catalog.models import DataDomain


class DataSourceAPITests(TestCase):
    """Test DataSource CRUD lifecycle, RBAC, and test-connection action."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='ds_admin', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='ds_user', password='pass')
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.admin, group=Group.objects.get(name='admins_group'), is_active=True)
        self.domain = DataDomain.objects.create(name='Test Domain')
        self.list_url = '/carbon-api/connections/sources/'

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    # ── CRUD ──────────────────────────────────────────────────

    def test_list_returns_all_sources(self):
        DataSource.objects.create(name='S1', source_type='api')
        DataSource.objects.create(name='S2', source_type='database')
        self._auth(self.admin)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 2

    def test_create_source_with_all_fields(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {
            'name': 'REST API Prod', 'source_type': 'api',
            'description': 'Production API', 'status': 'active',
            'connection_config': {'base_url': 'https://api.example.com', 'token': 'sk-abc'},
            'domain': self.domain.id,
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'REST API Prod'
        assert resp.data['slug'] == 'rest-api-prod'
        assert resp.data['source_type'] == 'api'
        assert resp.data['owner_name'] == 'ds_admin'

    def test_retrieve_source_detail(self):
        source = DataSource.objects.create(name='Detail Src', source_type='manual', description='Manual entry')
        self._auth(self.admin)
        resp = self.client.get(f'{self.list_url}{source.id}/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == 'Detail Src'
        assert resp.data['description'] == 'Manual entry'

    def test_patch_update_source(self):
        source = DataSource.objects.create(name='Old Name', source_type='api')
        self._auth(self.admin)
        resp = self.client.patch(f'{self.list_url}{source.id}/', {'name': 'Updated Name'}, format='json')
        assert resp.status_code == status.HTTP_200_OK
        source.refresh_from_db()
        assert source.name == 'Updated Name'

    def test_delete_source_removes_it(self):
        source = DataSource.objects.create(name='Delete Me', source_type='manual')
        self._auth(self.admin)
        resp = self.client.delete(f'{self.list_url}{source.id}/')
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert DataSource.objects.filter(id=source.id).count() == 0

    def test_create_minimal_source(self):
        """Only name and source_type required."""
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'name': 'Minimal', 'source_type': 'iot'}, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['status'] == 'active'
        assert resp.data['connection_config'] == {}

    # ── Test connection action ─────────────────────────────────

    def test_test_connection_with_config(self):
        source = DataSource.objects.create(name='Testable', source_type='api', connection_config={'host': 'x.com'})
        self._auth(self.admin)
        resp = self.client.post(f'{self.list_url}{source.id}/test/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['status'] == 'success'

    def test_test_connection_empty_config(self):
        source = DataSource.objects.create(name='No Config', source_type='api', connection_config={})
        self._auth(self.admin)
        resp = self.client.post(f'{self.list_url}{source.id}/test/')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data['status'] == 'failure'

    # ── RBAC ──────────────────────────────────────────────────

    def test_non_admin_cannot_create(self):
        self._auth(self.user)
        resp = self.client.post(self.list_url, {'name': 'Hack', 'source_type': 'api'}, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_non_admin_cannot_delete(self):
        source = DataSource.objects.create(name='Protected', source_type='manual')
        self._auth(self.user)
        resp = self.client.delete(f'{self.list_url}{source.id}/')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_non_admin_cannot_patch(self):
        source = DataSource.objects.create(name='Protected', source_type='manual')
        self._auth(self.user)
        resp = self.client.patch(f'{self.list_url}{source.id}/', {'name': 'X'}, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self):
        self.client.credentials()
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # ── Edge cases ────────────────────────────────────────────

    def test_create_duplicate_name_fails(self):
        DataSource.objects.create(name='Duplicate', source_type='api')
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'name': 'Duplicate', 'source_type': 'database'}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_required_fields_fails(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'name': 'Incomplete'}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


class ConsumingConnectionAPITests(TestCase):
    """Test ConsumingConnection CRUD, key management, RBAC."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='cc_admin', password='pass', is_staff=True)
        self.user = User.objects.create_user(username='cc_user', password='pass')
        Group.objects.get_or_create(name='admins_group')
        ScopedRole.objects.create(user=self.admin, group=Group.objects.get(name='admins_group'), is_active=True)
        self.list_url = '/carbon-api/connections/consuming/'

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    # ── CRUD ──────────────────────────────────────────────────

    def test_create_connection(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {
            'name': 'Pulse AI Conn', 'system_type': 'pulse',
            'description': 'AI integration', 'scopes': [1, 2, 3],
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data['name'] == 'Pulse AI Conn'
        assert resp.data['system_type'] == 'pulse'
        assert resp.data['is_active'] is True
        assert resp.data['owner_name'] == 'cc_admin'

    def test_list_connections(self):
        ConsumingConnection.objects.create(name='C1', system_type='api_key')
        ConsumingConnection.objects.create(name='C2', system_type='webhook')
        self._auth(self.admin)
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.data) >= 2

    def test_retrieve_connection(self):
        conn = ConsumingConnection.objects.create(name='Detail Conn', system_type='powerbi')
        self._auth(self.admin)
        resp = self.client.get(f'{self.list_url}{conn.id}/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['name'] == 'Detail Conn'

    def test_patch_update_connection(self):
        conn = ConsumingConnection.objects.create(name='Old', system_type='tableau')
        self._auth(self.admin)
        resp = self.client.patch(f'{self.list_url}{conn.id}/', {
            'name': 'Updated', 'description': 'New desc', 'is_active': False
        }, format='json')
        assert resp.status_code == status.HTTP_200_OK
        conn.refresh_from_db()
        assert conn.name == 'Updated'
        assert conn.description == 'New desc'
        assert conn.is_active is False

    def test_delete_connection(self):
        conn = ConsumingConnection.objects.create(name='Del Me', system_type='api_key')
        self._auth(self.admin)
        resp = self.client.delete(f'{self.list_url}{conn.id}/')
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert ConsumingConnection.objects.filter(id=conn.id).count() == 0

    # ── API key lifecycle ─────────────────────────────────────

    def test_no_key_shows_none(self):
        conn = ConsumingConnection.objects.create(name='NoKey', system_type='api_key')
        self._auth(self.admin)
        resp = self.client.get(f'{self.list_url}{conn.id}/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['api_key_hash'] is None

    def test_key_set_shows_masked(self):
        conn = ConsumingConnection.objects.create(name='HasKey', system_type='api_key')
        conn.generate_api_key()
        self._auth(self.admin)
        resp = self.client.get(f'{self.list_url}{conn.id}/')
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['api_key_hash'] == '***SET***'

    def test_generate_and_verify_api_key(self):
        conn = ConsumingConnection.objects.create(name='GenKey', system_type='api_key')
        plaintext = conn.generate_api_key()
        assert isinstance(plaintext, str)
        assert len(plaintext) > 0
        assert conn.api_key_hash is not None
        assert conn.api_key_salt is not None
        assert conn.verify_api_key(plaintext) is True
        assert conn.verify_api_key('wrong') is False

    def test_rotate_key_endpoint(self):
        conn = ConsumingConnection.objects.create(name='RotateMe', system_type='api_key')
        conn.generate_api_key()
        old_hash = conn.api_key_hash
        self._auth(self.admin)
        resp = self.client.post(f'{self.list_url}{conn.id}/rotate_key/')
        assert resp.status_code == status.HTTP_200_OK
        assert 'api_key' in resp.data
        new_key = resp.data['api_key']
        conn.refresh_from_db()
        assert conn.api_key_hash != old_hash
        assert conn.verify_api_key(new_key) is True

    # ── RBAC ──────────────────────────────────────────────────

    def test_non_admin_cannot_create(self):
        self._auth(self.user)
        resp = self.client.post(self.list_url, {'name': 'Hack', 'system_type': 'api_key'}, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_non_admin_cannot_delete(self):
        conn = ConsumingConnection.objects.create(name='Protected', system_type='webhook')
        self._auth(self.user)
        resp = self.client.delete(f'{self.list_url}{conn.id}/')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_gets_401(self):
        self.client.credentials()
        resp = self.client.get(self.list_url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # ── Edge cases ────────────────────────────────────────────

    def test_create_duplicate_name_fails(self):
        ConsumingConnection.objects.create(name='Dup', system_type='api_key')
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'name': 'Dup', 'system_type': 'webhook'}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_system_type_fails(self):
        self._auth(self.admin)
        resp = self.client.post(self.list_url, {'name': 'No Type'}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_deactivate_connection(self):
        conn = ConsumingConnection.objects.create(name='Deact', system_type='api_key')
        self._auth(self.admin)
        resp = self.client.patch(f'{self.list_url}{conn.id}/', {'is_active': False}, format='json')
        assert resp.status_code == status.HTTP_200_OK
        conn.refresh_from_db()
        assert conn.is_active is False
