"""Tests for RequestAuditLogViewSet — the general request audit trail API.

Regression coverage for the QA defect where the Admin "Audit Log" page showed
"Total Events: 0" because the frontend was wired to the role-assignment-only
``accounts/role-audit-logs/`` endpoint instead of the general request audit.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RequestAuditLog

User = get_user_model()


def _unwrap_list(data):
    """Pagination is disabled under pytest, but tolerate a paginated envelope."""
    if isinstance(data, list):
        return data
    return data.get('results', [])


class TestRequestAuditLogAPI(TestCase):
    """GET /carbon-api/core/audit-logs/ returns the general request audit trail."""

    def setUp(self):
        self.api_client = APIClient()
        self.superuser = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='pass'
        )
        self.alice = User.objects.create_user(username='alice', password='pass')
        self.bob = User.objects.create_user(username='bob', password='pass')
        token = str(RefreshToken.for_user(self.superuser).access_token)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        self.list_url = reverse('requestauditlog-list')

    def _create_log(self, user, method='POST', path='/carbon-api/carbon/calculations/',
                    status_code=201):
        return RequestAuditLog.objects.create(
            user=user,
            ip_address='203.0.113.7',
            method=method,
            path=path,
            query_string='filter=active',
            status_code=status_code,
            duration_ms=42,
            correlation_id='corr-123',
        )

    def test_list_returns_audit_logs(self):
        RequestAuditLog.objects.all().delete()
        self._create_log(self.alice, method='POST')
        self._create_log(self.bob, method='DELETE', path='/carbon-api/carbon/calculations/1/')

        response = self.api_client.get(self.list_url, **self.auth)

        self.assertEqual(response.status_code, 200)
        results = _unwrap_list(response.data)
        self.assertEqual(len(results), 2)
        # Ordered by -timestamp: the most recently created (bob's DELETE) is first.
        self.assertEqual(results[0]['method'], 'DELETE')
        self.assertEqual(results[0]['user'], 'bob')
        self.assertEqual(results[0]['ip_address'], '203.0.113.7')
        self.assertEqual(results[0]['path'], '/carbon-api/carbon/calculations/1/')

    def test_filter_by_user(self):
        RequestAuditLog.objects.all().delete()
        self._create_log(self.alice)
        self._create_log(self.bob)

        response = self.api_client.get(self.list_url, {'user': 'ali'}, **self.auth)

        self.assertEqual(response.status_code, 200)
        results = _unwrap_list(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['user'], 'alice')

    def test_filter_by_method(self):
        RequestAuditLog.objects.all().delete()
        self._create_log(self.alice, method='POST')
        self._create_log(self.alice, method='PATCH')
        self._create_log(self.bob, method='DELETE')

        response = self.api_client.get(self.list_url, {'method': 'POST,PATCH'}, **self.auth)

        self.assertEqual(response.status_code, 200)
        results = _unwrap_list(response.data)
        self.assertEqual(len(results), 2)
        self.assertEqual({r['method'] for r in results}, {'POST', 'PATCH'})

    def test_requires_admin(self):
        RequestAuditLog.objects.all().delete()
        self._create_log(self.alice)

        # A non-admin user is denied access to the audit trail.
        plain_token = str(RefreshToken.for_user(self.alice).access_token)
        response = self.api_client.get(
            self.list_url, HTTP_AUTHORIZATION=f'Bearer {plain_token}'
        )
        self.assertEqual(response.status_code, 403)

    def test_filter_by_timestamp_range(self):
        RequestAuditLog.objects.all().delete()
        old_log = self._create_log(self.alice, method='POST')
        new_log = self._create_log(self.bob, method='DELETE')
        # ``timestamp`` is auto_now_add, so backdate via queryset update.
        RequestAuditLog.objects.filter(pk=old_log.pk).update(timestamp='2026-01-01T10:00:00Z')
        RequestAuditLog.objects.filter(pk=new_log.pk).update(timestamp='2026-06-01T10:00:00Z')

        response = self.api_client.get(
            self.list_url,
            {'timestamp__gte': '2026-02-01T00:00:00Z', 'timestamp__lte': '2026-12-31T23:59:59Z'},
            **self.auth,
        )

        self.assertEqual(response.status_code, 200)
        results = _unwrap_list(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['method'], 'DELETE')
